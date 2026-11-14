// Number and date formatting for the tables.
const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const AGE_STEPS = [
  [31536000, "y"],
  [2592000, "mo"],
  [86400, "d"],
  [3600, "h"],
  [60, "m"],
];

/** A size as `[value, unit]`, e.g. `["1.5", "GB"]`. */
export function bytesParts(bytes) {
  if (bytes === null || bytes === undefined) {
    return ["—", ""];
  }
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return [value.toFixed(unit === 0 ? 0 : 1), BYTE_UNITS[unit]];
}

export function formatBytes(bytes) {
  return bytesParts(bytes).filter(Boolean).join(" ");
}

/** An age as `[value, unit]`, e.g. `["3", "d ago"]`; `["just now", ""]`. */
export function ageParts(isoDate) {
  if (!isoDate) {
    return ["—", ""];
  }
  const elapsed = Date.now() - new Date(isoDate).getTime();
  const seconds = Math.max(0, elapsed / 1000);
  const step = AGE_STEPS.find(([size]) => seconds >= size);
  return step
    ? [String(Math.floor(seconds / step[0])), `${step[1]} ago`]
    : ["just now", ""];
}

export function timeAgo(isoDate) {
  const [value, unit] = ageParts(isoDate);
  return `${value}${unit}`;
}

/** A duration in milliseconds as `[value, unit]`: 850 ms, 1.2 s, 2 m. */
export function durationParts(ms) {
  if (ms < 1000) {
    return [String(Math.round(ms)), "ms"];
  }
  if (ms < 60000) {
    return [(ms / 1000).toFixed(1), "s"];
  }
  return [String(Math.floor(ms / 60000)), "m"];
}

/** A duration in milliseconds, compact like `timeAgo`: 850ms, 1.2s, 2m. */
export function formatDuration(ms) {
  return durationParts(ms).join("");
}

export function formatDate(isoDate) {
  return isoDate ? new Date(isoDate).toLocaleString() : "—";
}
