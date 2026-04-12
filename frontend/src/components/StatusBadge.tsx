import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  chanceOfPlaying?: number | null;
  className?: string;
}

export default function StatusBadge({
  status,
  chanceOfPlaying,
  className,
}: StatusBadgeProps) {
  // If status is not fit and we have a chance of playing, show the percentage
  let label: string;
  if (status === "a") {
    label = "Fit";
  } else if (chanceOfPlaying != null && chanceOfPlaying >= 0) {
    label = `${chanceOfPlaying}%`;
  } else if (status === "d") {
    label = "Doubt";
  } else if (status === "i") {
    label = "Injured";
  } else if (status === "s") {
    label = "Suspended";
  } else if (status === "u") {
    label = "Unavailable";
  } else {
    label = (status || "Unknown").toUpperCase();
  }

  // Color by chance: 75+ amber, 50 amber, <50 pink, fit green
  let colorClass: string;
  if (status === "a") {
    colorClass = "bg-fpl-green/15 text-fpl-green border-fpl-green/30";
  } else if (chanceOfPlaying != null) {
    if (chanceOfPlaying >= 75) {
      colorClass = "bg-fpl-gold/15 text-fpl-gold border-fpl-gold/30";
    } else if (chanceOfPlaying >= 25) {
      colorClass = "bg-fpl-gold/15 text-fpl-gold border-fpl-gold/30";
    } else {
      colorClass = "bg-fpl-pink/15 text-fpl-pink border-fpl-pink/30";
    }
  } else if (status === "d") {
    colorClass = "bg-fpl-gold/15 text-fpl-gold border-fpl-gold/30";
  } else {
    colorClass = "bg-fpl-pink/15 text-fpl-pink border-fpl-pink/30";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold",
        colorClass,
        className,
      )}
    >
      {label}
    </span>
  );
}
