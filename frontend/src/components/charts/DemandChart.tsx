import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatMonth, formatUnits } from "@/lib/format";
import type { DemandTimeline } from "@/types/api";

interface DemandChartProps {
  timeline: DemandTimeline;
}

interface ChartRow {
  period: string;
  actual?: number;
  forecast?: number;
  band?: [number, number];
}

/** Merges history + forecast into one continuous series keyed by period. */
function buildRows(timeline: DemandTimeline): ChartRow[] {
  const rows = new Map<string, ChartRow>();

  for (const point of timeline.history) {
    rows.set(point.period_start, { period: point.period_start, actual: point.units });
  }
  for (const point of timeline.forecast) {
    const existing = rows.get(point.period_start) ?? { period: point.period_start };
    existing.forecast = point.forecast_units;
    if (point.lower_bound_units !== null && point.upper_bound_units !== null) {
      existing.band = [point.lower_bound_units, point.upper_bound_units];
    }
    rows.set(point.period_start, existing);
  }

  return Array.from(rows.values()).sort((a, b) => a.period.localeCompare(b.period));
}

export function DemandChart({ timeline }: DemandChartProps) {
  const rows = buildRows(timeline);

  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <p>No demand history yet — upload sales data to see the chart.</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.18} />
            <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-soft)" />
        <XAxis
          dataKey="period"
          tickFormatter={(value: string) => formatMonth(value)}
          stroke="var(--color-text-faint)"
          fontSize={11}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(value: number) => formatUnits(value)}
          stroke="var(--color-text-faint)"
          fontSize={11}
          tickLine={false}
          width={54}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            fontSize: 12.5,
          }}
          labelFormatter={(value) => formatMonth(String(value))}
          formatter={(value: number, name: string) => [formatUnits(value), name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          type="monotone"
          dataKey={(row: ChartRow) => row.band?.[1]}
          stroke="none"
          fill="url(#bandFill)"
          name="Upper bound"
          isAnimationActive={false}
          legendType="none"
        />
        <Line
          type="monotone"
          dataKey="actual"
          name="Actual demand"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="forecast"
          name="Forecast"
          stroke="var(--color-primary)"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
