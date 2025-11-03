// Lightweight date utilities for client-only usage
// No timezone normalization here — we use the user's local time.

export function msUntilNextLocalMidnight(now = new Date()) {
  const next = new Date(now);
  // Move to next local midnight
  next.setHours(24, 0, 0, 0);
  const delta = next.getTime() - now.getTime();
  // Safety: in rare DST/clock-change cases delta can be <= 0
  return delta > 0 ? delta : 10_000; // 10s fallback
}
