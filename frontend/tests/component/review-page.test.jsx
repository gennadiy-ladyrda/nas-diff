import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ReviewPage } from "../../src/pages/ReviewPage";

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReviewPage", () => {
  it("saves decision and runs action batch workflow", async () => {
    const groupDetailsBase = {
      group_kind: "exact",
      group_id: 101,
      items: [
        {
          file_id: 1,
          abs_path: "/nas/photo/a.jpg",
          size_bytes: 100,
          is_primary: true,
          decision: null,
        },
        {
          file_id: 2,
          abs_path: "/nas/photo/b.jpg",
          size_bytes: 100,
          is_primary: false,
          decision: null,
        },
      ],
    };

    let latestGroupDetails = structuredClone(groupDetailsBase);
    let latestBatch = {
      batch_id: "batch-1",
      status: "draft",
      action_type: "move_to_trash",
      stats: { total: 1, pending: 1, done: 0, failed: 0, skipped: 0 },
      items: [
        {
          id: 11,
          file_id: 2,
          source_path: "/nas/photo/b.jpg",
          target_path: "/nas/.nas-diff-trash/nas/photo/b.jpg",
          status: "pending",
          error_message: null,
        },
      ],
    };

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.includes("/api/v1/scan/jobs/job-1/groups") && method === "GET") {
        return jsonResponse({
          job_id: "job-1",
          kind: "exact",
          page: 1,
          page_size: 100,
          total: 1,
          items: [{ id: 101, file_count: 2, reclaimable_bytes: 100 }],
        });
      }

      if (url.endsWith("/api/v1/groups/exact/101") && method === "GET") {
        return jsonResponse(latestGroupDetails);
      }

      if (url.endsWith("/api/v1/groups/exact/101/decision") && method === "POST") {
        latestGroupDetails.items[0].is_primary = false;
        latestGroupDetails.items[1].is_primary = true;
        latestGroupDetails.items[1].decision = "keep";
        return jsonResponse({ group_kind: "exact", group_id: 101, file_id: 2, decision: "keep", note: null });
      }

      if (url.endsWith("/api/v1/actions/batches") && method === "POST") {
        return jsonResponse(latestBatch, 201);
      }

      if (url.endsWith("/api/v1/actions/batches/preview") && method === "POST") {
        return jsonResponse({
          action_type: "move_to_trash",
          file_ids: [2],
          files_count: 1,
          total_bytes: 100,
          estimated_reclaimable_bytes: 100,
        });
      }

      if (url.endsWith("/api/v1/actions/batches/batch-1/confirm") && method === "POST") {
        latestBatch = {
          ...latestBatch,
          status: "executed",
          stats: { total: 1, pending: 0, done: 1, failed: 0, skipped: 0 },
          items: latestBatch.items.map((item) => ({ ...item, status: "done" })),
        };
        return jsonResponse({ batch_id: "batch-1", status: "confirmed", queued: true });
      }

      if (url.endsWith("/api/v1/actions/batches/batch-1") && method === "GET") {
        return jsonResponse(latestBatch);
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewPage activeJobId="job-1" recentJobIds={["job-1"]} onSelectJob={vi.fn()} />);

    await screen.findByTestId("group-list");
    await screen.findByTestId("group-details-table");

    await userEvent.click(screen.getAllByRole("button", { name: "keep" })[1]);

    await waitFor(() => {
      expect(screen.getByTestId("group-details-table")).toHaveTextContent("keep");
    });

    await userEvent.click(screen.getByRole("button", { name: "Preview Impact" }));
    await screen.findByTestId("action-preview-card");

    await userEvent.click(screen.getByRole("button", { name: "Create Draft Batch (1)" }));
    await screen.findByTestId("batch-card");

    await userEvent.click(screen.getByRole("button", { name: "Confirm Batch" }));

    await waitFor(() => {
      expect(screen.getByTestId("batch-card")).toHaveTextContent("executed");
      expect(screen.getByTestId("batch-card")).toHaveTextContent("done");
    });
  });

  it("previews all_filtered scope across all loaded groups", async () => {
    let previewPayload = null;
    let createPayload = null;

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.includes("/api/v1/scan/jobs/job-2/groups") && method === "GET") {
        return jsonResponse({
          job_id: "job-2",
          kind: "exact",
          page: 1,
          page_size: 100,
          total: 2,
          items: [
            { id: 201, file_count: 2, reclaimable_bytes: 100 },
            { id: 202, file_count: 2, reclaimable_bytes: 120 },
          ],
        });
      }

      if (url.endsWith("/api/v1/groups/exact/201") && method === "GET") {
        return jsonResponse({
          group_kind: "exact",
          group_id: 201,
          items: [
            { file_id: 10, abs_path: "/nas/photo/a1.jpg", size_bytes: 100, is_primary: true, decision: null },
            { file_id: 11, abs_path: "/nas/photo/a2.jpg", size_bytes: 100, is_primary: false, decision: null },
          ],
        });
      }

      if (url.endsWith("/api/v1/groups/exact/202") && method === "GET") {
        return jsonResponse({
          group_kind: "exact",
          group_id: 202,
          items: [
            { file_id: 12, abs_path: "/nas/photo/b1.jpg", size_bytes: 120, is_primary: true, decision: null },
            { file_id: 13, abs_path: "/nas/photo/b2.jpg", size_bytes: 120, is_primary: false, decision: null },
          ],
        });
      }

      if (url.endsWith("/api/v1/actions/batches/preview") && method === "POST") {
        previewPayload = JSON.parse(options.body);
        return jsonResponse({
          action_type: "move_to_trash",
          file_ids: [11, 13],
          files_count: 2,
          total_bytes: 220,
          estimated_reclaimable_bytes: 220,
        });
      }

      if (url.endsWith("/api/v1/actions/batches") && method === "POST") {
        createPayload = JSON.parse(options.body);
        return jsonResponse(
          {
            batch_id: "batch-all-filtered",
            status: "draft",
            action_type: "move_to_trash",
            stats: { total: 2, pending: 2, done: 0, failed: 0, skipped: 0 },
            items: [],
          },
          201,
        );
      }

      if (url.endsWith("/api/v1/actions/batches/batch-all-filtered") && method === "GET") {
        return jsonResponse({
          batch_id: "batch-all-filtered",
          status: "draft",
          action_type: "move_to_trash",
          stats: { total: 2, pending: 2, done: 0, failed: 0, skipped: 0 },
          items: [],
        });
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewPage activeJobId="job-2" recentJobIds={["job-2"]} onSelectJob={vi.fn()} />);

    await screen.findByTestId("group-list");
    await screen.findByTestId("group-details-table");

    await userEvent.selectOptions(screen.getByLabelText("bulk-scope"), "all_filtered");
    await userEvent.click(screen.getByRole("button", { name: "Preview Impact" }));

    await waitFor(() => {
      expect(previewPayload).toEqual({
        action_type: "move_to_trash",
        file_ids: [11, 13],
      });
    });
    await screen.findByTestId("action-preview-card");

    await userEvent.click(screen.getByRole("button", { name: "Create Draft Batch (2)" }));

    expect(createPayload).toEqual({
      action_type: "move_to_trash",
      file_ids: [11, 13],
      summary: "exact:scope=all_filtered;group=201",
    });
  });

  it("supports rollback after executed move_to_trash batch", async () => {
    let sourceBatch = {
      batch_id: "batch-rb-1",
      status: "draft",
      action_type: "move_to_trash",
      stats: { total: 1, pending: 1, done: 0, failed: 0, skipped: 0 },
      items: [
        {
          id: 5001,
          file_id: 2,
          source_path: "/nas/photo/b.jpg",
          target_path: "/nas/.nas-diff-trash/nas/photo/b.jpg",
          status: "pending",
          error_message: null,
        },
      ],
    };

    const rollbackBatch = {
      batch_id: "batch-rb-restore-1",
      status: "executed",
      action_type: "restore",
      stats: { total: 1, pending: 0, done: 1, failed: 0, skipped: 0 },
      items: [
        {
          id: 5002,
          file_id: 2,
          source_path: "/nas/.nas-diff-trash/nas/photo/b.jpg",
          target_path: "/nas/photo/b.jpg",
          status: "done",
          error_message: null,
        },
      ],
    };

    const fetchMock = vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = (options.method || "GET").toUpperCase();

      if (url.includes("/api/v1/scan/jobs/job-rb/groups") && method === "GET") {
        return jsonResponse({
          job_id: "job-rb",
          kind: "exact",
          page: 1,
          page_size: 100,
          total: 1,
          items: [{ id: 301, file_count: 2, reclaimable_bytes: 100 }],
        });
      }

      if (url.endsWith("/api/v1/groups/exact/301") && method === "GET") {
        return jsonResponse({
          group_kind: "exact",
          group_id: 301,
          items: [
            { file_id: 1, abs_path: "/nas/photo/a.jpg", size_bytes: 100, is_primary: true, decision: null },
            { file_id: 2, abs_path: "/nas/photo/b.jpg", size_bytes: 100, is_primary: false, decision: null },
          ],
        });
      }

      if (url.endsWith("/api/v1/actions/batches/preview") && method === "POST") {
        return jsonResponse({
          action_type: "move_to_trash",
          file_ids: [2],
          files_count: 1,
          total_bytes: 100,
          estimated_reclaimable_bytes: 100,
        });
      }

      if (url.endsWith("/api/v1/actions/batches") && method === "POST") {
        return jsonResponse(sourceBatch, 201);
      }

      if (url.endsWith("/api/v1/actions/batches/batch-rb-1/confirm") && method === "POST") {
        sourceBatch = {
          ...sourceBatch,
          status: "executed",
          stats: { total: 1, pending: 0, done: 1, failed: 0, skipped: 0 },
          items: sourceBatch.items.map((item) => ({ ...item, status: "done" })),
        };
        return jsonResponse({ batch_id: "batch-rb-1", status: "confirmed", queued: true });
      }

      if (url.endsWith("/api/v1/actions/batches/batch-rb-1/rollback") && method === "POST") {
        return jsonResponse({
          source_batch_id: "batch-rb-1",
          rollback_batch_id: "batch-rb-restore-1",
          status: "confirmed",
          queued: true,
        });
      }

      if (url.endsWith("/api/v1/actions/batches/batch-rb-1") && method === "GET") {
        return jsonResponse(sourceBatch);
      }

      if (url.endsWith("/api/v1/actions/batches/batch-rb-restore-1") && method === "GET") {
        return jsonResponse(rollbackBatch);
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewPage activeJobId="job-rb" recentJobIds={["job-rb"]} onSelectJob={vi.fn()} />);

    await screen.findByTestId("group-details-table");
    await userEvent.click(screen.getByRole("button", { name: "Preview Impact" }));
    await screen.findByTestId("action-preview-card");

    await userEvent.click(screen.getByRole("button", { name: "Create Draft Batch (1)" }));
    await screen.findByTestId("batch-card");

    await userEvent.click(screen.getByRole("button", { name: "Confirm Batch" }));
    await waitFor(() => {
      expect(screen.getByTestId("batch-card")).toHaveTextContent("executed");
    });

    await userEvent.click(screen.getByRole("button", { name: "Rollback" }));
    await waitFor(() => {
      expect(screen.getByTestId("batch-card")).toHaveTextContent("batch-rb-restore-1");
      expect(screen.getByTestId("batch-card")).toHaveTextContent("restore");
    });
  });
});
