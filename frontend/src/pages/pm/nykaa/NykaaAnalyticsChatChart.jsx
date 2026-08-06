import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Chart rendering only, kept separate from NykaaAnalyticsChatPanel.jsx (the
// chat orchestration) — mirrors the backend split between nykaa_chat_sql.py
// and nykaa_chat_chart.py. Renders whatever normalized {type, points,
// x_label, y_label} spec the backend chat endpoint returns.
const tooltipStyle = { borderRadius: 12, border: "none", fontSize: 12 };
const PIE_COLORS = ["#b8456f", "#d98a9c", "#8a5a76", "#e0b8c4", "#6b3f52", "#c98fa3", "#a34b68", "#f0d0da"];

export function AnalyticsChatChart({ spec }) {
  if (!spec || !spec.points?.length) return null;
  const { type, points, x_label, y_label } = spec;

  return (
    <div className="mt-3 rounded-xl border border-black/5 dark:border-white/10 p-3">
      <ResponsiveContainer width="100%" height={240}>
        {type === "pie" ? (
          <PieChart>
            <Pie data={points} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85} label={(d) => d.name}>
              {points.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, y_label]} />
          </PieChart>
        ) : type === "line" ? (
          <LineChart data={points} margin={{ bottom: 16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, y_label]} />
            <Line type="monotone" dataKey="value" stroke="#b8456f" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        ) : (
          <BarChart data={points} margin={{ bottom: 16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [value, y_label]} />
            <Bar dataKey="value" fill="#b8456f" radius={[6, 6, 0, 0]} barSize={28} />
          </BarChart>
        )}
      </ResponsiveContainer>
      <p className="mt-1 text-center text-[11px] text-ink/40 dark:text-ink-dark/40">
        {x_label} vs {y_label}
      </p>
    </div>
  );
}
