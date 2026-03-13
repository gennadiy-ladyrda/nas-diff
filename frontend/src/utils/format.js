const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];

export function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }

  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), BYTE_UNITS.length - 1);
  const normalized = bytes / 1024 ** exponent;
  const precision = exponent === 0 ? 0 : 1;

  return `${normalized.toFixed(precision)} ${BYTE_UNITS[exponent]}`;
}

export function formatTimestamp(value) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

export function toShortPath(path) {
  if (!path) {
    return "-";
  }
  return path.length > 72 ? `...${path.slice(-69)}` : path;
}
