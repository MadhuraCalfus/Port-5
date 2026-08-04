// Shared Year → Month → Week/Day navigation helpers for the PM dashboard's
// period pickers (Analytics, Reports) — kept in one place so both pages
// resolve periods identically and match the backend's own period-key
// format exactly (see insights.py's _period_key).
export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// ISO 8601 week numbering — matches the backend's _period_key(), so a week
// picked here resolves to exactly the period the insights/report endpoints
// already key their data by.
export function isoWeekInfo(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
  return { isoYear: d.getUTCFullYear(), week };
}

export function isoWeekKey(date) {
  const { isoYear, week } = isoWeekInfo(date);
  return `${isoYear}-W${String(week).padStart(2, "0")}`;
}

export function mondayOfIsoWeek(isoYear, week) {
  const jan4 = new Date(Date.UTC(isoYear, 0, 4));
  const jan4Day = jan4.getUTCDay() || 7;
  const monday = new Date(jan4);
  monday.setUTCDate(jan4.getUTCDate() - jan4Day + 1 + (week - 1) * 7);
  return monday;
}

// Every distinct ISO week that touches at least one day of this calendar
// month — the dropdown a PM picks a specific week's report/analytics from.
export function weeksInMonth(year, month) {
  const lastDate = new Date(year, month, 0).getDate();
  const byKey = new Map();
  for (let day = 1; day <= lastDate; day++) {
    const { isoYear, week } = isoWeekInfo(new Date(year, month - 1, day));
    const key = `${isoYear}-W${String(week).padStart(2, "0")}`;
    if (!byKey.has(key)) {
      const monday = mondayOfIsoWeek(isoYear, week);
      const sunday = new Date(monday);
      sunday.setUTCDate(monday.getUTCDate() + 6);
      const fmt = (d) => d.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
      byKey.set(key, { key, label: `${fmt(monday)} – ${fmt(sunday)}` });
    }
  }
  return Array.from(byKey.values());
}

export function dayKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

// Every day in this calendar month — the dropdown a PM picks one specific
// day's report/analytics from.
export function daysInMonth(year, month) {
  const lastDate = new Date(year, month, 0).getDate();
  const days = [];
  for (let day = 1; day <= lastDate; day++) {
    const date = new Date(year, month - 1, day);
    days.push({ key: dayKey(date), label: date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) });
  }
  return days;
}

export function yearOptions(count = 5) {
  const current = new Date().getFullYear();
  return Array.from({ length: count }, (_, i) => current - i);
}
