import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DashboardPage } from "../../src/pages/DashboardPage";

function jsonResponse(data, status = 200) {
  return new Response(data == null ? null : JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("DashboardPage", () => {
  it("starts scan, updates jobs table, and renders detail panel", async () => {
    const onJobCreated = vi.fn();
    const onSelectJob = vi.fn();

    let jobs = [];

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/health") && method === "GET") {
        return jsonResponse({
          service: "nas-diff",
          version: "0.1.0",
          status: "ok",
          components: {
            api: { status: "ok" },
            database: { status: "ok" },
            redis: { status: "ok" },
          },
        });
      }

      if (url.endsWith("/api/v1/scan/roots") && method === "GET") {
        return jsonResponse([
          { id: 1, path: "/nas/photo", enabled: true },
          { id: 2, path: "/nas/archive", enabled: true },
        ]);
      }

      if (url.includes("/api/v1/scan/jobs?") && method === "GET") {
        return jsonResponse({
          page: 1,
          page_size: 20,
          total: jobs.length,
          items: jobs,
        });
      }

      if (url.endsWith("/api/v1/scan/jobs") && method === "POST") {
        jobs = [
          {
            job_id: "job-001",
            mode: "both",
            status: "completed",
            requested_at: "2026-03-14T00:00:00",
            started_at: "2026-03-14T00:00:01",
            finished_at: "2026-03-14T00:00:10",
            error_message: null,
            files_seen: 3,
            files_indexed: 3,
            exact_groups_found: 1,
            similar_groups_found: 1,
            reclaimable_bytes: 1024,
          },
        ];

        return jsonResponse({ job_id: "job-001", status: "queued", mode: "both", root_ids: [1], queued: true }, 201);
      }

      if (url.endsWith("/api/v1/scan/jobs/job-001") && method === "GET") {
        return jsonResponse({
          job_id: "job-001",
          mode: "both",
          status: "completed",
          requested_at: "2026-03-14T00:00:00",
          started_at: "2026-03-14T00:00:01",
          finished_at: "2026-03-14T00:00:10",
          error_message: null,
          files_seen: 3,
          files_indexed: 3,
          exact_groups_found: 1,
          similar_groups_found: 1,
          reclaimable_bytes: 1024,
          roots: [{ id: 1, path: "/nas/photo", enabled: true }],
        });
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        activeJobId=""
        recentJobIds={[]}
        onSelectJob={onSelectJob}
        onJobCreated={onJobCreated}
      />,
    );

    await screen.findByTestId("health-grid");
    await screen.findByTestId("scan-roots-list");

    await userEvent.click(screen.getByRole("button", { name: "Start Scan" }));

    await waitFor(() => {
      expect(onJobCreated).toHaveBeenCalledWith("job-001");
    });

    await waitFor(() => {
      expect(screen.getByTestId("jobs-table")).toHaveTextContent("SCAN-BOTH-0001");
      expect(screen.getByTestId("job-detail-panel")).toHaveTextContent("job-001");
      expect(screen.getByTestId("job-detail-panel")).toHaveTextContent("1.0 KB");
    });
  });

  it("deletes root after explicit confirmation", async () => {
    const onJobCreated = vi.fn();
    const onSelectJob = vi.fn();

    vi.stubGlobal("confirm", vi.fn(() => true));

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/health") && method === "GET") {
        return jsonResponse({
          service: "nas-diff",
          version: "0.1.0",
          status: "ok",
          components: {
            api: { status: "ok" },
            database: { status: "ok" },
            redis: { status: "ok" },
          },
        });
      }

      if (url.endsWith("/api/v1/scan/roots") && method === "GET") {
        return jsonResponse([
          { id: 1, path: "/nas/photo", enabled: true },
          { id: 2, path: "/nas/archive", enabled: true },
        ]);
      }

      if (url.includes("/api/v1/scan/jobs?") && method === "GET") {
        return jsonResponse({ page: 1, page_size: 20, total: 0, items: [] });
      }

      if (url.endsWith("/api/v1/scan/roots/2") && method === "DELETE") {
        return jsonResponse(null, 204);
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        activeJobId=""
        recentJobIds={[]}
        onSelectJob={onSelectJob}
        onJobCreated={onJobCreated}
      />,
    );

    const rootRow = await screen.findByText("/nas/archive");
    const registryRow = rootRow.closest(".root-item--registry");
    expect(registryRow).not.toBeNull();

    await userEvent.click(within(registryRow).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(screen.queryByText("/nas/archive")).not.toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/scan/roots/2"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("retries delete for stale running job with allow_stale_running flag", async () => {
    const confirmMock = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmMock);

    let jobs = [
      {
        job_id: "job-running",
        mode: "both",
        status: "running",
        requested_at: "2026-03-14T00:00:00",
        started_at: "2026-03-14T00:00:01",
        finished_at: null,
        error_message: null,
        files_seen: 4,
        files_indexed: 1,
        exact_groups_found: 0,
        similar_groups_found: 0,
        reclaimable_bytes: 0,
      },
    ];

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/health") && method === "GET") {
        return jsonResponse({
          service: "nas-diff",
          version: "0.1.0",
          status: "ok",
          components: {
            api: { status: "ok" },
            database: { status: "ok" },
            redis: { status: "ok" },
          },
        });
      }

      if (url.endsWith("/api/v1/scan/roots") && method === "GET") {
        return jsonResponse([{ id: 1, path: "/nas/photo", enabled: true }]);
      }

      if (url.includes("/api/v1/scan/jobs?") && method === "GET") {
        return jsonResponse({ page: 1, page_size: 20, total: jobs.length, items: jobs });
      }

      if (url.endsWith("/api/v1/scan/jobs/job-running") && method === "GET") {
        if (!jobs[0]) {
          return jsonResponse({ detail: "scan_job=job-running not found" }, 404);
        }
        return jsonResponse({
          ...jobs[0],
          roots: [{ id: 1, path: "/nas/photo", enabled: true }],
        });
      }

      if (url.endsWith("/api/v1/scan/jobs/job-running") && method === "DELETE") {
        return jsonResponse(
          {
            detail:
              "scan_job=job-running with status='running' cannot be deleted; use allow_stale_running=true only for stale jobs",
          },
          409,
        );
      }

      if (url.includes("/api/v1/scan/jobs/job-running?allow_stale_running=true") && method === "DELETE") {
        jobs = [];
        return jsonResponse(null, 204);
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<DashboardPage activeJobId="" recentJobIds={[]} onSelectJob={vi.fn()} onJobCreated={vi.fn()} />);

    const jobsTable = await screen.findByTestId("jobs-table");
    expect(jobsTable).toHaveTextContent("job-running");

    const row = screen.getByText("job-running").closest("tr");
    expect(row).not.toBeNull();
    await userEvent.click(within(row).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(screen.getByTestId("jobs-table")).not.toHaveTextContent("job-running");
    });

    expect(confirmMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/scan/jobs/job-running"),
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/scan/jobs/job-running?allow_stale_running=true"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("renders simple scan variant with directory input and compact progress", async () => {
    const onJobCreated = vi.fn();
    const onSelectJob = vi.fn();

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/scan/jobs/latest/processed") && method === "GET") {
        return jsonResponse({ detail: "no processed scan jobs found" }, 404);
      }

      if (url.endsWith("/api/v1/scan/roots") && method === "GET") {
        return jsonResponse([]);
      }

      if (url.endsWith("/api/v1/scan/roots") && method === "POST") {
        return jsonResponse({ id: 41, path: "/nas/manual", enabled: true }, 201);
      }

      if (url.endsWith("/api/v1/scan/jobs") && method === "POST") {
        return jsonResponse({ job_id: "simple-job-1", status: "queued", mode: "exact", root_ids: [41], queued: true }, 201);
      }

      if (url.endsWith("/api/v1/scan/jobs/simple-job-1") && method === "GET") {
        return jsonResponse({
          job_id: "simple-job-1",
          mode: "exact",
          status: "running",
          requested_at: "2026-03-15T00:00:00",
          started_at: "2026-03-15T00:00:01",
          finished_at: null,
          error_message: null,
          files_seen: 10,
          files_indexed: 4,
          exact_groups_found: 0,
          similar_groups_found: 0,
          reclaimable_bytes: 0,
          roots: [{ id: 41, path: "/nas/manual", enabled: true }],
        });
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        variant="simple"
        activeJobId=""
        recentJobIds={[]}
        onSelectJob={onSelectJob}
        onJobCreated={onJobCreated}
      />,
    );

    expect(screen.queryByTestId("health-grid")).not.toBeInTheDocument();
    expect(screen.queryByTestId("jobs-table")).not.toBeInTheDocument();
    await screen.findByTestId("simple-scan-progress");

    await userEvent.clear(screen.getByLabelText("Directory path"));
    await userEvent.type(screen.getByLabelText("Directory path"), "/nas/manual");
    await userEvent.click(screen.getByRole("button", { name: "Start Scan" }));

    await waitFor(() => {
      expect(onJobCreated).toHaveBeenCalledWith("simple-job-1");
      expect(screen.getByTestId("simple-scan-progress")).toHaveTextContent("40%");
    });

    expect(JSON.parse(window.localStorage.getItem("nas-diff.simple-scan-defaults"))).toEqual({
      path: "/nas/manual",
      mode: "both",
    });
  });

  it("auto-fills simple scan from the latest processed job", async () => {
    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/scan/jobs/latest/processed") && method === "GET") {
        return jsonResponse({
          job_id: "job-latest",
          mode: "similar",
          status: "completed",
          requested_at: "2026-03-15T10:00:00",
          started_at: "2026-03-15T10:00:05",
          finished_at: "2026-03-15T10:01:05",
          error_message: null,
          files_seen: 12,
          files_indexed: 12,
          exact_groups_found: 1,
          similar_groups_found: 2,
          reclaimable_bytes: 2048,
          roots: [
            { id: 8, path: "/nas/photo/auto", enabled: true },
            { id: 9, path: "/nas/photo/other", enabled: true },
          ],
        });
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        variant="simple"
        activeJobId=""
        recentJobIds={[]}
        onSelectJob={vi.fn()}
        onJobCreated={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Directory path")).toHaveValue("/nas/photo/auto");
      expect(screen.getByLabelText("Scan mode")).toHaveValue("similar");
    });

    expect(screen.getByTestId("simple-defaults-card")).toHaveTextContent("Source: latest processed job");
    expect(screen.getByTestId("simple-defaults-card")).toHaveTextContent(
      "Auto-selected the first root from 2 roots of the latest processed job.",
    );
    expect(screen.getByTestId("simple-defaults-card")).toHaveTextContent("SCAN-SIMILAR-JOB-LATE");
  });

  it("falls back to local simple scan defaults when there is no processed job history", async () => {
    window.localStorage.setItem(
      "nas-diff.simple-scan-defaults",
      JSON.stringify({ path: "/nas/photo/fallback", mode: "exact" }),
    );

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/scan/jobs/latest/processed") && method === "GET") {
        return jsonResponse({ detail: "no processed scan jobs found" }, 404);
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        variant="simple"
        activeJobId=""
        recentJobIds={[]}
        onSelectJob={vi.fn()}
        onJobCreated={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Directory path")).toHaveValue("/nas/photo/fallback");
      expect(screen.getByLabelText("Scan mode")).toHaveValue("exact");
    });

    expect(screen.getByTestId("simple-defaults-card")).toHaveTextContent("Source: local fallback");
  });

  it("runs preview, draft, and confirm flow for the latest processed job action", async () => {
    let confirmPayload = null;

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.endsWith("/api/v1/scan/jobs/latest/processed") && method === "GET") {
        return jsonResponse({
          job_id: "job-latest-action",
          mode: "both",
          status: "completed",
          requested_at: "2026-03-15T10:00:00",
          started_at: "2026-03-15T10:00:05",
          finished_at: "2026-03-15T10:01:05",
          error_message: null,
          files_seen: 20,
          files_indexed: 20,
          exact_groups_found: 2,
          similar_groups_found: 1,
          reclaimable_bytes: 4096,
          roots: [{ id: 5, path: "/nas/photo/auto", enabled: true }],
        });
      }

      if (url.endsWith("/api/v1/actions/jobs/job-latest-action/preview") && method === "POST") {
        return jsonResponse({
          job_id: "job-latest-action",
          action_type: "move_to_trash",
          file_ids: [11, 12],
          files_count: 2,
          total_bytes: 3072,
          estimated_reclaimable_bytes: 3072,
        });
      }

      if (url.endsWith("/api/v1/actions/jobs/job-latest-action/batches") && method === "POST") {
        return jsonResponse(
          {
            batch_id: "simple-batch-1",
            status: "draft",
            action_type: "move_to_trash",
            requested_at: "2026-03-15T10:05:00",
            confirmed_at: null,
            executed_at: null,
            requested_by: "local_admin",
            dry_run: false,
            summary: "scan_job=job-latest-action;scope=all_non_primary_groups",
            stats: { total: 2, pending: 2, done: 0, failed: 0, skipped: 0 },
            items: [
              { id: 1, file_id: 11, source_path: "/nas/photo/1.jpg", target_path: "/trash/1.jpg", status: "pending" },
              { id: 2, file_id: 12, source_path: "/nas/photo/2.jpg", target_path: "/trash/2.jpg", status: "pending" },
            ],
          },
          201,
        );
      }

      if (url.endsWith("/api/v1/actions/batches/simple-batch-1/confirm") && method === "POST") {
        confirmPayload = JSON.parse(options.body);
        return jsonResponse({ batch_id: "simple-batch-1", status: "confirmed", queued: true });
      }

      if (url.endsWith("/api/v1/actions/batches/simple-batch-1") && method === "GET") {
        return jsonResponse({
          batch_id: "simple-batch-1",
          status: "executed",
          action_type: "move_to_trash",
          requested_at: "2026-03-15T10:05:00",
          confirmed_at: "2026-03-15T10:05:30",
          executed_at: "2026-03-15T10:05:50",
          requested_by: "local_admin",
          dry_run: false,
          summary: "scan_job=job-latest-action;scope=all_non_primary_groups",
          stats: { total: 2, pending: 0, done: 2, failed: 0, skipped: 0 },
          items: [
            { id: 1, file_id: 11, source_path: "/nas/photo/1.jpg", target_path: "/trash/1.jpg", status: "done" },
            { id: 2, file_id: 12, source_path: "/nas/photo/2.jpg", target_path: "/trash/2.jpg", status: "done" },
          ],
        });
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        variant="simple"
        activeJobId=""
        recentJobIds={[]}
        onSelectJob={vi.fn()}
        onJobCreated={vi.fn()}
      />,
    );

    await screen.findByTestId("simple-defaults-card");
    await userEvent.click(screen.getByRole("button", { name: "Preview Impact" }));
    await screen.findByTestId("simple-action-preview");

    await userEvent.click(screen.getByRole("button", { name: "Create Draft Batch (2)" }));
    await screen.findByTestId("simple-action-batch");

    await userEvent.click(screen.getByRole("button", { name: "Confirm Batch" }));

    await waitFor(() => {
      expect(screen.getByTestId("simple-action-batch")).toHaveTextContent("executed");
      expect(screen.getByTestId("simple-action-batch")).toHaveTextContent("2");
    });

    expect(confirmPayload).toEqual({ confirm_delete_permanent: false });
  });
});
