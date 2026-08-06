import clsx from "clsx";

// The one shared layer above each dashboard's existing Header/tabs pattern —
// lets a dashboard switch between its original content and the new Nykaa
// Pulse area without touching Header.jsx itself. Deliberately tiny and
// visually secondary (a thin pill row) so the existing Header underneath
// still reads as the primary navigation.
export function MegaTabs({ tabs, value, onChange }) {
  return (
    <div className="border-b border-black/8 dark:border-white/10 bg-black/[0.015] dark:bg-white/[0.02]">
      <div className="container-app flex gap-1 px-4 py-2">
        {tabs.map(({ id, label, badge }) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={clsx(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition",
              value === id
                ? "bg-brand text-white shadow-sm"
                : "text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10",
            )}
          >
            {label}
            {badge > 0 && (
              <span
                className={clsx(
                  "grid h-4 min-w-[16px] place-items-center rounded-full px-1 text-[10px] font-semibold leading-none",
                  value === id ? "bg-white/25 text-white" : "bg-red-500 text-white",
                )}
              >
                {badge}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
