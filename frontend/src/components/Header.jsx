import { useState } from "react";
import { LogOut, Star } from "lucide-react";
import clsx from "clsx";
import { BrandMark } from "./BrandMark";
import { SurveyAnswerModal } from "./SurveyAnswerModal";

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

// Name + avatar dropdown (name, role, logout) shared by every dashboard.
// `pendingSurveys`/`onSurveysViewed` are only ever passed by the customer
// (user) dashboard — every other role just gets name/role/logout, since
// only customers receive PM-authored surveys.
export function Header({
  tabs,
  tab,
  onTab,
  health,
  userName,
  roleLabel,
  onLogout,
  pendingSurveys,
  onSurveysViewed,
  onSurveyAnswered,
  menuOpen: menuOpenProp,
  onMenuOpenChange,
}) {
  // Controlled when the parent passes both props (so e.g. a "new survey"
  // toast can open this same menu from outside) — otherwise Header just
  // manages its own open/closed state.
  const [internalMenuOpen, setInternalMenuOpen] = useState(false);
  const menuOpen = onMenuOpenChange ? menuOpenProp : internalMenuOpen;
  const setMenuOpen = onMenuOpenChange ?? setInternalMenuOpen;
  const [answering, setAnswering] = useState(null);
  const surveyCount = pendingSurveys?.length ?? 0;

  function openMenu() {
    setMenuOpen(true);
    onSurveysViewed?.();
  }

  return (
    <header className="border-b border-black/8 dark:border-white/10">
      <div className="container-app flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2.5">
          <BrandMark />
          <div>
            <h1 className="font-display text-base font-semibold leading-tight">NykaaPulse</h1>
            <p className="text-[11px] leading-tight text-ink/50 dark:text-ink-dark/50">Shop, Review, Get Heard.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {health && (
            <span
              className={clsx(
                "hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium sm:inline-flex",
                health.mode === "live"
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "bg-amber-500/10 text-amber-600 dark:text-amber-400",
              )}
              title={health.reason ?? undefined}
            >
              <span className={clsx("h-1.5 w-1.5 rounded-full", health.mode === "live" ? "bg-emerald-500" : "bg-amber-500")} />
              {health.mode === "live" ? `Live · ${health.model}` : "Mock mode (keyword baseline)"}
            </span>
          )}

          {userName && (
            <div className="relative">
              <button
                type="button"
                onClick={() => (menuOpen ? setMenuOpen(false) : openMenu())}
                className="relative grid h-9 w-9 place-items-center rounded-full bg-brand text-xs font-semibold text-white"
                aria-label="Account menu"
              >
                {initials(userName)}
                {surveyCount > 0 && (
                  <span className="absolute -right-1 -top-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-none text-white">
                    {surveyCount}
                  </span>
                )}
              </button>

              {menuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                  <div className="fade-up absolute right-0 z-50 mt-2 w-64 rounded-xl border border-black/8 dark:border-white/10 bg-surface dark:bg-surface-dark p-2 shadow-xl">
                    <div className="px-2.5 py-2">
                      <p className="truncate text-sm font-semibold text-ink dark:text-ink-dark">{userName}</p>
                      {roleLabel && <p className="text-xs text-ink/50 dark:text-ink-dark/50">{roleLabel}</p>}
                    </div>

                    {pendingSurveys && (
                      <>
                        <div className="my-1 border-t border-black/5 dark:border-white/10" />
                        <div className="px-2.5 py-1.5">
                          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
                            <Star size={11} /> Submit Survey
                          </p>
                        </div>
                        {pendingSurveys.length === 0 ? (
                          <p className="px-2.5 pb-1.5 text-xs text-ink/50 dark:text-ink-dark/50">No surveys right now.</p>
                        ) : (
                          <div className="max-h-48 space-y-1 overflow-y-auto overscroll-contain px-1 pb-1">
                            {pendingSurveys.map((s) => (
                              <div key={s.id} className="flex items-center justify-between gap-2 rounded-lg px-1.5 py-1.5 hover:bg-black/[0.03] dark:hover:bg-white/[0.05]">
                                <span className="truncate text-xs text-ink/80 dark:text-ink-dark/80">{s.title}</span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setAnswering(s);
                                    setMenuOpen(false);
                                  }}
                                  className="shrink-0 rounded-lg bg-brand/10 px-2 py-1 text-[11px] font-semibold text-brand dark:text-brand-dim hover:bg-brand/20"
                                >
                                  Submit
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}

                    {onLogout && (
                      <>
                        <div className="my-1 border-t border-black/5 dark:border-white/10" />
                        <button
                          type="button"
                          onClick={onLogout}
                          className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-ink dark:text-ink-dark hover:bg-black/5 dark:hover:bg-white/10"
                        >
                          <LogOut size={15} /> Log out
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {tabs && tabs.length > 0 && (
        <nav className="container-app flex gap-1 overflow-x-auto px-4">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onTab(id)}
              className={clsx(
                "flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition",
                tab === id
                  ? "border-brand text-brand dark:text-brand-dim"
                  : "border-transparent text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark",
              )}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>
      )}

      {answering && (
        <SurveyAnswerModal
          survey={answering}
          onClose={() => setAnswering(null)}
          onAnswered={() => {
            setAnswering(null);
            onSurveyAnswered?.();
          }}
        />
      )}
    </header>
  );
}
