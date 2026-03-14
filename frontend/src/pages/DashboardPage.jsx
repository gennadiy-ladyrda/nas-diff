import { useEffect, useMemo, useRef, useState } from "react";

import {
  createScanJob,
  createScanRoot,
  deleteScanJob,
  deleteScanRoot,
  getHealth,
  getScanJob,
  listScanJobs,
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

const JOB_STATUS_FILTERS = ["all", "queued", "running", "completed", "failed", "canceled"];
const JOB_MODE_FILTERS = ["all", "exact", "similar", "both"];
const JOB_PAGE_SIZE = 20;

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

function toModeToken(mode) {
  const normalized = (mode || "unknown").toUpperCase();
  if (normalized === "BOTH") {
    return "BOTH";
  }
  if (normalized === "EXACT") {
    return "EXACT";
  }
  if (normalized === "SIMILAR") {
    return "SIMILAR";
  }
  return normalized;
}

function calculateSequence(index, page, pageSize, total, order) {
  const offset = (page - 1) * pageSize + index;
  if (order === "asc") {
    return offset + 1;
  }
  return Math.max(total - offset, 1);
}

function isActiveJobStatus(status) {
  return status === "queued" || status === "running";
}

function calculateJobProgressPercent(job) {
  if (!job) {
    return 0;
  }
  if (job.status === "completed") {
    return 100;
  }
  const filesSeen = Number(job.files_seen || 0);
  const filesIndexed = Number(job.files_indexed || 0);
  if (filesSeen <= 0 && filesIndexed <= 0) {
    return 0;
  }
  const denominator = Math.max(filesSeen, filesIndexed, 1);
  return Math.max(0, Math.min(100, Math.round((filesIndexed / denominator) * 100)));
}

function progressFillClass(status) {
  if (status === "completed") {
    return "jobs-progress__fill jobs-progress__fill--done";
  }
  if (status === "failed" || status === "canceled") {
    return "jobs-progress__fill jobs-progress__fill--failed";
  }
  return "jobs-progress__fill jobs-progress__fill--active";
}

function mergeJobRuntime(job, payload) {
  if (!payload || payload.job_id !== job.job_id) {
    return job;
  }

  const hasChanged =
    job.status !== payload.status ||
    job.started_at !== payload.started_at ||
    job.finished_at !== payload.finished_at ||
    job.error_message !== payload.error_message ||
    job.files_seen !== payload.files_seen ||
    job.files_indexed !== payload.files_indexed ||
    job.exact_groups_found !== payload.exact_groups_found ||
    job.similar_groups_found !== payload.similar_groups_found ||
    job.reclaimable_bytes !== payload.reclaimable_bytes;

  if (!hasChanged) {
    return job;
  }

  return {
    ...job,
    status: payload.status,
    started_at: payload.started_at,
    finished_at: payload.finished_at,
    error_message: payload.error_message,
    files_seen: payload.files_seen,
    files_indexed: payload.files_indexed,
    exact_groups_found: payload.exact_groups_found,
    similar_groups_found: payload.similar_groups_found,
    reclaimable_bytes: payload.reclaimable_bytes,
  };
}

function buildDisplayName(job, sequence = null) {
  if (!job) {
    return { title: "SCAN-UNKNOWN", subtitle: "-" };
  }

  const token = sequence == null ? job.job_id.slice(0, 8).toUpperCase() : String(sequence).padStart(4, "0");
  return {
    title: `SCAN-${toModeToken(job.mode)}-${token}`,
    subtitle: formatTimestamp(job.requested_at),
  };
}

function humanizeRootDeleteError(path, err) {
  const parsed = parseApiError(err);
  if (parsed.status === 409) {
    return `Cannot delete root ${path}: it is still referenced by existing jobs.`;
  }
  if (parsed.status === 422) {
    return `Cannot delete root ${path}: request was rejected by validation rules.`;
  }
  return `Failed to delete root ${path}: ${parsed.detail}`;
}

function humanizeJobDeleteError(jobId, err) {
  const parsed = parseApiError(err);
  if (parsed.status === 409) {
    if (parsed.detail.includes("allow_stale_running=true")) {
      return (
        `Cannot delete active job ${jobId} yet. ` +
        "If the job is stale, repeat delete and confirm stale cleanup."
      );
    }
    return `Cannot delete job ${jobId}: ${parsed.detail}`;
  }
  if (parsed.status === 404) {
    return `Cannot delete job ${jobId}: job was already removed.`;
  }
  return `Failed to delete job ${jobId}: ${parsed.detail}`;
}

export function DashboardPage({ activeJobId, recentJobIds, onSelectJob, onJobCreated, onJobDeleted = () => {} }) {
  const [health, setHealth] = useState(null);
  const [roots, setRoots] = useState([]);
  const [selectedRoots, setSelectedRoots] = useState(new Set());
  const [mode, setMode] = useState("both");
  const [newRootPath, setNewRootPath] = useState("");

  const [jobs, setJobs] = useState([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsStatusFilter, setJobsStatusFilter] = useState("all");
  const [jobsModeFilter, setJobsModeFilter] = useState("all");
  const [jobsOrder, setJobsOrder] = useState("desc");

  const [jobStatus, setJobStatus] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(activeJobId || "");
  const [manualJobId, setManualJobId] = useState(activeJobId || "");

  const [error, setError] = useState("");
  const [loadingRoots, setLoadingRoots] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [submittingJob, setSubmittingJob] = useState(false);
  const [deletingRootId, setDeletingRootId] = useState(0);
  const [deletingJobId, setDeletingJobId] = useState("");
  const pollingInFlightRef = useRef(false);

  const selectedRootIds = useMemo(() => Array.from(selectedRoots).sort((a, b) => a - b), [selectedRoots]);
  const totalJobPages = Math.max(1, Math.ceil(jobsTotal / JOB_PAGE_SIZE));
  const hasActiveJobs = useMemo(() => {
    if (jobs.some((job) => isActiveJobStatus(job.status))) {
      return true;
    }
    return Boolean(selectedJobId && isActiveJobStatus(jobStatus?.status));
  }, [jobs, selectedJobId, jobStatus]);

  const selectedJobContext = useMemo(() => {
    const selectedIndex = jobs.findIndex((job) => job.job_id === selectedJobId);
    if (selectedIndex < 0) {
      return buildDisplayName(jobStatus);
    }

    const selectedJob = jobs[selectedIndex];
    const sequence = calculateSequence(selectedIndex, jobsPage, JOB_PAGE_SIZE, jobsTotal, jobsOrder);
    return buildDisplayName(selectedJob, sequence);
  }, [jobStatus, jobs, jobsOrder, jobsPage, jobsTotal, selectedJobId]);

  async function loadHealth() {
    try {
      setHealth(await getHealth());
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Health check failed: ${parsed.detail}`);
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
      const parsed = parseApiError(err);
      setError(`Failed to load scan roots: ${parsed.detail}`);
    } finally {
      setLoadingRoots(false);
    }
  }

  async function loadJobs({ showLoading = true } = {}) {
    if (showLoading) {
      setLoadingJobs(true);
    }
    try {
      const payload = await listScanJobs({
        status: jobsStatusFilter,
        mode: jobsModeFilter,
        order: jobsOrder,
        page: jobsPage,
        pageSize: JOB_PAGE_SIZE,
      });

      setJobs(payload.items || []);
      setJobsTotal(payload.total || 0);

      const resolvedTotalPages = Math.max(1, Math.ceil((payload.total || 0) / JOB_PAGE_SIZE));
      if (jobsPage > resolvedTotalPages) {
        setJobsPage(resolvedTotalPages);
      }
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to load scan jobs: ${parsed.detail}`);
    } finally {
      if (showLoading) {
        setLoadingJobs(false);
      }
    }
  }

  async function loadJob(jobId) {
    if (!jobId) {
      return;
    }

    try {
      const payload = await getScanJob(jobId);
      setJobStatus(payload);
      setJobs((prev) => prev.map((job) => mergeJobRuntime(job, payload)));
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to load job ${jobId}: ${parsed.detail}`);
      setJobStatus(null);
    }
  }

  useEffect(() => {
    void loadHealth();
    void loadRoots();
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [jobsPage, jobsStatusFilter, jobsModeFilter, jobsOrder]);

  useEffect(() => {
    setManualJobId(activeJobId || "");
    if (!activeJobId) {
      return;
    }

    setSelectedJobId(activeJobId);
    void loadJob(activeJobId);
  }, [activeJobId]);

  usePolling(
    () => {
      if (pollingInFlightRef.current) {
        return;
      }

      const activeJobIds = [];
      const seen = new Set();
      for (const job of jobs) {
        if (isActiveJobStatus(job.status) && !seen.has(job.job_id)) {
          activeJobIds.push(job.job_id);
          seen.add(job.job_id);
        }
      }

      if (selectedJobId && isActiveJobStatus(jobStatus?.status) && !seen.has(selectedJobId)) {
        activeJobIds.push(selectedJobId);
      }

      if (activeJobIds.length === 0) {
        return;
      }

      pollingInFlightRef.current = true;
      void Promise.all(
        activeJobIds.map(async (jobId) => {
          try {
            return await getScanJob(jobId);
          } catch {
            return null;
          }
        }),
      )
        .then((payloads) => {
          const validPayloads = payloads.filter((payload) => payload !== null);
          if (validPayloads.length === 0) {
            return;
          }

          const payloadByJobId = new Map(validPayloads.map((payload) => [payload.job_id, payload]));
          setJobs((prev) => {
            let changed = false;
            const next = prev.map((job) => {
              const merged = mergeJobRuntime(job, payloadByJobId.get(job.job_id));
              if (merged !== job) {
                changed = true;
              }
              return merged;
            });
            return changed ? next : prev;
          });

          if (selectedJobId) {
            const selectedPayload = payloadByJobId.get(selectedJobId);
            if (selectedPayload) {
              setJobStatus((prev) => {
                if (!prev) {
                  return selectedPayload;
                }
                if (
                  prev.status === selectedPayload.status &&
                  prev.started_at === selectedPayload.started_at &&
                  prev.finished_at === selectedPayload.finished_at &&
                  prev.error_message === selectedPayload.error_message &&
                  prev.files_seen === selectedPayload.files_seen &&
                  prev.files_indexed === selectedPayload.files_indexed &&
                  prev.exact_groups_found === selectedPayload.exact_groups_found &&
                  prev.similar_groups_found === selectedPayload.similar_groups_found &&
                  prev.reclaimable_bytes === selectedPayload.reclaimable_bytes
                ) {
                  return prev;
                }
                return selectedPayload;
              });
            }
          }
        })
        .finally(() => {
          pollingInFlightRef.current = false;
        });
    },
    2500,
    hasActiveJobs,
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
      const parsed = parseApiError(err);
      setError(`Failed to add scan root: ${parsed.detail}`);
    }
  }

  async function handleDeleteRoot(root) {
    const confirmed = window.confirm(`Delete scan root ${root.path}? This removes only metadata, not NAS files.`);
    if (!confirmed) {
      return;
    }

    setDeletingRootId(root.id);
    try {
      await deleteScanRoot(root.id);
      setRoots((prev) => prev.filter((item) => item.id !== root.id));
      setSelectedRoots((prev) => {
        const next = new Set(prev);
        next.delete(root.id);
        return next;
      });
    } catch (err) {
      setError(humanizeRootDeleteError(root.path, err));
    } finally {
      setDeletingRootId(0);
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
      const parsed = parseApiError(err);
      setError(`Failed to update root ${rootId}: ${parsed.detail}`);
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
      onJobCreated(payload.job_id);
      setSelectedJobId(payload.job_id);
      setManualJobId(payload.job_id);
      await Promise.all([loadJob(payload.job_id), loadJobs({ showLoading: false })]);
    } catch (err) {
      const parsed = parseApiError(err);
      setError(`Failed to start scan: ${parsed.detail}`);
    } finally {
      setSubmittingJob(false);
    }
  }

  function handleSelectJob(jobId) {
    if (!jobId) {
      return;
    }

    setSelectedJobId(jobId);
    setManualJobId(jobId);
    onSelectJob(jobId);
    void loadJob(jobId);
  }

  async function handleLoadManualJob(event) {
    event.preventDefault();
    if (!manualJobId.trim()) {
      return;
    }

    const nextJobId = manualJobId.trim();
    handleSelectJob(nextJobId);
  }

  async function handleDeleteJob(job, sequence = null) {
    const targetJobId = job?.job_id || selectedJobId;
    if (!targetJobId) {
      return;
    }

    const display = buildDisplayName(job || jobStatus, sequence);
    const confirmed = window.confirm(
      `Delete job metadata ${display.title} (${targetJobId})? This does not modify NAS files.`,
    );
    if (!confirmed) {
      return;
    }

    setDeletingJobId(targetJobId);
    try {
      await deleteScanJob(targetJobId);
      onJobDeleted(targetJobId);

      if (selectedJobId === targetJobId) {
        setSelectedJobId("");
        setManualJobId("");
        setJobStatus(null);
      }

      await loadJobs({ showLoading: false });
    } catch (err) {
      const parsed = parseApiError(err);
      const currentStatus = job?.status || jobStatus?.status || jobs.find((item) => item.job_id === targetJobId)?.status;
      if (parsed.status === 409 && isActiveJobStatus(currentStatus)) {
        const confirmedStaleDelete = window.confirm(
          `Job ${targetJobId} is still ${currentStatus}. ` +
            "Delete stale metadata if this job is orphaned and older than timeout?",
        );
        if (!confirmedStaleDelete) {
          return;
        }

        try {
          await deleteScanJob(targetJobId, { allowStaleRunning: true });
          onJobDeleted(targetJobId);
          if (selectedJobId === targetJobId) {
            setSelectedJobId("");
            setManualJobId("");
            setJobStatus(null);
          }
          await loadJobs({ showLoading: false });
        } catch (forceDeleteErr) {
          setError(humanizeJobDeleteError(targetJobId, forceDeleteErr));
        }
        return;
      }

      setError(humanizeJobDeleteError(targetJobId, err));
    } finally {
      setDeletingJobId("");
    }
  }

  return (
    <div className="dashboard-layout">
      <ErrorBanner message={error} onDismiss={() => setError("")} />

      <aside className="dashboard-health-column">
        <Panel
          title="System Health"
          subtitle="Compact runtime status"
          actions={
            <button type="button" className="button button--ghost" onClick={() => void loadHealth()}>
              Refresh
            </button>
          }
        >
          {health ? (
            <div className="health-stack" data-testid="health-grid">
              <div className="health-item">
                <span className="hint">Service</span>
                <strong>{health.service}</strong>
              </div>
              <div className="health-item">
                <span className="hint">Version</span>
                <strong>{health.version}</strong>
              </div>
              <div className="health-item">
                <span className="hint">Overall</span>
                <StatusBadge value={health.status} />
              </div>
              {Object.entries(health.components || {}).map(([key, component]) => (
                <div key={key} className="health-item">
                  <span className="hint">{key}</span>
                  <StatusBadge value={component.status} />
                </div>
              ))}
            </div>
          ) : (
            <p>Loading health...</p>
          )}
        </Panel>
      </aside>

      <div className="dashboard-main-column">
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
                    <label className="root-select">
                      <input
                        type="checkbox"
                        checked={selectedRoots.has(root.id)}
                        disabled={!root.enabled}
                        onChange={(event) => handleRootSelection(root.id, event.target.checked)}
                      />
                      <span>{root.path}</span>
                    </label>
                    <StatusBadge value={root.enabled ? "ok" : "canceled"} />
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

        <Panel title="Scan Roots Registry" subtitle="Add, toggle, and remove roots with explicit confirmation">
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

          <div className="root-list root-list--registry">
            {roots.map((root) => (
              <div className="root-item root-item--registry" key={root.id}>
                <div className="root-item__main">
                  <strong>{root.path}</strong>
                  <span className="hint">root_id={root.id}</span>
                </div>
                <div className="root-item__actions">
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={root.enabled}
                      onChange={(event) => void handleRootEnabled(root.id, event.target.checked)}
                    />
                    <span>enabled</span>
                  </label>
                  <button
                    type="button"
                    className="tiny-button tiny-button--danger"
                    onClick={() => void handleDeleteRoot(root)}
                    disabled={deletingRootId === root.id}
                  >
                    {deletingRootId === root.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Scan Jobs Journal" subtitle="Filter jobs, open detail panel, and delete obsolete metadata">
          <div className="jobs-toolbar">
            <label className="field-inline">
              <span className="hint">status</span>
              <select
                value={jobsStatusFilter}
                onChange={(event) => {
                  setJobsPage(1);
                  setJobsStatusFilter(event.target.value);
                }}
              >
                {JOB_STATUS_FILTERS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className="field-inline">
              <span className="hint">mode</span>
              <select
                value={jobsModeFilter}
                onChange={(event) => {
                  setJobsPage(1);
                  setJobsModeFilter(event.target.value);
                }}
              >
                {JOB_MODE_FILTERS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className="field-inline">
              <span className="hint">order</span>
              <select
                value={jobsOrder}
                onChange={(event) => {
                  setJobsPage(1);
                  setJobsOrder(event.target.value);
                }}
              >
                <option value="desc">newest first</option>
                <option value="asc">oldest first</option>
              </select>
            </label>

            <button type="button" className="button button--ghost" onClick={() => void loadJobs()}>
              Refresh
            </button>

            <span className="hint jobs-toolbar__summary">
              page {jobsPage}/{totalJobPages}, total jobs: {jobsTotal}
            </span>
          </div>

          <div className="table-wrap">
            <table data-testid="jobs-table">
              <thead>
                <tr>
                  <th>Display name</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Requested</th>
                  <th>Finished</th>
                  <th>Files</th>
                  <th>Groups</th>
                  <th>Reclaimable</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loadingJobs ? (
                  <tr>
                    <td colSpan={9}>Loading jobs...</td>
                  </tr>
                ) : null}

                {!loadingJobs && jobs.length === 0 ? (
                  <tr>
                    <td colSpan={9}>No jobs for current filters.</td>
                  </tr>
                ) : null}

                {!loadingJobs
                  ? jobs.map((job, index) => {
                      const sequence = calculateSequence(index, jobsPage, JOB_PAGE_SIZE, jobsTotal, jobsOrder);
                      const display = buildDisplayName(job, sequence);
                      const isActive = selectedJobId === job.job_id;
                      const progressPercent = calculateJobProgressPercent(job);

                      return (
                        <tr
                          key={job.job_id}
                          className={isActive ? "jobs-row jobs-row--active" : "jobs-row"}
                          onClick={() => handleSelectJob(job.job_id)}
                        >
                          <td>
                            <div className="jobs-name">
                              <strong>{display.title}</strong>
                              <span className="hint">{display.subtitle}</span>
                              <code>{job.job_id}</code>
                            </div>
                          </td>
                          <td>
                            <StatusBadge value={job.status} />
                            <div className="hint">mode={job.mode}</div>
                          </td>
                          <td>
                            <div className="jobs-progress" data-testid={`job-progress-${job.job_id}`}>
                              <div className="jobs-progress__track">
                                <div
                                  className={progressFillClass(job.status)}
                                  style={{ width: `${progressPercent}%` }}
                                />
                              </div>
                              <span className="hint">{progressPercent}%</span>
                            </div>
                          </td>
                          <td>{formatTimestamp(job.requested_at)}</td>
                          <td>{formatTimestamp(job.finished_at)}</td>
                          <td>
                            {job.files_seen}/{job.files_indexed}
                          </td>
                          <td>
                            {job.exact_groups_found}/{job.similar_groups_found}
                          </td>
                          <td>{formatBytes(job.reclaimable_bytes)}</td>
                          <td>
                            <button
                              type="button"
                              className="tiny-button tiny-button--danger"
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleDeleteJob(job, sequence);
                              }}
                              disabled={deletingJobId === job.job_id}
                            >
                              {deletingJobId === job.job_id ? "Deleting..." : "Delete"}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  : null}
              </tbody>
            </table>
          </div>

          <div className="jobs-pagination">
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setJobsPage((prev) => Math.max(1, prev - 1))}
              disabled={jobsPage <= 1}
            >
              Previous page
            </button>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setJobsPage((prev) => Math.min(totalJobPages, prev + 1))}
              disabled={jobsPage >= totalJobPages}
            >
              Next page
            </button>
          </div>

          <form className="inline-form" onSubmit={handleLoadManualJob}>
            <input
              type="text"
              value={manualJobId}
              onChange={(event) => setManualJobId(event.target.value)}
              placeholder="Paste scan job id"
            />
            <button type="submit" className="button button--ghost">
              Open Job By ID
            </button>
          </form>

          {recentJobIds.length > 0 ? (
            <div className="chip-row">
              {recentJobIds.map((jobId) => (
                <button key={jobId} type="button" className="chip" onClick={() => handleSelectJob(jobId)}>
                  {jobId.slice(0, 12)}...
                </button>
              ))}
            </div>
          ) : null}

          <div className="job-card" data-testid="job-detail-panel">
            {jobStatus ? (
              <>
                <div className="job-card__header">
                  <div>
                    <strong>{selectedJobContext.title}</strong>
                    <div className="hint">{selectedJobContext.subtitle}</div>
                    <code>{jobStatus.job_id}</code>
                  </div>
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

                {jobStatus.roots?.length ? (
                  <div className="field">
                    <span className="hint">Attached roots</span>
                    <div className="root-list">
                      {jobStatus.roots.map((root) => (
                        <div key={root.id} className="root-item">
                          <span>{root.path}</span>
                          <StatusBadge value={root.enabled ? "ok" : "canceled"} />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {jobStatus.error_message ? <p className="error-text">{jobStatus.error_message}</p> : null}

                <div className="inline-actions">
                  <button type="button" className="button button--ghost" onClick={() => void loadJob(jobStatus.job_id)}>
                    Refresh details
                  </button>
                  <button
                    type="button"
                    className="tiny-button tiny-button--danger"
                    onClick={() => void handleDeleteJob(jobStatus)}
                    disabled={deletingJobId === jobStatus.job_id}
                  >
                    {deletingJobId === jobStatus.job_id ? "Deleting..." : "Delete job metadata"}
                  </button>
                </div>
              </>
            ) : (
              <p className="hint">Pick a job from the table or open it by id.</p>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
