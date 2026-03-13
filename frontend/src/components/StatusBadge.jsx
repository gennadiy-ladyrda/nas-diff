const STATUS_CLASS_MAP = {
  ok: "badge badge--ok",
  degraded: "badge badge--warn",
  queued: "badge badge--neutral",
  running: "badge badge--info",
  completed: "badge badge--ok",
  confirmed: "badge badge--info",
  executed: "badge badge--ok",
  rolled_back: "badge badge--ok",
  partially_failed: "badge badge--warn",
  failed: "badge badge--danger",
  draft: "badge badge--neutral",
};

export function StatusBadge({ value }) {
  const label = value || "unknown";
  const className = STATUS_CLASS_MAP[label] || "badge badge--neutral";
  return <span className={className}>{label}</span>;
}
