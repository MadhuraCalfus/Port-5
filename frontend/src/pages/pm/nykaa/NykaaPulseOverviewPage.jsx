import { useEffect, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Loader2, RefreshCw } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";
import { NykaaPeriodDateControls, NykaaPeriodTypeToggle, useNykaaPeriodFilter } from "../../../components/NykaaPeriodToggle";

function formatInr(amount) {
  return `₹${Number(amount).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

// Same re-stepped, dataviz-skill-validated sentiment colors as the Mission
// side's Analytics tab (AnalyticsPage.jsx) — duplicated locally rather than
// imported since that module doesn't export them, but the values must stay
// identical so "positive/neutral/negative" reads the same color everywhere
// in this app.
const SENTIMENT_COLORS = { positive: "#2f8f5b", neutral: "#556270", negative: "#c0392b" };
const SENTIMENT_ORDER = ["positive", "neutral", "negative"];

function StatTile({ label, value, sub, tone }) {
  const toneClass =
    tone === "good"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "bad"
        ? "text-red-600 dark:text-red-400"
        : "text-ink dark:text-ink-dark";
  return (
    <Card className="p-3.5">
      <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</p>
      <p className={`mt-1 font-display text-xl font-bold ${toneClass}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{sub}</p>}
    </Card>
  );
}

// One funnel row: a label/count/rate header over a horizontal track+fill
// bar — same track-and-fill anatomy as primitives.jsx's ConfidenceMeter,
// just full-width and sized relative to the funnel's first stage instead of
// a fixed 0-100% confidence value.
function FunnelStage({ label, count, pct, rateLabel }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-ink dark:text-ink-dark">{label}</span>
        <span className="text-ink/60 dark:text-ink-dark/60">
          <span className="font-display font-bold text-ink dark:text-ink-dark">{count.toLocaleString()}</span>
          {rateLabel && <span className="ml-1.5 text-xs">{rateLabel}</span>}
        </span>
      </div>
      <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-black/[0.06] dark:bg-white/[0.08]">
        <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Nykaa Pulse's Overview sub-tab — order/GMV/rating headline numbers, the
// order -> review -> photo -> published drop-off funnel the teardown
// flagged as missing from Nykaa's own PM dashboard, and a quick sentiment
// read over Nykaa Pulse reviews specifically. Same stat-tile/Card/recharts
// conventions as the Mission side's Analytics tab (AnalyticsPage.jsx) — no
// new visual language introduced.
export function NykaaPulseOverviewPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const picker = useNykaaPeriodFilter("all");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.nykaaPmOverview(picker.isAllTime ? undefined : picker.periodType, picker.periodKey));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picker.periodType, picker.periodKey]);

  const sentimentData = data
    ? SENTIMENT_ORDER.filter((k) => data.review_sentiment[k] != null).map((k) => ({ name: k, value: data.review_sentiment[k] }))
    : [];

  const funnel = data?.funnel;
  const ordersPlaced = funnel?.orders_placed ?? 0;
  const pctOf = (n) => (ordersPlaced > 0 ? Math.min(100, (100 * n) / ordersPlaced) : 0);
  const publishedRatePct = ordersPlaced > 0 && funnel ? Math.round((1000 * funnel.published) / ordersPlaced) / 10 : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">Overview</h2>
          <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
            Order volume, review conversion, and delivery satisfaction — the order/catalog-level view the Mission side's
            Analytics tab has no visibility into.
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
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            <StatTile label="Total orders" value={data.total_orders.toLocaleString()} />
            <StatTile label="Order items" value={data.total_order_items.toLocaleString()} />
            <StatTile label="GMV" value={formatInr(data.total_gmv_inr)} />
            <StatTile
              label="Avg product rating"
              value={data.rated_count > 0 ? `★ ${data.avg_rating.toFixed(1)}` : "—"}
              sub={data.rated_count > 0 ? `${data.rated_count} rated` : "Not enough data yet"}
            />
            <StatTile
              label="Avg delivery rating"
              value={data.delivery_rated_count > 0 ? `★ ${data.avg_delivery_rating.toFixed(1)} / 5` : "—"}
              sub={data.delivery_rated_count > 0 ? `${data.delivery_rated_count} rated` : "Not enough data yet"}
            />
            <StatTile
              label="Avg moderation time"
              value={data.avg_moderation_hours != null ? `${data.avg_moderation_hours.toFixed(1)}h` : "—"}
              sub={data.avg_moderation_hours != null ? "submit to decision" : "Not enough data yet"}
            />
            <StatTile label="Tickets linked" value={data.ticket_linked_count.toLocaleString()} sub="raised from an order" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Order → review funnel</h3>
              <p className="mb-4 text-xs text-ink/50 dark:text-ink-dark/50">Where orders drop off before becoming a published review</p>
              {funnel && (
                <div className="space-y-4">
                  <FunnelStage label="Orders placed" count={funnel.orders_placed} pct={100} />
                  <FunnelStage
                    label="Reviewed"
                    count={funnel.reviewed}
                    pct={pctOf(funnel.reviewed)}
                    rateLabel={`${funnel.review_rate_pct}% of orders`}
                  />
                  <FunnelStage
                    label="Photo attached"
                    count={funnel.with_photo}
                    pct={pctOf(funnel.with_photo)}
                    rateLabel={`${funnel.photo_attach_rate_pct}% of orders`}
                  />
                  <FunnelStage label="Published" count={funnel.published} pct={pctOf(funnel.published)} rateLabel={`${publishedRatePct}% of orders`} />
                </div>
              )}
            </Card>

            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Review sentiment</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                {data.review_count} review{data.review_count === 1 ? "" : "s"} analyzed
              </p>
              {sentimentData.length === 0 ? (
                <p className="py-10 text-center text-sm text-ink/50 dark:text-ink-dark/50">No reviews yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                      {sentimentData.map((entry) => (
                        <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? "#556270"} />
                      ))}
                    </Pie>
                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, textTransform: "capitalize" }} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
