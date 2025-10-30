export const int = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
};

export function hashColor(seed) {
  // Deterministic pastel-ish color from string
  let h = 0;
  const s = String(seed || '');
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsl(${hue}, 60%, 65%)`;
}

export function colorForTask(taskName) {
  // Simple mapping by task name hash to stable palette
  const palette = ['#5b8def', '#50e3c2', '#f5a623', '#ff6b6b', '#b084eb', '#7ed957'];
  if (!taskName) return palette[0];
  let h = 0;
  const s = String(taskName);
  for (let i = 0; i < s.length; i++) h = (h * 33 + s.charCodeAt(i)) >>> 0;
  return palette[h % palette.length];
}
