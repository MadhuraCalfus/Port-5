import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { FileDown, Loader2, RefreshCw } from "lucide-react";
import { api } from "../../api";
import { Card } from "../../components/primitives";
import { NykaaPeriodDateControls, NykaaPeriodTypeToggle, useNykaaPeriodFilter } from "../../components/NykaaPeriodToggle";
import { generateSurveyOverviewPdf, generateSurveyReportPdf } from "../../pmReportExport";

const ALL_SURVEYS = "all";

// Same 3-color language as feedback sentiment elsewhere in this app —
// response answers get pooled into positive/neutral/negative regardless of
// which scale size (3/4/5-point) the survey used.
const RESPONSE_TYPE_COLORS = { positive: "#2f8f5b", neutral: "#556270", negative: "#c0392b" };
const RESPONSE_TYPE_ORDER = ["positive", "neutral", "negative"];

function responseTypeChartData(distribution) {
  return RESPONSE_TYPE_ORDER.filter((k) => distribution[k] != null).map((k) => ({ name: k, value: distribution[k] }));
}

// Worst -> Best across the fixed 5-point scale, same red/amber/green
// language as the fixed star-rating chart on the Analytics tab — matches
// the backend's negative (1-2) / neutral (3) / positive (4-5) zones.
function scaleColor(value) {
  if (value <= 2) return "#c0392b";
  if (value === 3) return "#b8860b";
  return "#2f8f5b";
}

export function SurveyAnalyticsPage() {
  const picker = useNykaaPeriodFilter("all");
  const [surveys, setSurveys] = useState(null);
  const [selected, setSelected] = useState(ALL_SURVEYS);
  const [results, setResults] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.pmListSurveys();
      setSurveys(r.surveys.filter((s) => s.status === "sent"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function loadSelected() {
    setLoadingResults(true);
    try {
      const periodType = picker.isAllTime ? undefined : picker.periodType;
      if (selected === ALL_SURVEYS) {
        setOverview(await api.pmSurveysOverview(periodType, picker.periodKey));
      } else {
        setResults(await api.pmSurveyResults(selected, periodType, picker.periodKey));
      }
    } finally {
      setLoadingResults(false);
    }
  }

  useEffect(() => {
    loadSelected();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, picker.periodType, picker.periodKey]);

  const selectedSurvey = useMemo(() => surveys?.find((s) => s.id === selected) ?? null, [surveys, selected]);
  const isAll = selected === ALL_SURVEYS;

  async function refresh() {
    await Promise.all([load(), loadSelected()]);
  }

  async function exportPdf() {
    setExporting(true);
    setError(null);
    try {
      if (isAll && overview) {
        generateSurveyOverviewPdf({ overview });
      } else if (results) {
        generateSurveyReportPdf({ survey: results.survey, results });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">Survey Analytics</h2>
          <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">Results for the surveys you've sent to customers.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <NykaaPeriodDateControls picker={picker} />
          <NykaaPeriodTypeToggle picker={picker} />
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value === ALL_SURVEYS ? ALL_SURVEYS : Number(e.target.value))}
            className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
          >
            <option value={ALL_SURVEYS}>All Surveys</option>
            {(surveys ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading || loadingResults ? "animate-spin" : ""} /> Refresh
          </button>
          <button
            onClick={exportPdf}
            disabled={exporting || (isAll ? !overview : !results)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
          >
            {exporting ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />}
            Export PDF
          </button>
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {!surveys ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading...</Card>
      ) : surveys.length === 0 ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          Nothing sent yet — create and send a survey from the Create Survey tab to see results here.
        </Card>
      ) : loadingResults || (isAll ? !overview : !results) ? (
        <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">Loading results...</Card>
      ) : isAll ? (
        <>
          <Card className="p-4">
            <p className="text-sm text-ink dark:text-ink-dark">{overview.summary}</p>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Surveys sent</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">{overview.total_surveys}</p>
            </Card>
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Total responses</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">{overview.total_responses}</p>
            </Card>
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Customers responded</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">{overview.total_respondents}</p>
            </Card>
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Average score</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">
                {overview.avg_score != null ? `${overview.avg_score.toFixed(1)} / 5` : "—"}
              </p>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Overall response type</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">Every answer across every sent survey, pooled together</p>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={responseTypeChartData(overview.response_distribution)}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={2}
                  >
                    {responseTypeChartData(overview.response_distribution).map((entry) => (
                      <Cell key={entry.name} fill={RESPONSE_TYPE_COLORS[entry.name]} />
                    ))}
                  </Pie>
                  <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, textTransform: "capitalize" }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </Card>

            <Card className="p-5">
              <h3 className="mb-1 text-sm font-semibold">Responses by rating</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">Worst to Best, every answer across every sent survey</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={overview.scale_labels.map((label, idx) => ({ label: `${idx + 1}. ${label}`, value: idx + 1, count: overview.scale_distribution[idx + 1] ?? 0 }))}
                  layout="vertical"
                  margin={{ left: 24, right: 24 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} formatter={(value) => [value, "Responses"]} />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={18}>
                    {overview.scale_labels.map((_, idx) => (
                      <Cell key={idx} fill={scaleColor(idx + 1)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card className="p-5 lg:col-span-2">
              <h3 className="mb-1 text-sm font-semibold">Responses per survey</h3>
              <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">Which surveys customers actually engaged with</p>
              <ResponsiveContainer width="100%" height={Math.max(220, overview.per_survey.length * 34)}>
                <BarChart data={overview.per_survey} layout="vertical" margin={{ left: 24, right: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="title" width={170} tick={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} formatter={(value) => [value, "Responses"]} />
                  <Bar dataKey="response_count" name="Responses" fill="#3d6b96" radius={[0, 6, 6, 0]} barSize={18} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
        </>
      ) : (
        <>
          <Card className="p-4">
            <p className="text-sm text-ink dark:text-ink-dark">{results.summary}</p>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Responses</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">{results.response_count}</p>
            </Card>
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Questions</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">{results.questions.length}</p>
            </Card>
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Average score</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">
                {results.avg_score != null ? `${results.avg_score.toFixed(1)} / 5` : "—"}
              </p>
            </Card>
            <Card className="p-3.5">
              <p className="text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">Sent</p>
              <p className="mt-1 font-display text-xl font-bold text-ink dark:text-ink-dark">
                {results.survey.sent_at ? new Date(results.survey.sent_at).toLocaleDateString() : "—"}
              </p>
            </Card>
          </div>

          {results.response_count === 0 ? (
            <Card className="p-8 text-center text-sm text-ink/50 dark:text-ink-dark/50">
              No responses yet — check back once customers have answered.
            </Card>
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="p-5">
                <h3 className="mb-1 text-sm font-semibold">Overall response type</h3>
                <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">Every answer to this survey, pooled across all its questions</p>
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={responseTypeChartData(results.response_distribution)}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={50}
                      outerRadius={85}
                      paddingAngle={2}
                    >
                      {responseTypeChartData(results.response_distribution).map((entry) => (
                        <Cell key={entry.name} fill={RESPONSE_TYPE_COLORS[entry.name]} />
                      ))}
                    </Pie>
                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, textTransform: "capitalize" }} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>

              {results.questions.map((q, i) => {
                const chartData = results.scale_labels.map((label, idx) => ({
                  label: `${idx + 1}. ${label}`,
                  value: idx + 1,
                  count: q.distribution[idx + 1] ?? 0,
                }));
                return (
                  <Card key={i} className="p-5">
                    <h3 className="mb-1 text-sm font-semibold">{q.question}</h3>
                    <p className="mb-3 text-xs text-ink/50 dark:text-ink-dark/50">
                      {q.avg != null ? `Average: ${q.avg.toFixed(1)} / ${selectedSurvey?.scale_points}` : "No answers yet"}
                    </p>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={chartData} layout="vertical" margin={{ left: 24, right: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.15} />
                        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                        <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 11 }} />
                        <Tooltip contentStyle={{ borderRadius: 12, border: "none", fontSize: 12 }} formatter={(value) => [value, "Responses"]} />
                        <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={18}>
                          {chartData.map((entry) => (
                            <Cell key={entry.value} fill={scaleColor(entry.value)} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
