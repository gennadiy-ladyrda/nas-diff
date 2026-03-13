import { useEffect, useMemo, useState } from "react";

import {
  confirmActionBatch,
  createActionBatch,
  getActionBatch,
  getGroupDetails,
  getScanJobGroups,
  rollbackActionBatch,
  saveGroupDecision,
} from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { usePolling } from "../hooks/usePolling";
import { formatBytes, toShortPath } from "../utils/format";

const DECISIONS = ["keep", "trash", "delete", "ignore"];

export function ReviewPage({ activeJobId, recentJobIds, onSelectJob }) {
  const [jobInput, setJobInput] = useState(activeJobId || "");
  const [kind, setKind] = useState("exact");
  const [groups, setGroups] = useState([]);
  const [groupTotal, setGroupTotal] = useState(0);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [groupDetails, setGroupDetails] = useState(null);
  const [selectedFileIds, setSelectedFileIds] = useState(new Set());
  const [actionType, setActionType] = useState("move_to_trash");
  const [confirmHardDelete, setConfirmHardDelete] = useState(false);
  const [batch, setBatch] = useState(null);
  const [error, setError] = useState("");
  const [savingDecisionId, setSavingDecisionId] = useState(null);

  const selectableFileIds = useMemo(() => Array.from(selectedFileIds), [selectedFileIds]);

  async function loadGroups(targetJobId) {
    if (!targetJobId) {
      return;
    }

    setGroupsLoading(true);
    try {
      const payload = await getScanJobGroups(targetJobId, kind, 1, 100);
      setGroups(payload.items || []);
      setGroupTotal(payload.total || 0);
      setSelectedGroupId((prev) => {
        if (prev && payload.items.some((item) => item.id === prev)) {
          return prev;
        }
        return payload.items[0]?.id ?? null;
      });
    } catch (err) {
      setError(`Failed to load groups: ${err.message}`);
    } finally {
      setGroupsLoading(false);
    }
  }

  async function loadGroupDetails(groupId) {
    if (!groupId) {
      setGroupDetails(null);
      return;
    }

    try {
      const payload = await getGroupDetails(kind, groupId);
      setGroupDetails(payload);
    } catch (err) {
      setError(`Failed to load group details: ${err.message}`);
    }
  }

  async function loadBatch(batchId) {
    if (!batchId) {
      return;
    }

    try {
      const payload = await getActionBatch(batchId);
      setBatch(payload);
    } catch (err) {
      setError(`Failed to load action batch: ${err.message}`);
    }
  }

  useEffect(() => {
    setJobInput(activeJobId || "");
    if (activeJobId) {
      void loadGroups(activeJobId);
    }
  }, [activeJobId, kind]);

  useEffect(() => {
    if (selectedGroupId) {
      void loadGroupDetails(selectedGroupId);
    }
  }, [selectedGroupId, kind]);

  useEffect(() => {
    if (!groupDetails?.items) {
      setSelectedFileIds(new Set());
      return;
    }

    setSelectedFileIds(new Set(groupDetails.items.filter((item) => !item.is_primary).map((item) => item.file_id)));
  }, [groupDetails?.group_id]);

  usePolling(
    () => {
      if (activeJobId) {
        void loadGroups(activeJobId);
      }
    },
    5000,
    Boolean(activeJobId),
  );

  usePolling(
    () => {
      if (batch?.batch_id) {
        void loadBatch(batch.batch_id);
      }
    },
    2500,
    Boolean(batch?.status && ["confirmed", "draft"].includes(batch.status)),
  );

  function toggleFileSelection(fileId, checked) {
    setSelectedFileIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(fileId);
      } else {
        next.delete(fileId);
      }
      return next;
    });
  }

  async function handleDecision(fileId, decision) {
    if (!selectedGroupId) {
      return;
    }

    setSavingDecisionId(fileId);
    try {
      await saveGroupDecision(kind, selectedGroupId, { file_id: fileId, decision });
      await loadGroupDetails(selectedGroupId);
    } catch (err) {
      setError(`Failed to save decision: ${err.message}`);
    } finally {
      setSavingDecisionId(null);
    }
  }

  async function handleCreateBatch(event) {
    event.preventDefault();
    if (selectableFileIds.length === 0) {
      return;
    }

    try {
      const payload = await createActionBatch({
        action_type: actionType,
        file_ids: selectableFileIds,
        summary: `${kind}:group=${selectedGroupId}`,
      });
      setBatch(payload);
    } catch (err) {
      setError(`Failed to create action batch: ${err.message}`);
    }
  }

  async function handleConfirmBatch() {
    if (!batch?.batch_id) {
      return;
    }

    try {
      await confirmActionBatch(batch.batch_id, {
        confirm_delete_permanent: actionType === "delete_permanent" ? confirmHardDelete : false,
      });
      await loadBatch(batch.batch_id);
    } catch (err) {
      setError(`Failed to confirm batch: ${err.message}`);
    }
  }

  async function handleRollback() {
    if (!batch?.batch_id) {
      return;
    }

    try {
      const payload = await rollbackActionBatch(batch.batch_id, { requested_by: "local_admin" });
      await loadBatch(payload.rollback_batch_id);
    } catch (err) {
      setError(`Failed to rollback batch: ${err.message}`);
    }
  }

  return (
    <div className="page-grid">
      <ErrorBanner message={error} onDismiss={() => setError("")} />

      <Panel title="Review Controls" subtitle="Select job + group type to inspect dedup results">
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (jobInput.trim()) {
              onSelectJob(jobInput.trim());
            }
          }}
        >
          <input
            type="text"
            value={jobInput}
            onChange={(event) => setJobInput(event.target.value)}
            placeholder="Scan job id"
          />
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="exact">Exact groups</option>
            <option value="similar">Similar groups</option>
          </select>
          <button type="submit" className="button button--ghost">
            Load
          </button>
        </form>

        {recentJobIds.length > 0 ? (
          <div className="chip-row">
            {recentJobIds.map((jobId) => (
              <button type="button" className="chip" key={jobId} onClick={() => onSelectJob(jobId)}>
                {jobId.slice(0, 12)}...
              </button>
            ))}
          </div>
        ) : null}
      </Panel>

      <div className="review-grid">
        <Panel title="Groups" subtitle={`Found: ${groupTotal}`}>
          {groupsLoading ? <p>Loading groups...</p> : null}
          <div className="group-list" data-testid="group-list">
            {groups.length === 0 ? <p className="hint">No groups yet for the selected job.</p> : null}
            {groups.map((group) => (
              <button
                key={group.id}
                type="button"
                className={`group-row ${selectedGroupId === group.id ? "group-row--active" : ""}`}
                onClick={() => setSelectedGroupId(group.id)}
              >
                <div>
                  <strong>#{group.id}</strong>
                  <div className="hint">{group.file_count} files</div>
                </div>
                <div>
                  {kind === "exact" ? <span>{formatBytes(group.reclaimable_bytes)} reclaimable</span> : null}
                  {kind === "similar" ? <span>{group.algorithm} / t={group.threshold}</span> : null}
                </div>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Group Details" subtitle="Override primary and prepare batch items">
          {!groupDetails ? <p className="hint">Select a group to inspect files.</p> : null}
          {groupDetails?.items?.length ? (
            <div className="table-wrap" data-testid="group-details-table">
              <table>
                <thead>
                  <tr>
                    <th>Pick</th>
                    <th>File</th>
                    <th>Size</th>
                    <th>Primary</th>
                    <th>Decision</th>
                    <th>Set Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {groupDetails.items.map((item) => (
                    <tr key={item.file_id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedFileIds.has(item.file_id)}
                          onChange={(event) => toggleFileSelection(item.file_id, event.target.checked)}
                        />
                      </td>
                      <td title={item.abs_path}>
                        <code>{toShortPath(item.abs_path)}</code>
                      </td>
                      <td>{formatBytes(item.size_bytes)}</td>
                      <td>{item.is_primary ? <StatusBadge value="ok" /> : "-"}</td>
                      <td>{item.decision || "-"}</td>
                      <td>
                        <div className="decision-row">
                          {DECISIONS.map((decision) => (
                            <button
                              key={decision}
                              type="button"
                              className="tiny-button"
                              disabled={savingDecisionId === item.file_id}
                              onClick={() => void handleDecision(item.file_id, decision)}
                            >
                              {decision}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Panel>
      </div>

      <Panel title="Action Center" subtitle="Draft -> confirm -> execute -> rollback">
        <form className="stack" onSubmit={handleCreateBatch}>
          <div className="inline-form">
            <select value={actionType} onChange={(event) => setActionType(event.target.value)}>
              <option value="move_to_trash">move_to_trash</option>
              <option value="delete_permanent">delete_permanent</option>
              <option value="restore">restore</option>
            </select>
            <button type="submit" className="button" disabled={selectableFileIds.length === 0}>
              Create Draft Batch ({selectableFileIds.length})
            </button>
          </div>

          {actionType === "delete_permanent" ? (
            <label className="field-inline warning-box">
              <input
                type="checkbox"
                checked={confirmHardDelete}
                onChange={(event) => setConfirmHardDelete(event.target.checked)}
              />
              <span>I understand this is irreversible and requires explicit confirmation.</span>
            </label>
          ) : null}

          {batch ? (
            <div className="batch-card" data-testid="batch-card">
              <div className="job-card__header">
                <code>{batch.batch_id}</code>
                <StatusBadge value={batch.status} />
              </div>

              <div className="metric-grid">
                <div>
                  <span className="hint">Action</span>
                  <div>{batch.action_type}</div>
                </div>
                <div>
                  <span className="hint">Total</span>
                  <div>{batch.stats?.total ?? 0}</div>
                </div>
                <div>
                  <span className="hint">Done</span>
                  <div>{batch.stats?.done ?? 0}</div>
                </div>
                <div>
                  <span className="hint">Failed</span>
                  <div>{batch.stats?.failed ?? 0}</div>
                </div>
              </div>

              <div className="inline-actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => void handleConfirmBatch()}
                  disabled={batch.status !== "draft" || (actionType === "delete_permanent" && !confirmHardDelete)}
                >
                  Confirm Batch
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => void loadBatch(batch.batch_id)}
                >
                  Refresh
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => void handleRollback()}
                  disabled={!batch.status || !["executed", "partially_failed"].includes(batch.status)}
                >
                  Rollback
                </button>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Status</th>
                      <th>Source</th>
                      <th>Target</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(batch.items || []).map((item) => (
                      <tr key={item.id}>
                        <td>{item.file_id}</td>
                        <td>
                          <StatusBadge value={item.status} />
                        </td>
                        <td>
                          <code>{toShortPath(item.source_path)}</code>
                        </td>
                        <td>
                          <code>{toShortPath(item.target_path)}</code>
                        </td>
                        <td>{item.error_message || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="hint">Create a draft batch from selected files to start execution workflow.</p>
          )}
        </form>
      </Panel>
    </div>
  );
}
