import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCompact } from "@/lib/format";
import type { CategoryBreakdown } from "@/types/api";

export function CategoryChart({ data }: { data: CategoryBreakdown[] }) {
  if (data.length === 0) {
    return <div className="empty-state">No category data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-soft)" />
        <XAxis dataKey="category" stroke="var(--color-text-faint)" fontSize={11} tickLine={false} />
        <YAxis
          tickFormatter={(v: number) => formatCompact(v)}
          stroke="var(--color-text-faint)"
          fontSize={11}
          tickLine={false}
          width={44}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            fontSize: 12.5,
          }}
        />
        <Bar dataKey="history_units" name="Recent demand" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
        <Bar dataKey="forecast_units" name="Forecast" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
