import { useState, useEffect } from "react";

/**
 * Check if the current time is within a match window (UK time).
 * Uses Europe/London via Intl.DateTimeFormat to handle timezone correctly.
 */
function isMatchWindow(): boolean {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/London",
      weekday: "short",
      hour: "numeric",
      hour12: false,
    }).formatToParts(new Date());

    const weekday = parts.find((p) => p.type === "weekday")?.value;
    const hourStr = parts.find((p) => p.type === "hour")?.value;
    if (!weekday || hourStr === undefined) return false;
    const hour = parseInt(hourStr, 10);

    // Weekday as string: Mon, Tue, Wed, Thu, Fri, Sat, Sun
    if (weekday === "Sat" && hour >= 12 && hour < 22) return true;
    if (weekday === "Sun" && hour >= 12 && hour < 22) return true;
    if (weekday === "Mon" && hour >= 20 && hour < 23) return true;
    if (weekday === "Fri" && hour >= 19 && hour < 23) return true;
    return false;
  } catch {
    // Fallback to local time if Intl fails
    const now = new Date();
    const day = now.getDay();
    const hour = now.getHours();
    if (day === 6 && hour >= 12 && hour < 22) return true;
    if (day === 0 && hour >= 12 && hour < 22) return true;
    if (day === 1 && hour >= 20 && hour < 23) return true;
    return false;
  }
}

export function useAutoRefresh(): boolean {
  const [active, setActive] = useState(isMatchWindow());

  useEffect(() => {
    const check = setInterval(() => setActive(isMatchWindow()), 60_000);
    return () => clearInterval(check);
  }, []);

  return active;
}

export function useAutoRefreshInterval(intervalMs = 60_000): number | false {
  const active = useAutoRefresh();
  return active ? intervalMs : false;
}
