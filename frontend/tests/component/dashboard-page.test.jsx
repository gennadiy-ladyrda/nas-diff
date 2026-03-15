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
  });
});
