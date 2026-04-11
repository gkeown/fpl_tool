import { useState, useEffect } from "react";

function isMatchWindow(): boolean {
  const now = new Date();
  const day = now.getDay(); // 0=Sun, 6=Sat
  const hour = now.getHours();
  if (day === 6 && hour >= 12 && hour < 22) return true; // Saturday
  if (day === 0 && hour >= 12 && hour < 22) return true; // Sunday
  if (day === 1 && hour >= 20 && hour < 23) return true; // Monday evening
  return false;
}

export function useAutoRefresh(intervalMs = 60_000): boolean {
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
