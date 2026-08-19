import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { DashboardPage } from "@/pages/DashboardPage";

describe("DashboardPage", () => {
  it("shows a loading state before data arrives", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("renders KPI tiles once the summary loads", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("25")).toBeInTheDocument());
    expect(screen.getByText("Active Products")).toBeInTheDocument();
    expect(screen.getByText("Open Exceptions")).toBeInTheDocument();
  });

  it("shows the critical exception count as a negative delta", async () => {
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("2 critical")).toBeInTheDocument());
    expect(screen.getByText("2 critical")).toHaveClass("negative");
  });

  it("links the 'Run Forecast Cycle' action to the forecast page", async () => {
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("Run Forecast Cycle")).toBeInTheDocument());
    expect(screen.getByText("Run Forecast Cycle").closest("a")).toHaveAttribute("href", "/forecast");
  });
});
