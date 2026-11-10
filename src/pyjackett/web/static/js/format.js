// Number and date formatting for the tables.
const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const AGE_STEPS = [
  [31536000, "y"],
  [2592000, "mo"],
  [86400, "d"],
  [3600, "h"],
  [60, "m"],
];

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) {
    return "—";
  }
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${BYTE_UNITS[unit]}`;
}

export function timeAgo(isoDate) {
  if (!isoDate) {
    return "—";
  }
  const elapsed = Date.now() - new Date(isoDate).getTime();
  const seconds = Math.max(0, elapsed / 1000);
  const step = AGE_STEPS.find(([size]) => seconds >= size);
  return step ? `${Math.floor(seconds / step[0])}${step[1]} ago` : "just now";
}

export function formatDate(isoDate) {
  return isoDate ? new Date(isoDate).toLocaleString() : "—";
}
