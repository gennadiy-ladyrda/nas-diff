import { useEffect, useMemo, useRef, useState } from "react";

import {
  confirmActionBatch,
  createActionBatch,
  getActionBatch,
  getGroupDetails,
  previewActionBatch,
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
const BULK_SCOPES = [
  { value: "selected", label: "selected" },
  { value: "selected_groups", label: "selected groups" },
  { value: "all_in_group", label: "all in group" },
  { value: "all_filtered", label: "all filtered" },
];

function parseApiError(err) {
  const raw = err instanceof Error ? err.message : String(err);
  const match = raw.match(/^(\d+):\s*(.*)$/);
  if (!match) {
    return { status: null, detail: raw };
  }
  return {
    status: Number(match[1]),
    detail: match[2] || raw,
  };
}

function collectNonPrimaryFileIds(items = []) {
  return items.filter((item) => !item.is_primary).map((item) => item.file_id);
}

function buildPreviewSignature({
  jobId,
  kind,
  scope,
  actionType,
  groupId,
  fileIds,
}) {
  return [
    jobId || "none",
    kind,
    scope,
    actionType,
    String(groupId ?? "none"),
    fileIds.join(","),
  ].join("|");
}

export function ReviewPage({ activeJobId, recentJobIds, onSelectJob }) {
  const [jobInput, setJobInput] = useState(activeJobId || "");
  const [kind, setKind] = useState("exact");
  const [groups, setGroups] = useState([]);
  const [groupTotal, setGroupTotal] = useState(0);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [selectedGroupIds, setSelectedGroupIds] = useState(new Set());
  const [groupDetails, setGroupDetails] = useState(null);
  const [selectedFileIds, setSelectedFileIds] = useState(new Set());
  const [bulkDecision, setBulkDecision] = useState("trash");
  const [groupsBulkDecision, setGroupsBulkDecision] = useState("trash");
  const [selectionScope, setSelectionScope] = useState("selected");
  const [actionType, setActionType] = useState("move_to_trash");
  const [confirmHardDelete, setConfirmHardDelete] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [batch, setBatch] = useState(null);
  const [error, setError] = useState("");
  const [savingDecisionId, setSavingDecisionId] = useState(null);
  const [applyingBulkDecision, setApplyingBulkDecision] = useState(false);
  const [applyingGroupsBulkDecision, setApplyingGroupsBulkDecision] = useState(false);
  const groupDetailsCacheRef = useRef(new Map());

  const selectableFileIds = useMemo(() => Array.from(selectedFileIds).sort((a, b) => a - b), [selectedFileIds]);
  const selectedGroupMarker = useMemo(
    () => Array.from(selectedGroupIds).sort((a, b) => a - b).join(","),
    [selectedGroupIds],
  );
  const filteredGroupIdsMarker = useMemo(() => groups.map((group) => group.id).join(","), [groups]);

  function buildGroupCacheKey(groupId) {
    return `${activeJobId || "none"}:${kind}:${groupId}`;
  }

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
      setSelectedGroupIds((prev) => {
        const allowed = new Set((payload.items || []).map((item) => item.id));
        const next = new Set([...prev].filter((groupId) => allowed.has(groupId)));
        if (next.size === 0 && payload.items?.[0]?.id) {
          next.add(payload.items[0].id);
        }
        return next;
      });
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to load groups: ${parsed.detail}`);
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
      groupDetailsCacheRef.current.set(buildGroupCacheKey(groupId), payload);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to load group details: ${parsed.detail}`);
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
      const parsed = parseApiError(err);
      setError(`Failed to load action batch: ${parsed.detail}`);
    }
  }

  useEffect(() => {
    groupDetailsCacheRef.current.clear();
    setPreview(null);
    setJobInput(activeJobId || "");
    setSelectedGroupIds(new Set());
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
    if (!selectedGroupId) {
      return;
    }
    setSelectedGroupIds((prev) => {
      if (prev.has(selectedGroupId)) {
        return prev;
      }
      const next = new Set(prev);
      next.add(selectedGroupId);
      return next;
    });
  }, [selectedGroupId]);

  useEffect(() => {
    if (selectedGroupIds.size > 1 && selectionScope === "selected") {
      setSelectionScope("selected_groups");
    }
  }, [selectedGroupIds, selectionScope]);

  useEffect(() => {
    if (!groupDetails?.items) {
      setSelectedFileIds(new Set());
      return;
    }

    setSelectedFileIds(new Set(collectNonPrimaryFileIds(groupDetails.items)));
  }, [groupDetails?.group_id]);

  useEffect(() => {
    setPreview(null);
  }, [
    actionType,
    selectionScope,
    selectedGroupId,
    selectedGroupMarker,
    activeJobId,
    kind,
    selectableFileIds.join(","),
    filteredGroupIdsMarker,
  ]);

  useEffect(() => {
    if (actionType !== "delete_permanent") {
      setConfirmHardDelete(false);
    }
  }, [actionType]);

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
    Boolean(batch?.status && ["confirmed", "draft", "partially_failed"].includes(batch.status)),
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

  function toggleGroupSelection(groupId, checked) {
    setSelectedGroupIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(groupId);
      } else {
        next.delete(groupId);
      }
      return next;
    });
  }

  function selectAllGroups() {
    setSelectedGroupIds(new Set(groups.map((group) => group.id)));
  }

  function clearGroupSelection() {
    setSelectedGroupIds(new Set());
  }

  async function handleDecision(fileId, decision) {
    if (!selectedGroupId) {
      return;
    }

    setSavingDecisionId(fileId);
    try {
      await saveGroupDecision(kind, selectedGroupId, { file_id: fileId, decision });
      await loadGroupDetails(selectedGroupId);
      setPreview(null);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to save decision: ${parsed.detail}`);
    } finally {
      setSavingDecisionId(null);
    }
  }

  async function handleApplyDecisionToSelected() {
    if (!selectedGroupId || selectableFileIds.length === 0) {
      return;
    }

    setApplyingBulkDecision(true);
    try {
      for (const fileId of selectableFileIds) {
        await saveGroupDecision(kind, selectedGroupId, { file_id: fileId, decision: bulkDecision });
      }
      await loadGroupDetails(selectedGroupId);
      setPreview(null);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to apply decision to selected files: ${parsed.detail}`);
    } finally {
      setApplyingBulkDecision(false);
    }
  }

  async function handleApplyDecisionToSelectedGroups() {
    if (!activeJobId || selectedGroupIds.size === 0) {
      return;
    }

    setApplyingGroupsBulkDecision(true);
    try {
      const orderedGroupIds = Array.from(selectedGroupIds).sort((a, b) => a - b);
      for (const groupId of orderedGroupIds) {
        const cacheKey = buildGroupCacheKey(groupId);
        let details = groupDetailsCacheRef.current.get(cacheKey);
        if (!details) {
          details = await getGroupDetails(kind, groupId);
          groupDetailsCacheRef.current.set(cacheKey, details);
        }

        const fileIds = collectNonPrimaryFileIds(details.items || []);
        for (const fileId of fileIds) {
          await saveGroupDecision(kind, groupId, { file_id: fileId, decision: groupsBulkDecision });
        }

        groupDetailsCacheRef.current.delete(cacheKey);
      }

      if (selectedGroupId && selectedGroupIds.has(selectedGroupId)) {
        await loadGroupDetails(selectedGroupId);
      }
      setPreview(null);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to apply decision to selected groups: ${parsed.detail}`);
    } finally {
      setApplyingGroupsBulkDecision(false);
    }
  }

  async function resolveFileIdsForScope(scope) {
    if (scope === "selected") {
      return selectableFileIds;
    }

    if (scope === "selected_groups") {
      if (!activeJobId || selectedGroupIds.size === 0) {
        return [];
      }
      const resolved = new Set();
      const orderedGroupIds = Array.from(selectedGroupIds).sort((a, b) => a - b);

      for (const groupId of orderedGroupIds) {
        const key = buildGroupCacheKey(groupId);
        let details = groupDetailsCacheRef.current.get(key);
        if (!details) {
          details = await getGroupDetails(kind, groupId);
          groupDetailsCacheRef.current.set(key, details);
        }

        for (const fileId of collectNonPrimaryFileIds(details.items || [])) {
          resolved.add(fileId);
        }
      }

      return Array.from(resolved).sort((a, b) => a - b);
    }

    if (scope === "all_in_group") {
      return collectNonPrimaryFileIds(groupDetails?.items || []);
    }

    if (scope === "all_filtered") {
      if (!activeJobId) {
        return [];
      }
      const resolved = new Set();

      for (const group of groups) {
        const key = buildGroupCacheKey(group.id);
        let details = groupDetailsCacheRef.current.get(key);
        if (!details) {
          details = await getGroupDetails(kind, group.id);
          groupDetailsCacheRef.current.set(key, details);
        }

        for (const fileId of collectNonPrimaryFileIds(details.items || [])) {
          resolved.add(fileId);
        }
      }

      return Array.from(resolved).sort((a, b) => a - b);
    }

    return [];
  }

  async function handlePreviewBatch(event) {
    event.preventDefault();

    setPreviewLoading(true);
    try {
      const resolvedFileIds = await resolveFileIdsForScope(selectionScope);
      if (resolvedFileIds.length === 0) {
        setPreview(null);
        setError("Preview requires at least one file in the selected scope.");
        return;
      }

      const previewPayload = await previewActionBatch({
        action_type: actionType,
        file_ids: resolvedFileIds,
      });

      setPreview({
        ...previewPayload,
        selection_scope: selectionScope,
        signature: buildPreviewSignature({
          jobId: activeJobId,
          kind,
          scope: selectionScope,
          actionType,
          groupId: selectionScope === "selected_groups" ? selectedGroupMarker || "none" : selectedGroupId,
          fileIds: previewPayload.file_ids || resolvedFileIds,
        }),
      });
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to preview action batch: ${parsed.detail}`);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleCreateBatch(event) {
    event.preventDefault();
    if (!preview) {
      setError("Run preview before creating a draft batch.");
      return;
    }

    try {
      const payload = await createActionBatch({
        action_type: actionType,
        file_ids: preview.file_ids,
        summary: `${kind}:scope=${preview.selection_scope};group=${
          preview.selection_scope === "selected_groups" ? selectedGroupMarker || "none" : selectedGroupId ?? "none"
        }`,
      });
      setBatch(payload);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to create action batch: ${parsed.detail}`);
    }
  }

  async function handleConfirmBatch() {
    if (!batch?.batch_id) {
      return;
    }

    if (batch.action_type === "delete_permanent") {
      if (!confirmHardDelete) {
        setError("Explicit destructive confirmation is required for delete_permanent.");
        return;
      }

      const hardDeleteConfirmed = window.confirm(
        `Permanently delete ${batch.stats?.total ?? 0} file(s)? ` +
          "This action is irreversible.",
      );
      if (!hardDeleteConfirmed) {
        return;
      }
    }

    try {
      await confirmActionBatch(batch.batch_id, {
        confirm_delete_permanent: batch.action_type === "delete_permanent",
      });
      await loadBatch(batch.batch_id);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to confirm batch: ${parsed.detail}`);
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
      const parsed = parseApiError(err);
      setError(`Failed to rollback batch: ${parsed.detail}`);
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
              <div
                key={group.id}
                className={`group-row ${selectedGroupId === group.id ? "group-row--active" : ""}`}
                onClick={() => setSelectedGroupId(group.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedGroupId(group.id);
                  }
                }}
              >
                <div>
                  <strong>#{group.id}</strong>
                  <div className="hint">{group.file_count} files</div>
                </div>
                <div className="group-row__meta">
                  <div>{kind === "exact" ? <span>{formatBytes(group.reclaimable_bytes)} reclaimable</span> : null}</div>
                  <div>{kind === "similar" ? <span>{group.algorithm} / t={group.threshold}</span> : null}</div>
                  <label
                    className="group-row__selector"
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={selectedGroupIds.has(group.id)}
                      onChange={(event) => toggleGroupSelection(group.id, event.target.checked)}
                    />
                    <span className="hint">select for batch</span>
                  </label>
                </div>
              </div>
            ))}
          </div>

          {groups.length > 0 ? (
            <div className="warning-box">
              <strong>Batch decision for groups</strong>
              <div className="inline-form">
                <button type="button" className="tiny-button" onClick={selectAllGroups}>
                  Select All Groups
                </button>
                <button type="button" className="tiny-button" onClick={clearGroupSelection}>
                  Clear Selection
                </button>
                <span className="hint">selected: {selectedGroupIds.size}</span>
              </div>
              <div className="inline-form">
                <select
                  aria-label="groups-bulk-decision"
                  value={groupsBulkDecision}
                  onChange={(event) => setGroupsBulkDecision(event.target.value)}
                >
                  {DECISIONS.map((decision) => (
                    <option key={decision} value={decision}>
                      {decision}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => void handleApplyDecisionToSelectedGroups()}
                  disabled={applyingGroupsBulkDecision || selectedGroupIds.size === 0}
                >
                  {applyingGroupsBulkDecision
                    ? "Applying..."
                    : `Apply To Selected Groups (${selectedGroupIds.size})`}
                </button>
              </div>
            </div>
          ) : null}
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

          {groupDetails?.items?.length ? (
            <div className="warning-box">
              <strong>Apply one decision to selected files</strong>
              <div className="inline-form">
                <select
                  aria-label="bulk-decision"
                  value={bulkDecision}
                  onChange={(event) => setBulkDecision(event.target.value)}
                >
                  {DECISIONS.map((decision) => (
                    <option key={decision} value={decision}>
                      {decision}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => void handleApplyDecisionToSelected()}
                  disabled={applyingBulkDecision || selectableFileIds.length === 0}
                >
                  {applyingBulkDecision ? "Applying..." : `Apply To Selected (${selectableFileIds.length})`}
                </button>
              </div>
            </div>
          ) : null}
        </Panel>
      </div>

      <Panel title="Action Center" subtitle="Draft -> confirm -> execute -> rollback">
        <form className="stack" onSubmit={handleCreateBatch}>
          <div className="inline-form">
            <select aria-label="action-type" value={actionType} onChange={(event) => setActionType(event.target.value)}>
              <option value="move_to_trash">move_to_trash</option>
              <option value="delete_permanent">delete_permanent</option>
              <option value="restore">restore</option>
            </select>
            <select aria-label="bulk-scope" value={selectionScope} onChange={(event) => setSelectionScope(event.target.value)}>
              {BULK_SCOPES.map((scope) => (
                <option key={scope.value} value={scope.value}>
                  {scope.label}
                </option>
              ))}
            </select>
            <span className="hint">selected groups: {selectedGroupIds.size}</span>
            <button type="button" className="button button--ghost" onClick={handlePreviewBatch} disabled={previewLoading}>
              {previewLoading ? "Previewing..." : "Preview Impact"}
            </button>
            <button type="submit" className="button" disabled={!preview || preview.files_count === 0}>
              Create Draft Batch ({preview?.files_count ?? 0})
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

          {preview ? (
            <div className="warning-box" data-testid="action-preview-card">
              <strong>Preview</strong>
              <div className="hint">
                scope={preview.selection_scope}, action={preview.action_type}
              </div>
              <div className="metric-grid">
                <div>
                  <span className="hint">Files</span>
                  <div>{preview.files_count}</div>
                </div>
                <div>
                  <span className="hint">Total size</span>
                  <div>{formatBytes(preview.total_bytes)}</div>
                </div>
                <div>
                  <span className="hint">Estimated reclaimable</span>
                  <div>{formatBytes(preview.estimated_reclaimable_bytes)}</div>
                </div>
              </div>
            </div>
          ) : (
            <p className="hint">Run preview before creating a draft batch.</p>
          )}

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
                <div>
                  <span className="hint">Skipped</span>
                  <div>{batch.stats?.skipped ?? 0}</div>
                </div>
                <div>
                  <span className="hint">Pending</span>
                  <div>{batch.stats?.pending ?? 0}</div>
                </div>
              </div>

              <div className="inline-actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => void handleConfirmBatch()}
                  disabled={
                    batch.status !== "draft" || (batch.action_type === "delete_permanent" && !confirmHardDelete)
                  }
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
                  disabled={
                    batch.action_type !== "move_to_trash" ||
                    !batch.status ||
                    !["executed", "partially_failed"].includes(batch.status)
                  }
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
