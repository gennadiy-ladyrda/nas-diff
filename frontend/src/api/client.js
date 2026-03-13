const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json") ?? false;
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const detail = payload?.detail || response.statusText || "Request failed";
    throw new Error(`${response.status}: ${detail}`);
  }

  return payload;
}

export function getHealth() {
  return request("/health");
}

export function listScanRoots() {
  return request("/scan/roots");
}

export function createScanRoot(path) {
  return request("/scan/roots", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function updateScanRoot(rootId, enabled) {
  return request(`/scan/roots/${rootId}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}

export function createScanJob(payload) {
  return request("/scan/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getScanJob(jobId) {
  return request(`/scan/jobs/${jobId}`);
}

export function getScanJobGroups(jobId, kind, page = 1, pageSize = 50) {
  const params = new URLSearchParams({ kind, page: String(page), page_size: String(pageSize) });
  return request(`/scan/jobs/${jobId}/groups?${params.toString()}`);
}

export function getGroupDetails(kind, groupId) {
  return request(`/groups/${kind}/${groupId}`);
}

export function saveGroupDecision(kind, groupId, payload) {
  return request(`/groups/${kind}/${groupId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createActionBatch(payload) {
  return request("/actions/batches", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getActionBatch(batchId) {
  return request(`/actions/batches/${batchId}`);
}

export function confirmActionBatch(batchId, payload = {}) {
  return request(`/actions/batches/${batchId}/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function rollbackActionBatch(batchId, payload = { requested_by: "local_admin" }) {
  return request(`/actions/batches/${batchId}/rollback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
