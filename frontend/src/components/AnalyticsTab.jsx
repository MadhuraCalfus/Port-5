import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { FileDown, RefreshCw } from "lucide-react";
import { api } from "../api";
import { generateAnalyticsPdf } from "../reportPdf";
import { Card } from "./primitives";
import { PeriodPicker, usePeriodPicker } from "./PeriodPicker";

const PRIORITY_COLORS = { High: "#c0392b", Medium: "#b8860b", Low: "#2f8f5b" };
const STATUS_COLORS = { New: "#64748b", Routed: "#3d6b96", "In Progress": "#b8860b", Resolved: "#2f8f5b" };
const STATUS_ORDER = ["New", "Routed", "In Progress", "Resolved"];
const PALETTE = ["#3d6b96", "#7fa8c9", "#9a9a9f", "#c0392b", "#b8860b", "#2f8f5b", "#5a5a5e", "#8a8a8f"];
const RESOLUTION_COLORS = { "Resolved by AI": "#2f8f5b", "Routed to a team": "#3d6b96" };

function toChartData(breakdown) {
  return Object.entries(breakdown).map(([name, value]) => ({ name, value }));
}

function toTimelineData(timeline) {
  return timeline.map((point) => ({
    ...point,
    label: new Date(point.date + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }),
  }));
}

// Status and mode both have a natural priority order (unlike the other
// breakdowns, which are unordered categories) — sort by that instead of
// whatever order the backend's Counter happened to emit.
function toOrderedChartData(breakdown, order, labels) {
  return order
    .filter((name) => breakdown[name] != null)
    .map((name) => ({ name: labels?.[name] ?? name, key: name, value: breakdown[name] }));
}

export function AnalyticsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const picker = usePeriodPicker();

  async function load() {
    setLoading(true);
    try {
      setData(await api.analytics(picker.periodType, picker.periodKey));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picker.periodType, picker.periodKey]);

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="font-display text-lg font-semibold">Analytics</h2>
      <div className="flex flex-wrap items-center gap-2">
        <PeriodPicker picker={picker} />
        {data && (
          <button
            onClick={() => generateAnalyticsPdf(data)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <FileDown size={13} /> Export PDF
          </button>
        )}
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>
    </div>
  );

  if (!data) {
    return (
      <div className="space-y-6">
        {header}
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading analytics...</Card>
      </div>
    );
  }

  if (data.total_tickets === 0 && data.self_resolved_count === 0) {
    return (
      <div className="space-y-6">
        {header}
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          No tickets routed yet for this period — try a different period, or the "Route a Ticket"/"Demo" tab first.
        </Card>
      </div>
    );
  }

  const resolutionSplit = [
    { name: "Resolved by AI", value: data.self_resolved_count },
    { name: "Routed to a team", value: data.total_tickets },
  ];

  return (
    <div className="space-y-6">
      {header}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard label="Tickets routed" value={String(data.total_tickets)} />
        <StatCard
          label="Resolved by AI"
          value={String(data.self_resolved_count)}
          sub={data.self_resolved_count > 0 ? "no ticket raised" : "none yet"}
        />
        <StatCard label="Avg. AI time" value={`${(data.avg_ai_latency_ms / 1000).toFixed(2)}s`} sub={`per ticket (${data.avg_ai_latency_ms.toFixed(0)}ms)`} />
        <StatCard label="Avg. manual time" value={`${data.avg_manual_seconds.toFixed(0)}s`} sub={data.measured_manual_count > 0 ? `${data.measured_manual_count} measured` : "assumed baseline"} />
        <StatCard
          label="Time saved"
          value={`${data.time_saved_pct.toFixed(0)}%`}
          sub={`~${Math.round(data.total_time_saved_seconds / 60)} min total · ${
            data.measured_manual_count === 0
              ? "estimated"
              : data.measured_manual_count < data.total_tickets
                ? `${data.measured_manual_count}/${data.total_tickets} measured`
                : "measured"
          }`}
          highlight
        />
      </div>

      {(data.self_resolved_count > 0 || data.total_tickets > 0) && (
        <div className="rounded-xl bg-brand/10 p-4 text-center">
          <div className="font-display text-2xl font-bold text-brand dark:text-brand-dim">{data.deflection_rate_pct.toFixed(0)}%</div>
          <div className="text-xs text-ink/50 dark:text-ink-dark/50">
            of all issues raised were resolved by AI before ever becoming a ticket ({data.self_resolved_count} of{" "}
            {data.self_resolved_count + data.total_tickets})
          </div>
        </div>
      )}

      {data.timeline.length > 1 && (
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Tickets generated over time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={toTimelineData(data.timeline)} margin={{ left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ""}
              />
              <Line type="monotone" dataKey="count" name="Tickets" stroke="#3d6b96" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Status breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={toOrderedChartData(data.status_breakdown, STATUS_ORDER)}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={2}
              >
                {toOrderedChartData(data.status_breakdown, STATUS_ORDER).map((entry) => (
                  <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#3d6b96"} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Priority breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={toChartData(data.priority_breakdown)}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={2}
              >
                {toChartData(data.priority_breakdown).map((entry) => (
                  <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name] ?? "#3d6b96"} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Category breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={toChartData(data.category_breakdown)} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {toChartData(data.category_breakdown).map((entry, i) => (
                  <Cell key={entry.name} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Team assignment</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={toChartData(data.team_breakdown)} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]} fill="#3d6b96" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Customer tone detected</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={toChartData(data.tone_breakdown)}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis hide />
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} fill="#7fa8c9" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">AI-resolved vs. routed tickets</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={resolutionSplit}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={2}
              >
                {resolutionSplit.map((entry) => (
                  <Cell key={entry.name} fill={RESOLUTION_COLORS[entry.name] ?? "#3d6b96"} />
                ))}
              </Pie>
              <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

      </div>

    </div>
  );
}

function StatCard({ label, value, sub, highlight }) {
  return (
    <Card className={`p-4 text-center ${highlight ? "ring-2 ring-brand/40" : ""}`}>
      <div className={`font-display text-2xl font-bold ${highlight ? "text-brand dark:text-brand-dim" : ""}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{sub}</div>}
    </Card>
  );
}
