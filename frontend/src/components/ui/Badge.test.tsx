import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { Badge } from "@/components/ui/Badge";

describe("Badge", () => {
  it("renders the mapped severity label", () => {
    renderWithProviders(<Badge variant="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders custom children over the default label", () => {
    renderWithProviders(<Badge variant="open">Custom Label</Badge>);
    expect(screen.getByText("Custom Label")).toBeInTheDocument();
  });

  it("renders the mapped status label for exception statuses", () => {
    renderWithProviders(<Badge variant="acknowledged" />);
    expect(screen.getByText("Acknowledged")).toBeInTheDocument();
  });

  it("renders the mapped status label for the 'open' status, not the severity table", () => {
    // "open" is a status, not a severity — this guards against Badge only
    // ever consulting SEVERITY_LABEL and silently falling through to the
    // raw variant string for every status value.
    renderWithProviders(<Badge variant="open" />);
    expect(screen.getByText("Open")).toBeInTheDocument();
  });

  it("falls back to the raw variant name for unknown variants", () => {
    renderWithProviders(<Badge variant="mystery-status" />);
    expect(screen.getByText("mystery-status")).toBeInTheDocument();
  });

  it("applies the variant-specific CSS class", () => {
    renderWithProviders(<Badge variant="high" />);
    expect(screen.getByText("High")).toHaveClass("badge-high");
  });
});
