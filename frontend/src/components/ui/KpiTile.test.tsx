import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { KpiTile } from "@/components/ui/KpiTile";

describe("KpiTile", () => {
  it("renders the label and value", () => {
    renderWithProviders(<KpiTile label="Active Products" value="25" />);
    expect(screen.getByText("Active Products")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("omits the delta row when none is provided", () => {
    renderWithProviders(<KpiTile label="Products" value="25" />);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("renders a positive delta with the positive tone class", () => {
    renderWithProviders(
      <KpiTile label="Demand" value="1,200" delta={{ text: "+7.8%", direction: "positive" }} />,
    );
    const delta = screen.getByText("+7.8%");
    expect(delta).toHaveClass("positive");
  });

  it("renders a negative delta with the negative tone class", () => {
    renderWithProviders(
      <KpiTile label="Exceptions" value="7" delta={{ text: "2 critical", direction: "negative" }} />,
    );
    expect(screen.getByText("2 critical")).toHaveClass("negative");
  });
});
