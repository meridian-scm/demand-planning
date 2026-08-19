import clsx from "clsx";

interface KpiTileProps {
  label: string;
  value: string;
  delta?: { text: string; direction: "positive" | "negative" | "neutral" };
}

export function KpiTile({ label, value, delta }: KpiTileProps) {
  return (
    <div className="kpi-tile" data-testid="kpi-tile">
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{value}</p>
      {delta && <div className={clsx("kpi-delta", delta.direction)}>{delta.text}</div>}
    </div>
  );
}
