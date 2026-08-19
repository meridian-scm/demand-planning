import { describe, expect, it } from "vitest";
import {
  EXCEPTION_TYPE_LABEL,
  formatCompact,
  formatCurrency,
  formatDateTime,
  formatMonth,
  formatPercent,
  formatUnits,
  MODEL_LABEL,
  SEVERITY_LABEL,
  STATUS_LABEL,
} from "@/lib/format";

describe("formatUnits", () => {
  it("formats whole numbers with thousands separators", () => {
    expect(formatUnits(1234)).toBe("1,234");
  });

  it("rounds fractional values", () => {
    expect(formatUnits(1234.6)).toBe("1,235");
  });

  it("returns an em dash for null/undefined/NaN", () => {
    expect(formatUnits(null)).toBe("—");
    expect(formatUnits(undefined)).toBe("—");
    expect(formatUnits(NaN)).toBe("—");
  });

  it("formats zero as 0, not a dash", () => {
    expect(formatUnits(0)).toBe("0");
  });
});

describe("formatCompact", () => {
  it("abbreviates large numbers", () => {
    expect(formatCompact(15000)).toBe("15K");
  });

  it("handles null gracefully", () => {
    expect(formatCompact(null)).toBe("—");
  });
});

describe("formatCurrency", () => {
  it("formats as USD", () => {
    expect(formatCurrency(19.5)).toBe("$19.50");
  });

  it("handles null gracefully", () => {
    expect(formatCurrency(null)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats with one decimal place", () => {
    expect(formatPercent(12.345)).toBe("12.3%");
  });

  it("adds a plus sign for positive values when signed is true", () => {
    expect(formatPercent(12.3, { signed: true })).toBe("+12.3%");
  });

  it("does not add a plus sign for negative values", () => {
    expect(formatPercent(-12.3, { signed: true })).toBe("-12.3%");
  });

  it("handles null gracefully", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatMonth", () => {
  it("formats an ISO date as short month + year", () => {
    expect(formatMonth("2025-06-01")).toBe("Jun 2025");
  });

  it("returns the em dash for null/undefined", () => {
    expect(formatMonth(null)).toBe("—");
    expect(formatMonth(undefined)).toBe("—");
  });

  it("falls back to the raw string for unparsable input", () => {
    expect(formatMonth("not-a-date")).toBe("not-a-date");
  });
});

describe("formatDateTime", () => {
  it("returns the em dash for null", () => {
    expect(formatDateTime(null)).toBe("—");
  });

  it("formats a valid ISO timestamp without throwing", () => {
    const result = formatDateTime("2025-06-15T10:30:00Z");
    expect(result).not.toBe("—");
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("label lookup tables", () => {
  it("covers every exception type used by the backend", () => {
    expect(Object.keys(EXCEPTION_TYPE_LABEL)).toEqual(
      expect.arrayContaining([
        "demand_spike",
        "demand_drop",
        "stockout_risk",
        "excess_inventory",
        "forecast_anomaly",
        "new_product_volatility",
      ]),
    );
  });

  it("covers every forecast model", () => {
    expect(MODEL_LABEL.auto).toBe("Auto-select");
    expect(MODEL_LABEL.holt_winters).toBe("Holt-Winters");
  });

  it("covers every severity level", () => {
    expect(SEVERITY_LABEL).toEqual({
      low: "Low",
      medium: "Medium",
      high: "High",
      critical: "Critical",
    });
  });

  it("covers every exception status", () => {
    expect(STATUS_LABEL).toEqual({
      open: "Open",
      acknowledged: "Acknowledged",
      resolved: "Resolved",
      dismissed: "Dismissed",
    });
  });
});
