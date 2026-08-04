import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

// Every narrative field is a list of short bullet points (see
// models.NarrativeReport) — rendered as one row per bullet rather than
// wrapped paragraph text, matching how "Suggested actions" already renders.
function bulletRows(points) {
  return (points ?? []).map((line) => [`•  ${line}`]);
}

export function generatePmReportPdf({ periodType, report, trend, actions, items }) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();

  doc.setFontSize(18);
  doc.text(`NykaaPulse — ${periodType[0].toUpperCase() + periodType.slice(1)} Insight Report`, 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Generated ${generatedAt} · ${report.period_start} to ${report.period_end}`, 14, 25);
  doc.setTextColor(0);

  autoTable(doc, {
    startY: 32,
    head: [["Summary"]],
    body: bulletRows(report.narrative.narrative),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 6,
    head: [["What went well"]],
    body: bulletRows(report.narrative.whats_going_well),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [47, 143, 91] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 6,
    head: [["Top pain point"]],
    body: bulletRows(report.narrative.top_pain_point),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [192, 57, 43] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 6,
    head: [["Recommendation"]],
    body: bulletRows(report.narrative.recommendation),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  // trend.current is the same aggregate shape compute_period_insights
  // returns for the Analytics export — reused here so this report is
  // self-contained (total feedback/survey/sentiment/urgency/rating at a
  // glance) without needing to cross-reference the Analytics PDF.
  const current = trend.current;
  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["This period at a glance", "Value", "vs. previous"]],
    body: [
      ["Total feedback", String(current.total_items), `${trend.total_items_delta >= 0 ? "+" : ""}${trend.total_items_delta}`],
      ["Avg. sentiment", current.avg_sentiment_score.toFixed(2), `${trend.avg_sentiment_score_delta >= 0 ? "+" : ""}${trend.avg_sentiment_score_delta.toFixed(2)}`],
      ["Avg. urgency", current.avg_urgency_score.toFixed(2), `${trend.avg_urgency_score_delta >= 0 ? "+" : ""}${trend.avg_urgency_score_delta.toFixed(2)}`],
      ["Needs follow-up", String(current.actionable_count), ""],
      ["Avg. survey rating", current.avg_rating != null ? `${current.avg_rating.toFixed(1)} / 5 (${current.rated_count} rated)` : "No surveys this period", ""],
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  if (actions.length > 0) {
    autoTable(doc, {
      startY: doc.lastAutoTable.finalY + 10,
      head: [["Suggested actions"]],
      body: actions.map((a) => [a.action_text]),
      styles: { fontSize: 9 },
      headStyles: { fillColor: [61, 107, 150] },
    });
  }

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["Source", "Text", "Sentiment", "Category", "Urgency", "Actionable", "Date"]],
    body: items.map((i) => [
      i.source_type,
      i.text.length > 60 ? `${i.text.slice(0, 60)}…` : i.text,
      `${i.sentiment_label} (${i.sentiment_score >= 0 ? "+" : ""}${i.sentiment_score.toFixed(1)})`,
      i.category,
      `${Math.round(i.urgency_score * 100)}%`,
      i.is_actionable_ticket ? "Yes" : "No",
      i.created_at.slice(0, 10),
    ]),
    styles: { fontSize: 8 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  doc.save(`nykaapulse-${periodType}-insight-${report.period_start}.pdf`);
}

// Nykaa Pulse's weekly/monthly/yearly brand report has no PDF export today
// (see NykaaPulseWeeklyReportPage.jsx) — this mirrors generatePmReportPdf's
// bullet-point layout, minus the actions/raw-items tables that page doesn't
// have data for (its report is computed fresh per GET, not a persisted
// report + separate actions/items endpoints like the Mission side).
export function generateNykaaReportPdf({ periodType, periodLabel, report, trend }) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();

  doc.setFontSize(18);
  doc.text(`Nykaa Pulse — ${periodType[0].toUpperCase() + periodType.slice(1)} Brand Insight Report`, 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Generated ${generatedAt} · ${periodLabel}`, 14, 25);
  doc.setTextColor(0);

  autoTable(doc, {
    startY: 32,
    head: [["Summary"]],
    body: bulletRows(report.narrative),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 6,
    head: [["What went well"]],
    body: bulletRows(report.whats_going_well),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [47, 143, 91] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 6,
    head: [["Top pain point"]],
    body: bulletRows(report.top_pain_point),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [192, 57, 43] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 6,
    head: [["Recommendation"]],
    body: bulletRows(report.recommendation),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  const current = trend.current;
  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["This period at a glance", "Value"]],
    body: [
      ["Total reviews", String(current.total_items)],
      ["Positive", String(current.sentiment_distribution.positive ?? 0)],
      ["Negative", String(current.sentiment_distribution.negative ?? 0)],
      ["Neutral", String(current.sentiment_distribution.neutral ?? 0)],
      ["Needs follow-up", String(current.actionable_count)],
      ["Avg. urgency", `${Math.round(current.avg_urgency_score * 100)}%`],
      ...(current.rated_count > 0 ? [["Avg. rating", `${current.avg_rating.toFixed(1)} / 5 (${current.rated_count} rated)`]] : []),
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  doc.save(`nykaa-pulse-${periodType}-brand-report.pdf`);
}

export function generateAnalyticsExportPdf({ periodType, insights, trend }) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();
  const title = periodType === "custom" ? "Custom Range Analytics" : `${periodType[0].toUpperCase() + periodType.slice(1)} Analytics`;

  doc.setFontSize(18);
  doc.text(`NykaaPulse — ${title}`, 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Generated ${generatedAt} · ${insights.period_start} to ${insights.period_end}`, 14, 25);
  doc.setTextColor(0);

  // trend (period-over-period deltas) doesn't exist for a custom date
  // range — there's no well-defined "previous range" to compare against —
  // so the metrics table drops that column entirely rather than showing
  // blanks, and the category-trend table below is skipped altogether.
  autoTable(doc, {
    startY: 32,
    head: trend ? [["Metric", "This period", "vs. previous"]] : [["Metric", "This period"]],
    body: [
      trend
        ? ["Total feedback", String(insights.total_items), `${trend.total_items_delta >= 0 ? "+" : ""}${trend.total_items_delta}`]
        : ["Total feedback", String(insights.total_items)],
      trend
        ? ["Avg. sentiment", insights.avg_sentiment_score.toFixed(2), `${trend.avg_sentiment_score_delta >= 0 ? "+" : ""}${trend.avg_sentiment_score_delta.toFixed(2)}`]
        : ["Avg. sentiment", insights.avg_sentiment_score.toFixed(2)],
      trend
        ? ["Avg. urgency", insights.avg_urgency_score.toFixed(2), `${trend.avg_urgency_score_delta >= 0 ? "+" : ""}${trend.avg_urgency_score_delta.toFixed(2)}`]
        : ["Avg. urgency", insights.avg_urgency_score.toFixed(2)],
      trend ? ["Needs follow-up", String(insights.actionable_count), ""] : ["Needs follow-up", String(insights.actionable_count)],
      [
        "Avg. survey rating",
        insights.avg_rating != null ? `${insights.avg_rating.toFixed(1)} / 5 (${insights.rated_count} rated)` : "No surveys this period",
        ...(trend ? [""] : []),
      ],
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["Sentiment", "Count"]],
    body: Object.entries(insights.sentiment_distribution).map(([label, count]) => [label, String(count)]),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["Category", "Mentions", "Avg. urgency", "Avg. sentiment"]],
    body: insights.category_urgency_ranking.map((t) => [t.category, String(t.count), `${Math.round(t.avg_urgency_score * 100)}%`, t.avg_sentiment_score.toFixed(2)]),
    styles: { fontSize: 9 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  if (trend) {
    autoTable(doc, {
      startY: doc.lastAutoTable.finalY + 10,
      head: [["Category", "This period", "Previous", "Change"]],
      body: trend.category_deltas.map((d) => [
        d.category,
        String(d.current_count),
        String(d.previous_count),
        d.direction === "new" ? "New" : d.direction === "resolved" ? "Dropped off" : d.direction === "flat" ? "No change" : `${d.delta_pct > 0 ? "+" : ""}${d.delta_pct}%`,
      ]),
      styles: { fontSize: 9 },
      headStyles: { fillColor: [61, 107, 150] },
    });
  }

  doc.save(`nykaapulse-${periodType}-analytics-${insights.period_start}.pdf`);
}

export function generateSurveyReportPdf({ survey, results }) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();

  doc.setFontSize(18);
  doc.text(doc.splitTextToSize(`NykaaPulse — Survey Report: ${survey.title}`, 180), 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(
    `Generated ${generatedAt} · Sent ${survey.sent_at ? new Date(survey.sent_at).toLocaleDateString() : "—"}`,
    14,
    30,
  );
  doc.setTextColor(0);

  doc.setFontSize(11);
  const summaryLines = doc.splitTextToSize(results.summary, 180);
  doc.text(summaryLines, 14, 40);
  const afterSummaryY = 40 + summaryLines.length * 5.5;

  autoTable(doc, {
    startY: afterSummaryY + 4,
    head: [["Metric", "Value"]],
    body: [
      ["Responses", String(results.response_count)],
      ["Questions", String(results.questions.length)],
      ["Average score", results.avg_score != null ? `${results.avg_score.toFixed(1)} / 5` : "—"],
      ["Scale", `${survey.scale_points}-point (${results.scale_labels.join(" -> ")})`],
      [
        "Overall response type",
        `Positive ${results.response_distribution.positive} · Neutral ${results.response_distribution.neutral} · Negative ${results.response_distribution.negative}`,
      ],
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  results.questions.forEach((q, i) => {
    autoTable(doc, {
      startY: doc.lastAutoTable.finalY + 10,
      head: [[`Q${i + 1}. ${q.question}`, "Responses"]],
      body:
        results.response_count > 0
          ? results.scale_labels.map((label, idx) => [`${idx + 1}. ${label}`, String(q.distribution[idx + 1] ?? 0)])
          : [[{ content: "No responses yet.", colSpan: 2, styles: { halign: "center" } }]],
      styles: { fontSize: 9 },
      headStyles: { fillColor: [61, 107, 150] },
      foot: q.avg != null ? [["Average", `${q.avg.toFixed(1)} / ${survey.scale_points}`]] : [],
      footStyles: { fillColor: [240, 239, 236], textColor: [11, 11, 11] },
    });
  });

  doc.save(`nykaapulse-survey-${survey.id}-report.pdf`);
}

export function generateSurveyOverviewPdf({ overview }) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();

  doc.setFontSize(18);
  doc.text("NykaaPulse — All Surveys Overview", 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Generated ${generatedAt}`, 14, 25);
  doc.setTextColor(0);

  doc.setFontSize(11);
  const summaryLines = doc.splitTextToSize(overview.summary, 180);
  doc.text(summaryLines, 14, 35);
  const afterSummaryY = 35 + summaryLines.length * 5.5;

  autoTable(doc, {
    startY: afterSummaryY + 4,
    head: [["Metric", "Value"]],
    body: [
      ["Surveys sent", String(overview.total_surveys)],
      ["Total responses", String(overview.total_responses)],
      ["Customers responded", String(overview.total_respondents)],
      ["Average score", overview.avg_score != null ? `${overview.avg_score.toFixed(1)} / 5` : "—"],
      [
        "Overall response type",
        `Positive ${overview.response_distribution.positive} · Neutral ${overview.response_distribution.neutral} · Negative ${overview.response_distribution.negative}`,
      ],
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["Rating", "Responses"]],
    body: overview.scale_labels.map((label, idx) => [`${idx + 1}. ${label}`, String(overview.scale_distribution[idx + 1] ?? 0)]),
    styles: { fontSize: 9 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["Survey", "Scale", "Responses"]],
    body:
      overview.per_survey.length > 0
        ? overview.per_survey.map((s) => [s.title, `${s.scale_points}-point`, String(s.response_count)])
        : [[{ content: "No surveys sent yet.", colSpan: 3, styles: { halign: "center" } }]],
    styles: { fontSize: 9 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  doc.save("nykaapulse-surveys-overview.pdf");
}
