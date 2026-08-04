import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

function breakdownRows(breakdown) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  return Object.entries(breakdown)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => [name, String(count), total ? `${Math.round((100 * count) / total)}%` : "0%"]);
}

export function generateAnalyticsPdf(data) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();

  doc.setFontSize(18);
  doc.text("NykaaPulse — Analytics Report", 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Generated ${generatedAt}`, 14, 25);
  doc.setTextColor(0);

  autoTable(doc, {
    startY: 32,
    head: [["Metric", "Value"]],
    body: [
      ["Tickets routed", String(data.total_tickets)],
      ["Avg. AI time per ticket", `${data.avg_ai_latency_ms.toFixed(0)}ms`],
      [
        "Avg. manual time per ticket",
        `${data.avg_manual_seconds.toFixed(0)}s (${data.measured_manual_count > 0 ? `${data.measured_manual_count} measured` : "assumed baseline"})`,
      ],
      [
        "Total time saved",
        `${Math.round(data.total_time_saved_seconds / 60)} min (${data.time_saved_pct.toFixed(0)}%) — ${
          data.measured_manual_count === 0
            ? "estimated"
            : data.measured_manual_count < data.total_tickets
              ? `${data.measured_manual_count}/${data.total_tickets} measured`
              : "measured"
        }`,
      ],
      ["Flagged ambiguous", String(data.ambiguous_count)],
      ["Priority escalated (tone-triggered)", String(data.escalated_count)],
      ["Reviewed by a human", String(data.feedback_count)],
      ["Human/AI agreement rate", data.agreement_rate === null ? "no feedback yet" : `${data.agreement_rate.toFixed(0)}%`],
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  const sections = [
    ["Status breakdown", data.status_breakdown],
    ["Category breakdown", data.category_breakdown],
    ["Priority breakdown", data.priority_breakdown],
    ["Team assignment", data.team_breakdown],
    ["Customer tone detected", data.tone_breakdown],
    ["AI mode breakdown", data.mode_breakdown],
  ];

  for (const [title, breakdown] of sections) {
    const prevY = doc.lastAutoTable ? doc.lastAutoTable.finalY : 32;
    autoTable(doc, {
      startY: prevY + 10,
      head: [[title, "Count", "Share"]],
      body: breakdownRows(breakdown),
      styles: { fontSize: 10 },
      headStyles: { fillColor: [61, 107, 150] },
    });
  }

  doc.save(`nykaapulse-analytics-${new Date().toISOString().slice(0, 10)}.pdf`);
}

export function generateTeamsPdf(teams) {
  const doc = new jsPDF();
  const generatedAt = new Date().toLocaleString();

  doc.setFontSize(18);
  doc.text("NykaaPulse — Teams Report", 14, 18);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Generated ${generatedAt}`, 14, 25);
  doc.setTextColor(0);

  const totals = teams.reduce(
    (acc, t) => ({
      total: acc.total + t.total,
      assigned: acc.assigned + t.assigned,
      in_progress: acc.in_progress + t.in_progress,
      resolved: acc.resolved + t.resolved,
    }),
    { total: 0, assigned: 0, in_progress: 0, resolved: 0 },
  );

  autoTable(doc, {
    startY: 32,
    head: [["Metric", "Value"]],
    body: [
      ["Total tickets", String(totals.total)],
      ["Assigned (not yet started)", String(totals.assigned)],
      ["In progress", String(totals.in_progress)],
      ["Resolved", String(totals.resolved)],
    ],
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  autoTable(doc, {
    startY: doc.lastAutoTable.finalY + 10,
    head: [["Team", "Total", "Assigned", "In Progress", "Resolved"]],
    body: teams.map((t) => [t.team, String(t.total), String(t.assigned), String(t.in_progress), String(t.resolved)]),
    styles: { fontSize: 10 },
    headStyles: { fillColor: [61, 107, 150] },
  });

  doc.save(`nykaapulse-teams-${new Date().toISOString().slice(0, 10)}.pdf`);
}
