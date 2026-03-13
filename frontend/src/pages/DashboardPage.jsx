import { useEffect, useMemo, useState } from "react";

import {
  createScanJob,
  createScanRoot,
  getHealth,
  getScanJob,
  listScanRoots,
  updateScanRoot,
} from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { usePolling } from "../hooks/usePolling";
import { formatBytes, formatTimestamp } from "../utils/format";

const SCAN_MODES = [
  { value: "exact", label: "Exact" },
  { value: "similar", label: "Similar" },
  { value: "both", label: "Both" },
];

export function DashboardPage({ activeJobId, recentJobIds, onSelectJob, onJobCreated }) {
  const [health, setHealth] = useState(null);
  const [roots, setRoots] = useState([]);
  const [selectedRoots, setSelectedRoots] = useState(new Set());
  const [mode, setMode] = useState("both");
  const [newRootPath, setNewRootPath] = useState("");
  const [jobStatus, setJobStatus] = useState(null);
  const [manualJobId, setManualJobId] = useState(activeJobId || "");
  const [error, setError] = useState("");
  const [loadingRoots, setLoadingRoots] = useState(false);
  const [submittingJob, setSubmittingJob] = useState(false);

  const selectedRootIds = useMemo(() => Array.from(selectedRoots), [selectedRoots]);

  async function loadHealth() {
    try {
      setHealth(await getHealth());
    } catch (err) {
      setError(`Health check failed: ${err.message}`);
    }
  }

  async function loadRoots() {
    setLoadingRoots(true);
    try {
      const payload = await listScanRoots();
      setRoots(payload);
      setSelectedRoots((prev) => {
        if (prev.size > 0) {
          return new Set([...prev].filter((rootId) => payload.some((root) => root.id === rootId && root.enabled)));
        }
        return new Set(payload.filter((root) => root.enabled).map((root) => root.id));
      });
    } catch (err) {
      setError(`Failed to load scan roots: ${err.message}`);
    } finally {
      setLoadingRoots(false);
    }
  }

  async function loadJob(jobId) {
    if (!jobId) {
      return;
    }
    try {
      const payload = await getScanJob(jobId);
      setJobStatus(payload);
    } catch (err) {
      setError(`Failed to load job ${jobId}: ${err.message}`);
    }
  }

  useEffect(() => {
    void loadHealth();
    void loadRoots();
  }, []);

  useEffect(() => {
    setManualJobId(activeJobId || "");
    if (activeJobId) {
      void loadJob(activeJobId);
    }
  }, [activeJobId]);

  usePolling(
    () => {
      if (activeJobId) {
        void loadJob(activeJobId);
      }
    },
    2500,
    Boolean(activeJobId && jobStatus && ["queued", "running"].includes(jobStatus.status)),
  );

  async function handleCreateRoot(event) {
    event.preventDefault();
    if (!newRootPath.trim()) {
      return;
    }

    try {
      const created = await createScanRoot(newRootPath.trim());
      setNewRootPath("");
      setRoots((prev) => [...prev, created].sort((a, b) => a.id - b.id));
      setSelectedRoots((prev) => new Set(prev).add(created.id));
    } catch (err) {
      setError(`Failed to add scan root: ${err.message}`);
    }
  }

  async function handleRootEnabled(rootId, enabled) {
    try {
      const updated = await updateScanRoot(rootId, enabled);
      setRoots((prev) => prev.map((root) => (root.id === rootId ? updated : root)));
      setSelectedRoots((prev) => {
        const next = new Set(prev);
        if (!enabled) {
          next.delete(rootId);
        }
        return next;
      });
    } catch (err) {
      setError(`Failed to update root ${rootId}: ${err.message}`);
    }
  }

  function handleRootSelection(rootId, checked) {
    setSelectedRoots((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(rootId);
      } else {
        next.delete(rootId);
      }
      return next;
    });
  }

  async function handleStartScan(event) {
    event.preventDefault();
    setSubmittingJob(true);

    try {
      const payload = await createScanJob({ mode, root_ids: selectedRootIds });
      setJobStatus(null);
      onJobCreated(payload.job_id);
      await loadJob(payload.job_id);
    } catch (err) {
      setError(`Failed to start scan: ${err.message}`);
    } finally {
      setSubmittingJob(false);
    }
  }

  async function handleLoadManualJob(event) {
    event.preventDefault();
    if (!manualJobId.trim()) {
      return;
    }

    onSelectJob(manualJobId.trim());
    await loadJob(manualJobId.trim());
  }

  return (
    <div className="page-grid">
      <ErrorBanner message={error} onDismiss={() => setError("")} />

      <Panel
        title="System Health"
        subtitle="API + Redis + SQLite readiness"
        actions={
          <button type="button" className="button button--ghost" onClick={() => void loadHealth()}>
            Refresh
          </button>
        }
      >
        {health ? (
          <div className="health-grid" data-testid="health-grid">
            <div>
              <span className="hint">Service</span>
              <div>{health.service}</div>
            </div>
            <div>
              <span className="hint">Version</span>
              <div>{health.version}</div>
            </div>
            <div>
              <span className="hint">Overall</span>
              <StatusBadge value={health.status} />
            </div>
            {Object.entries(health.components || {}).map(([key, component]) => (
              <div key={key}>
                <span className="hint">{key}</span>
                <StatusBadge value={component.status} />
              </div>
            ))}
          </div>
        ) : (
          <p>Loading health...</p>
        )}
      </Panel>

      <Panel title="Scan Setup" subtitle="Choose mode and roots, then launch a scan job">
        <form className="stack" onSubmit={handleStartScan}>
          <label className="field">
            <span>Scan mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              {SCAN_MODES.map((scanMode) => (
                <option key={scanMode.value} value={scanMode.value}>
                  {scanMode.label}
                </option>
              ))}
            </select>
          </label>

          <div className="field">
            <span>Selected roots</span>
            {loadingRoots ? <p>Loading roots...</p> : null}
            <div className="root-list" data-testid="scan-roots-list">
              {roots.length === 0 ? <p className="hint">No roots configured yet.</p> : null}
              {roots.map((root) => (
                <div className="root-item" key={root.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedRoots.has(root.id)}
                      disabled={!root.enabled}
                      onChange={(event) => handleRootSelection(root.id, event.target.checked)}
                    />
                    <span>{root.path}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={root.enabled}
                      onChange={(event) => void handleRootEnabled(root.id, event.target.checked)}
                    />
                    <span>enabled</span>
                  </label>
                </div>
              ))}
            </div>
          </div>

          <div className="inline-actions">
            <button type="submit" className="button" disabled={selectedRootIds.length === 0 || submittingJob}>
              {submittingJob ? "Starting..." : "Start Scan"}
            </button>
            <span className="hint">Default-safe action policy remains `move_to_trash`.</span>
          </div>
        </form>
      </Panel>

      <Panel title="Scan Roots" subtitle="Add paths under /nas and toggle their availability">
        <form className="inline-form" onSubmit={handleCreateRoot}>
          <input
            type="text"
            placeholder="/nas/photo/family"
            value={newRootPath}
            onChange={(event) => setNewRootPath(event.target.value)}
          />
          <button type="submit" className="button button--ghost">
            Add Root
          </button>
        </form>
      </Panel>

      <Panel title="Current Job" subtitle="Track queue/running state and resulting metrics">
        <form className="inline-form" onSubmit={handleLoadManualJob}>
          <input
            type="text"
            value={manualJobId}
            onChange={(event) => setManualJobId(event.target.value)}
            placeholder="Paste scan job id"
          />
          <button type="submit" className="button button--ghost">
            Load Job
          </button>
        </form>

        {recentJobIds.length > 0 ? (
          <div className="chip-row">
            {recentJobIds.map((jobId) => (
              <button key={jobId} type="button" className="chip" onClick={() => onSelectJob(jobId)}>
                {jobId.slice(0, 12)}...
              </button>
            ))}
          </div>
        ) : null}

        {jobStatus ? (
          <div className="job-card" data-testid="scan-job-card">
            <div className="job-card__header">
              <code>{jobStatus.job_id}</code>
              <StatusBadge value={jobStatus.status} />
            </div>
            <div className="metric-grid">
              <div>
                <span className="hint">Mode</span>
                <div>{jobStatus.mode}</div>
              </div>
              <div>
                <span className="hint">Requested</span>
                <div>{formatTimestamp(jobStatus.requested_at)}</div>
              </div>
              <div>
                <span className="hint">Started</span>
                <div>{formatTimestamp(jobStatus.started_at)}</div>
              </div>
              <div>
                <span className="hint">Finished</span>
                <div>{formatTimestamp(jobStatus.finished_at)}</div>
              </div>
              <div>
                <span className="hint">Files seen</span>
                <div>{jobStatus.files_seen}</div>
              </div>
              <div>
                <span className="hint">Files indexed</span>
                <div>{jobStatus.files_indexed}</div>
              </div>
              <div>
                <span className="hint">Exact groups</span>
                <div>{jobStatus.exact_groups_found}</div>
              </div>
              <div>
                <span className="hint">Similar groups</span>
                <div>{jobStatus.similar_groups_found}</div>
              </div>
              <div>
                <span className="hint">Reclaimable</span>
                <div>{formatBytes(jobStatus.reclaimable_bytes)}</div>
              </div>
            </div>
            {jobStatus.error_message ? <p className="error-text">{jobStatus.error_message}</p> : null}
          </div>
        ) : (
          <p className="hint">No job selected.</p>
        )}
      </Panel>
    </div>
  );
}
