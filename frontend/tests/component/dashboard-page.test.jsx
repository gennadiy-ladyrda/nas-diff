import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DashboardPage } from "../../src/pages/DashboardPage";

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DashboardPage", () => {
  it("starts scan and renders final metrics", async () => {
    const onJobCreated = vi.fn();
    const onSelectJob = vi.fn();

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
          { id: 2, path: "/nas/archive", enabled: false },
        ]);
      }

      if (url.endsWith("/api/v1/scan/jobs") && method === "POST") {
        return jsonResponse({ job_id: "job-001", status: "queued", mode: "both", root_ids: [1], queued: true }, 201);
      }

      if (url.endsWith("/api/v1/scan/jobs/job-001") && method === "GET") {
        return jsonResponse({
          job_id: "job-001",
          mode: "both",
          status: "completed",
          requested_at: "2026-03-13T00:00:00",
          started_at: "2026-03-13T00:00:01",
          finished_at: "2026-03-13T00:00:10",
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
      expect(screen.getByTestId("scan-job-card")).toHaveTextContent("completed");
      expect(screen.getByTestId("scan-job-card")).toHaveTextContent("1.0 KB");
    });
  });
});
