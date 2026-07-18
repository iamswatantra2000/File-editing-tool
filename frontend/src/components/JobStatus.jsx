import { resultUrl } from "../api.js";

const STATUS_CONFIG = {
  pending: {
    label: "Pending",
    className: "bg-stone-800 text-stone-400 border border-stone-700",
  },
  running: {
    label: "Running",
    className: "bg-orange-500/10 text-orange-400 border border-orange-500/30",
  },
  done: {
    label: "Done",
    className: "bg-stone-800 text-stone-200 border border-stone-700",
  },
  failed: {
    label: "Failed",
    className: "bg-red-950/60 text-red-400 border border-red-800/40",
  },
};

export default function JobStatus({ job, onReset }) {
  if (!job) return null;

  const { id, status, changes = [], error } = job;
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 sm:p-6 mt-4 space-y-4 sm:space-y-5">

      {/* Status row */}
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full
                          text-xs font-semibold uppercase tracking-wider font-inter shrink-0
                          ${cfg.className}`}>
          {status === "running" && <span className="spinner" />}
          {cfg.label}
        </span>
        <span className="text-xs text-stone-600 font-mono truncate min-w-0 hidden sm:block">
          {id}
        </span>
        <span className="text-xs text-stone-600 font-mono truncate min-w-0 sm:hidden">
          {id.slice(0, 8)}…
        </span>
      </div>

      {/* Running message */}
      {status === "running" && (
        <p className="text-xs sm:text-sm text-stone-500 leading-relaxed">
          The agent is editing your document…
        </p>
      )}

      {/* Changes list */}
      {changes.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-stone-500 mb-3">
            Changes applied
          </p>
          <ul className="space-y-2.5">
            {changes.map((c, i) => (
              <li key={i} className="flex flex-col sm:flex-row sm:items-start gap-1.5 sm:gap-3">
                <span className="shrink-0 self-start bg-stone-800 border border-stone-700 text-orange-400
                                 px-2 py-0.5 rounded text-xs font-mono font-medium">
                  {c.tool}
                </span>
                <span className="text-xs sm:text-sm text-stone-300 sm:pt-0.5 leading-relaxed">
                  {c.description}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-950/60 border border-red-800/50 rounded-lg px-4 py-3
                        text-xs sm:text-sm text-red-400 leading-relaxed">
          <span className="font-semibold">Error: </span>{error}
        </div>
      )}

      {/* Actions */}
      {(status === "done" || status === "failed") && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 pt-1">
          {status === "done" && (
            <a
              href={resultUrl(id)}
              download
              className="inline-flex items-center justify-center gap-2
                         bg-orange-500 hover:bg-orange-600 active:bg-orange-700
                         text-stone-950 font-semibold text-sm rounded-lg
                         px-5 py-2.5 transition font-inter w-full sm:w-auto"
            >
              Download edited file
            </a>
          )}
          <button
            onClick={onReset}
            className="text-sm text-stone-500 hover:text-orange-400 underline
                       underline-offset-2 transition font-inter text-center sm:text-left"
          >
            Edit another document
          </button>
        </div>
      )}
    </div>
  );
}
