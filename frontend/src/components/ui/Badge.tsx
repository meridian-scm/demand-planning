import clsx from "clsx";
import { SEVERITY_LABEL, STATUS_LABEL } from "@/lib/format";

interface BadgeProps {
  variant: string;
  children?: React.ReactNode;
}

/**
 * A small status/severity pill. `variant` doubles as both the CSS modifier
 * (`badge-{variant}`) and the lookup key across the severity and status
 * label tables (both use lowercase snake-free keys, so this is unambiguous).
 * Falls back to the raw variant string for anything neither table covers.
 */
export function Badge({ variant, children }: BadgeProps) {
  const label = children ?? SEVERITY_LABEL[variant] ?? STATUS_LABEL[variant] ?? variant;
  return <span className={clsx("badge", `badge-${variant}`)}>{label}</span>;
}
