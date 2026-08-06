import { createPortal } from "react-dom";
import clsx from "clsx";
import { AlertCircle, AlertTriangle, Check, Frown, HelpCircle, Meh, Smile, X, Zap as ZapIcon } from "lucide-react";

export function Card({ className, children }) {
  return (
    <div
      className={clsx(
        "rounded-2xl border border-black/8 dark:border-white/10 bg-surface dark:bg-surface-dark shadow-sm shadow-black/[0.03] dark:shadow-black/20",
        className,
      )}
    >
      {children}
    </div>
  );
}

const PRIORITY_STYLES = {
  High: "bg-red-500/10 text-red-600 dark:text-red-400 ring-1 ring-red-500/30",
  Medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400 ring-1 ring-amber-500/30",
  Low: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-1 ring-emerald-500/30",
};

export function PriorityBadge({ priority, escalated }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold",
        PRIORITY_STYLES[priority],
      )}
    >
      {priority === "High" && <span className="h-1.5 w-1.5 rounded-full bg-red-500 pulse-ring" />}
      {priority}
      {escalated && <span title="Priority escalated due to detected tone">↑</span>}
    </span>
  );
}

const TONE_STYLES = {
  neutral: { icon: Meh, className: "bg-slate-500/10 text-slate-600 dark:text-slate-300" },
  frustrated: { icon: Frown, className: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
  angry: { icon: AlertTriangle, className: "bg-red-500/10 text-red-600 dark:text-red-400" },
  urgent: { icon: ZapIcon, className: "bg-purple-500/10 text-purple-600 dark:text-purple-400" },
  confused: { icon: HelpCircle, className: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  worried: { icon: AlertCircle, className: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  positive: { icon: Smile, className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
};

export function ToneBadge({ tone }) {
  const s = TONE_STYLES[tone] ?? TONE_STYLES.neutral;
  const Icon = s.icon;
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium capitalize", s.className)}>
      <Icon size={12} />
      {tone}
    </span>
  );
}

export function CategoryPill({ children }) {
  return (
    <span className="inline-flex items-center rounded-full bg-brand/10 px-2.5 py-1 text-xs font-semibold text-brand dark:text-brand-dim">
      {children}
    </span>
  );
}

export function ConfidenceMeter({ value, ambiguous }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "bg-emerald-500" : pct >= 45 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <div className={clsx("h-full rounded-full transition-all duration-500", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium tabular-nums text-ink/70 dark:text-ink-dark/70">{pct}%</span>
      {ambiguous && (
        <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
          ambiguous
        </span>
      )}
    </div>
  );
}

export function ModePill({ mode, model }) {
  const label = {
    live: model ? `${model} (live)` : "Live",
    mock: "Keyword baseline",
    repaired: model ? `${model} (self-repaired JSON)` : "Self-repaired JSON",
    fallback: "Fallback baseline",
  };
  const style = {
    live: "bg-brand/10 text-brand dark:text-brand-dim",
    mock: "bg-slate-500/10 text-slate-500 dark:text-slate-300",
    repaired: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    fallback: "bg-red-500/10 text-red-500",
  };
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", style[mode] ?? style.mock)}>
      {label[mode] ?? mode}
    </span>
  );
}

const STATUS_STYLES = {
  New: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
  Routed: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  "In Progress": "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  Resolved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
};

export function StatusBadge({ status }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold", STATUS_STYLES[status] ?? STATUS_STYLES.New)}>
      {status}
    </span>
  );
}

const STATUS_STEPS = ["New", "Routed", "In Progress", "Resolved"];

export function StatusStepper({ status, labels = STATUS_STEPS }) {
  const current = STATUS_STEPS.indexOf(status);
  return (
    <div className="flex items-start">
      {STATUS_STEPS.map((step, i) => {
        const done = i < current;
        const isCurrent = i === current;
        return (
          <div key={step} className="flex items-start">
            <div className="flex flex-col items-center">
              <div
                className={clsx(
                  "grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10px] font-bold",
                  done && "bg-emerald-500 text-white",
                  isCurrent && "bg-brand text-white ring-4 ring-brand/15",
                  !done && !isCurrent && "bg-black/8 dark:bg-white/10 text-ink/40 dark:text-ink-dark/40",
                )}
                title={step}
              >
                {done ? <Check size={13} /> : i + 1}
              </div>
              <span
                className={clsx(
                  "mt-1 w-14 text-center text-[10px] leading-tight",
                  isCurrent ? "font-semibold text-brand dark:text-brand-dim" : "text-ink/40 dark:text-ink-dark/40",
                )}
              >
                {labels[i]}
              </span>
            </div>
            {i < STATUS_STEPS.length - 1 && (
              <div className={clsx("mt-3 h-0.5 w-4 shrink-0 sm:w-7", done ? "bg-emerald-500" : "bg-black/8 dark:bg-white/10")} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Toast({ message, onClick }) {
  if (!message) return null;
  return (
    <div
      onClick={onClick}
      className={clsx(
        "fade-up fixed bottom-6 right-6 z-50 rounded-xl bg-ink dark:bg-ink-dark px-4 py-3 text-sm font-medium text-ink-dark dark:text-ink shadow-lg shadow-black/20",
        onClick && "cursor-pointer",
      )}
    >
      {message}
    </div>
  );
}

// Portaled to document.body — a Modal opened from inside a SlideOver (whose
// sliding panel keeps a non-none `transform` from its own animation, even
// after that animation finishes) would otherwise become a descendant of an
// element that establishes a containing block for `position: fixed`,
// confining the "centered over everything" dialog to that panel's bounds
// instead of the viewport. Rendering outside the React tree's DOM position
// sidesteps that entirely, regardless of how deeply nested the caller is.
export function Modal({ title, onClose, children }) {
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="fade-up thin-scroll max-h-[90vh] w-full max-w-2xl overflow-y-auto overscroll-contain rounded-2xl border border-black/8 dark:border-white/10 bg-surface dark:bg-surface-dark p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-display text-base font-semibold text-ink dark:text-ink-dark">{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-7 w-7 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

// Right-anchored panel — the "Bag" slide-over pattern real e-commerce sites
// use for cart/account/orders, vs. Modal's centered dialog for one-off forms.
// Portaled to document.body for the same reason Modal is (see its comment) —
// a SlideOver nested inside another SlideOver's already-animated panel would
// otherwise render confined to it instead of the full viewport. `overscroll-
// contain` stops this panel's own scroll from chaining into the page
// scrolling behind it once the panel hits its top/bottom edge.
export function SlideOver({ title, onClose, children, widthClassName = "max-w-md" }) {
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className={clsx(
          "slide-in-right thin-scroll h-full w-full overflow-y-auto overscroll-contain border-l border-black/8 dark:border-white/10 bg-surface dark:bg-surface-dark p-5 shadow-xl",
          widthClassName,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-display text-base font-semibold text-ink dark:text-ink-dark">{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function Button({ children, className, variant = "primary", ...rest }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:opacity-40 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-brand text-white hover:opacity-90 active:scale-[0.98] shadow-sm shadow-brand/30",
    ghost: "bg-black/5 dark:bg-white/10 text-ink dark:text-ink-dark hover:bg-black/10 dark:hover:bg-white/15",
    danger: "bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-500/20",
  };
  return (
    <button className={clsx(base, variants[variant], className)} {...rest}>
      {children}
    </button>
  );
}
