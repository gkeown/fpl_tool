import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const label = status === "a" ? "Fit" : status === "d" ? "Doubt" : status === "i" ? "Injured" : (status || "Unknown").toUpperCase();
  const colorClass =
    status === "a"
      ? "bg-fpl-green/15 text-fpl-green border-fpl-green/30"
      : status === "d"
        ? "bg-fpl-gold/15 text-fpl-gold border-fpl-gold/30"
        : "bg-fpl-pink/15 text-fpl-pink border-fpl-pink/30";

  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold", colorClass, className)}>
      {label}
    </span>
  );
}
