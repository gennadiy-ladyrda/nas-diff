import { expect, test } from "@playwright/test";

test("launches scan job and shows it in jobs journal with detail panel", async ({ page }) => {
  let jobs = [];
  let jobPollCount = 0;

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (url.endsWith("/api/v1/health") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          service: "nas-diff",
          version: "0.1.0",
          status: "ok",
          components: {
            api: { status: "ok" },
            database: { status: "ok" },
            redis: { status: "ok" },
          },
        }),
      });
      return;
    }

    if (url.endsWith("/api/v1/scan/roots") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ id: 1, path: "/nas/photo", enabled: true }]),
      });
      return;
    }

    if (url.includes("/api/v1/scan/jobs?") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          page: 1,
          page_size: 20,
          total: jobs.length,
          items: jobs,
        }),
      });
      return;
    }

    if (url.endsWith("/api/v1/scan/jobs") && method === "POST") {
      jobs = [
        {
          job_id: "job-e2e-1",
          mode: "both",
          status: "running",
          requested_at: "2026-03-14T00:00:00",
          started_at: "2026-03-14T00:00:01",
          finished_at: null,
          error_message: null,
          files_seen: 4,
          files_indexed: 4,
          exact_groups_found: 2,
          similar_groups_found: 1,
          reclaimable_bytes: 2048,
        },
      ];

      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "job-e2e-1",
          status: "queued",
          mode: "both",
          root_ids: [1],
          queued: true,
        }),
      });
      return;
    }

    if (url.endsWith("/api/v1/scan/jobs/job-e2e-1") && method === "GET") {
      jobPollCount += 1;
      const status = jobPollCount < 2 ? "running" : "completed";
      jobs = [
        {
          job_id: "job-e2e-1",
          mode: "both",
          status,
          requested_at: "2026-03-14T00:00:00",
          started_at: "2026-03-14T00:00:01",
          finished_at: status === "completed" ? "2026-03-14T00:00:04" : null,
          error_message: null,
          files_seen: 4,
          files_indexed: 4,
          exact_groups_found: 2,
          similar_groups_found: 1,
          reclaimable_bytes: 2048,
        },
      ];

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "job-e2e-1",
          mode: "both",
          status,
          requested_at: "2026-03-14T00:00:00",
          started_at: "2026-03-14T00:00:01",
          finished_at: status === "completed" ? "2026-03-14T00:00:04" : null,
          error_message: null,
          files_seen: 4,
          files_indexed: 4,
          exact_groups_found: 2,
          similar_groups_found: 1,
          reclaimable_bytes: 2048,
          roots: [{ id: 1, path: "/nas/photo", enabled: true }],
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

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "NAS Diff Control Plane" })).toBeVisible();
  await page.getByRole("button", { name: "Start Scan" }).click();

  await expect(page.getByTestId("jobs-table")).toContainText("SCAN-BOTH-0001");
  await expect(page.getByTestId("job-detail-panel")).toContainText("job-e2e-1");
  await expect(page.getByTestId("job-detail-panel")).toContainText("completed");
  await expect(page.getByTestId("job-detail-panel")).toContainText("2.0 KB");
});
