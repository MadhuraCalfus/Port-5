import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RefreshCw } from "lucide-react";
import { api } from "../../../api";
import { Card } from "../../../components/primitives";

// Same recharts set/layout as the existing project's AnalyticsTab.jsx, over
// np_tickets instead — no "New" status (np_tickets are born already-routed)
// and no AI-vs-manual time-saved economics (there's no hand-routed baseline
// for Nykaa Pulse tickets to compare against).
const PRIORITY_COLORS = { High: "#c0392b", Medium: "#b8860b", Low: "#2f8f5b" };
const STATUS_COLORS = { Routed: "#64748b", "In Progress": "#b8860b", Resolved: "#2f8f5b" };
const STATUS_ORDER = ["Routed", "In Progress", "Resolved"];
const PALETTE = ["#d6588c", "#f2a6c6", "#9a9a9f", "#c0392b", "#b8860b", "#2f8f5b", "#5a5a5e", "#8a8a8f"];
const RESOLUTION_COLORS = { "Resolved by AI": "#2f8f5b", "Routed to a team": "#d6588c" };

function toChartData(breakdown) {
  return Object.entries(breakdown).map(([name, value]) => ({ name, value }));
}

function toOrderedChartData(breakdown, order) {
  return order.filter((name) => breakdown[name] != null).map((name) => ({ name, value: breakdown[name] }));
}

function toTimelineData(timeline) {
  return timeline.map((point) => ({
    ...point,
    label: new Date(point.date + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }),
  }));
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

export function NykaaAnalyticsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await api.nykaaAdminAnalytics());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (!data) {
    return <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading analytics...</Card>;
  }

  if (data.total_tickets === 0 && data.self_resolved_count === 0) {
    return (
      <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
        No Nykaa Pulse tickets or AI-resolved chats yet — come back once customers have raised a few.
      </Card>
    );
  }

  const resolutionSplit = [
    { name: "Resolved by AI", value: data.self_resolved_count },
    { name: "Routed to a team", value: data.total_tickets },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold">Nykaa Pulse Analytics</h2>
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Tickets routed" value={String(data.total_tickets)} />
        <StatCard label="Resolved by AI" value={String(data.self_resolved_count)} sub={data.self_resolved_count > 0 ? "no ticket raised" : "none yet"} />
        <StatCard label="Deflection rate" value={`${data.deflection_rate_pct.toFixed(0)}%`} sub="resolved before a ticket existed" highlight />
      </div>

      {data.timeline.length > 1 && (
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Tickets over time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={toTimelineData(data.timeline)} margin={{ left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ""} />
              <Line type="monotone" dataKey="count" name="Tickets" stroke="#d6588c" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Status breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={toOrderedChartData(data.status_breakdown, STATUS_ORDER)} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                {toOrderedChartData(data.status_breakdown, STATUS_ORDER).map((entry) => (
                  <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#d6588c"} />
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
              <Pie data={toChartData(data.priority_breakdown)} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                {toChartData(data.priority_breakdown).map((entry) => (
                  <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name] ?? "#d6588c"} />
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
              <Bar dataKey="value" radius={[0, 6, 6, 0]} fill="#d6588c" />
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
              <Bar dataKey="value" radius={[6, 6, 0, 0]} fill="#f2a6c6" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold">AI-resolved vs. routed</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={resolutionSplit} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                {resolutionSplit.map((entry) => (
                  <Cell key={entry.name} fill={RESOLUTION_COLORS[entry.name] ?? "#d6588c"} />
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
