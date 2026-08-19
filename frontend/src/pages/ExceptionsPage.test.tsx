import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ExceptionsPage } from "@/pages/ExceptionsPage";

describe("ExceptionsPage", () => {
  it("renders exceptions returned by the API", async () => {
    renderWithProviders(<ExceptionsPage />);
    await waitFor(() => expect(screen.getByText(/Stockout Risk/i)).toBeInTheDocument());
    expect(screen.getByText("SKU-1001")).toBeInTheDocument();
  });

  it("defaults to the 'open' status filter chip being active", async () => {
    renderWithProviders(<ExceptionsPage />);
    // "Open" also appears as the status badge on the seeded exception row, so
    // the filter chip must be targeted by role rather than by text alone.
    const openChip = await screen.findByRole("button", { name: "Open" });
    expect(openChip).toHaveClass("active");
  });

  it("switches the active filter chip on click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExceptionsPage />);
    const resolvedChip = await screen.findByRole("button", { name: "Resolved" });

    await user.click(resolvedChip);
    expect(resolvedChip).toHaveClass("active");
    expect(screen.getByRole("button", { name: "Open" })).not.toHaveClass("active");
  });

  it("shows Ack/Resolve actions for open exceptions", async () => {
    renderWithProviders(<ExceptionsPage />);
    await waitFor(() => expect(screen.getByText("Ack")).toBeInTheDocument());
    expect(screen.getByText("Resolve")).toBeInTheDocument();
  });
});
