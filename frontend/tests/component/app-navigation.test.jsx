import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../src/pages/DashboardPage", () => ({
  DashboardPage: ({ variant }) => <div data-testid={`dashboard-${variant}`}>{variant}</div>,
}));

vi.mock("../../src/pages/ReviewPage", () => ({
  ReviewPage: () => <div data-testid="review-page">review</div>,
}));

import App from "../../src/App";

describe("App navigation", () => {
  it("opens Simple Scan by default and routes Advanced through the hamburger menu", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-simple")).toBeInTheDocument();
    expect(screen.getByText("Simple Scan")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Open navigation menu" }));
    await userEvent.click(screen.getByRole("link", { name: "Advanced" }));

    expect(screen.getByTestId("dashboard-advanced")).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
  });

  it("closes the hamburger menu by Escape and outside click", async () => {
    render(
      <MemoryRouter initialEntries={["/review"]}>
        <App />
      </MemoryRouter>,
    );

    const menuButton = screen.getByRole("button", { name: "Open navigation menu" });
    await userEvent.click(menuButton);
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();

    await userEvent.click(menuButton);
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();

    await userEvent.click(screen.getByText("NAS Diff Control Plane"));
    expect(screen.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
  });
});
