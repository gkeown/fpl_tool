import { cn } from "@/lib/utils";

interface FormBadgeProps {
  value: number;
  className?: string;
}

export function formColor(form: number): string {
  if (form >= 6) return "#00ff87";
  if (form >= 4) return "#f7c948";
  return "#e90052";
}

export function formColorClass(form: number): string {
  if (form >= 6) return "bg-fpl-green/15 text-fpl-green border-fpl-green/30";
  if (form >= 4) return "bg-fpl-gold/15 text-fpl-gold border-fpl-gold/30";
  return "bg-fpl-pink/15 text-fpl-pink border-fpl-pink/30";
}

export default function FormBadge({ value, className }: FormBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-bold tabular-nums",
        formColorClass(value),
        className,
      )}
    >
      {value.toFixed(1)}
    </span>
  );
}
