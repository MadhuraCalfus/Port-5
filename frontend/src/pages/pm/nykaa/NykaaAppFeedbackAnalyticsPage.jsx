import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";
import { NykaaPeriodDateControls, NykaaPeriodTypeToggle, useNykaaPeriodFilter } from "../../../components/NykaaPeriodToggle";

function StatTile({ label, value }) {
  return (
    <Card className="p-3.5">
      <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</p>
      <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">{value}</p>
    </Card>
  );
}

// Same track-and-fill bar anatomy as NykaaPulseOverviewPage.jsx's
// FunnelStage — no new visual language introduced for this tab.
function BarRow({ label, count, max }) {
  const pct = max > 0 ? (100 * count) / max : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-ink dark:text-ink-dark">{label}</span>
        <span className="font-display font-bold text-ink dark:text-ink-dark">{count.toLocaleString()}</span>
      </div>
      <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-black/[0.06] dark:bg-white/[0.08]">
        <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Analytics-only view of the app-feedback widget's submissions — rating
// distribution + issue-category counts, deliberately no raw feedback list.
export function NykaaAppFeedbackAnalyticsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const picker = useNykaaPeriodFilter("all");

  function load() {
    setLoading(true);
    setError(null);
    api
      .nykaaPmAppFeedbackAnalytics(picker.isAllTime ? undefined : picker.periodType, picker.periodKey)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picker.periodType, picker.periodKey]);

  const ratingRows = data ? [5, 4, 3, 2, 1].map((r) => ({ rating: r, count: data.rating_distribution[r] || 0 })) : [];
  const maxRating = Math.max(1, ...ratingRows.map((r) => r.count));
  const maxCategory = data && data.category_breakdown.length ? Math.max(...data.category_breakdown.map((c) => c.count)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">App Feedback</h2>
          <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
            Ratings and issue categories from the shop's floating feedback widget.
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <NykaaPeriodDateControls picker={picker} />
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <NykaaPeriodTypeToggle picker={picker} className="ml-auto" />
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {!data ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          {loading ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 size={16} className="animate-spin" /> Loading...
            </span>
          ) : (
            "No data yet."
          )}
        </Card>
      ) : data.total === 0 ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          {picker.isAllTime ? "No app feedback submitted yet." : "No app feedback in this period."}
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:w-1/2">
            <StatTile label="Total feedback" value={data.total.toLocaleString()} />
            <StatTile label="Avg rating" value={`★ ${data.avg_rating.toFixed(1)} / 5`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-4 text-sm font-semibold">Rating distribution</h3>
              <div className="space-y-4">
                {ratingRows.map((r) => (
                  <BarRow key={r.rating} label={`${r.rating}★`} count={r.count} max={maxRating} />
                ))}
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="mb-4 text-sm font-semibold">Issue categories</h3>
              <div className="space-y-4">
                {data.category_breakdown.map((c) => (
                  <BarRow key={c.category} label={c.category} count={c.count} max={maxCategory} />
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
