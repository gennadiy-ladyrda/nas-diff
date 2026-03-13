import { expect, test } from "@playwright/test";

test("reviews group, creates action batch, confirms execution", async ({ page }) => {
  let batchStatus = "draft";

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (url.includes("/api/v1/scan/jobs/job-e2e-2/groups") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "job-e2e-2",
          kind: "exact",
          total: 1,
          page: 1,
          page_size: 100,
          items: [{ id: 55, file_count: 2, reclaimable_bytes: 100 }],
        }),
      });
      return;
    }

    if (url.endsWith("/api/v1/groups/exact/55") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          group_kind: "exact",
          group_id: 55,
          items: [
            {
              file_id: 500,
              abs_path: "/nas/photo/a.jpg",
              size_bytes: 110,
              is_primary: true,
              decision: null,
            },
            {
              file_id: 501,
              abs_path: "/nas/photo/b.jpg",
              size_bytes: 108,
              is_primary: false,
              decision: null,
            },
          ],
        }),
      });
      return;
    }

    if (url.endsWith("/api/v1/groups/exact/55/decision") && method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ group_kind: "exact", group_id: 55, file_id: 501, decision: "keep", note: null }),
      });
      return;
    }

    if (url.endsWith("/api/v1/actions/batches") && method === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          batch_id: "batch-e2e-1",
          status: "draft",
          action_type: "move_to_trash",
          stats: { total: 1, pending: 1, done: 0, failed: 0, skipped: 0 },
          items: [
            {
              id: 900,
              file_id: 501,
              source_path: "/nas/photo/b.jpg",
              target_path: "/nas/.nas-diff-trash/nas/photo/b.jpg",
              status: "pending",
              error_message: null,
            },
          ],
        }),
      });
      return;
    }

    if (url.endsWith("/api/v1/actions/batches/batch-e2e-1/confirm") && method === "POST") {
      batchStatus = "executed";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ batch_id: "batch-e2e-1", status: "confirmed", queued: true }),
      });
      return;
    }

    if (url.endsWith("/api/v1/actions/batches/batch-e2e-1") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          batch_id: "batch-e2e-1",
          status: batchStatus,
          action_type: "move_to_trash",
          stats: {
            total: 1,
            pending: batchStatus === "executed" ? 0 : 1,
            done: batchStatus === "executed" ? 1 : 0,
            failed: 0,
            skipped: 0,
          },
          items: [
            {
              id: 900,
              file_id: 501,
              source_path: "/nas/photo/b.jpg",
              target_path: "/nas/.nas-diff-trash/nas/photo/b.jpg",
              status: batchStatus === "executed" ? "done" : "pending",
              error_message: null,
            },
          ],
        }),
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: `${method} ${url} is not mocked` }),
    });
  });

  await page.goto("/review");

  await page.getByPlaceholder("Scan job id").fill("job-e2e-2");
  await page.getByRole("button", { name: "Load" }).click();

  await expect(page.getByTestId("group-details-table")).toBeVisible();

  await page.getByRole("button", { name: "Create Draft Batch (1)" }).click();
  await expect(page.getByTestId("batch-card")).toContainText("draft");

  await page.getByRole("button", { name: "Confirm Batch" }).click();
  await expect(page.getByTestId("batch-card")).toContainText("executed");
  await expect(page.getByTestId("batch-card")).toContainText("done");
});
