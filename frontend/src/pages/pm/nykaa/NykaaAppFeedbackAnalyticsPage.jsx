import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";

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

  useEffect(() => {
    setLoading(true);
    api
      .nykaaPmAppFeedbackAnalytics()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const ratingRows = data ? [5, 4, 3, 2, 1].map((r) => ({ rating: r, count: data.rating_distribution[r] || 0 })) : [];
  const maxRating = Math.max(1, ...ratingRows.map((r) => r.count));
  const maxCategory = data && data.category_breakdown.length ? Math.max(...data.category_breakdown.map((c) => c.count)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-semibold">App Feedback</h2>
        <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
          Ratings and issue categories from the shop's floating feedback widget.
        </p>
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
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">No app feedback submitted yet.</Card>
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
