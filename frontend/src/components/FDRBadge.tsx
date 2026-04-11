import { cn } from "@/lib/utils";

interface FDRBadgeProps {
  fdr: number;
  label?: string;
  className?: string;
}

export function fdrBg(fdr: number): string {
  if (fdr <= 1.5) return "#00ff87";
  if (fdr <= 2.0) return "#2ddc73";
  if (fdr <= 2.5) return "#5ec960";
  if (fdr <= 3.0) return "#97b84e";
  if (fdr <= 3.5) return "#d4a43a";
  if (fdr <= 4.0) return "#f58a23";
  if (fdr <= 4.5) return "#e95035";
  return "#e90052";
}

export function fdrTextColor(fdr: number): string {
  return fdr > 3.5 ? "#fff" : "#000";
}

export default function FDRBadge({ fdr, label, className }: FDRBadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold tabular-nums", className)}
      style={{ backgroundColor: fdrBg(fdr), color: fdrTextColor(fdr) }}
    >
      {label ?? fdr.toFixed(1)}
    </span>
  );
}
