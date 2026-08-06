import { useEffect, useMemo, useState } from "react";
import { MONTHS, dayKey, daysInMonth, isoWeekKey, mondayOfIsoWeek, weeksInMonth, yearOptions } from "../periodNav";

// All time/Daily/Weekly/Monthly/Yearly — the one period toggle shared by
// every Nykaa Pulse PM tab (Overview, All Feedback, Analytics, App
// Feedback, Delivery Feedback) so it behaves identically everywhere
// instead of five slightly-different copies. Deliberately separate from
// components/PeriodPicker.jsx's usePeriodPicker/PeriodPicker — that one has
// no "All time"/"Daily" and backs a different picker (Admin's Nykaa
// analytics, TicketTrident's own Analytics tab).
export const NYKAA_PERIOD_TYPES = [
  { id: "all", label: "All time" },
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

export function useNykaaPeriodFilter(defaultType = "all") {
  const [periodType, setPeriodType] = useState(defaultType);
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedWeekKey, setSelectedWeekKey] = useState(() => isoWeekKey(new Date()));
  const [selectedDayKey, setSelectedDayKey] = useState(() => dayKey(new Date()));

  const yearOptionsList = useMemo(() => yearOptions(), []);
  const weekOptions = useMemo(() => weeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);
  const dayOptions = useMemo(() => daysInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);

  // Keep the selected week/day valid whenever the year/month narrows its options.
  useEffect(() => {
    if (weekOptions.length > 0 && !weekOptions.some((w) => w.key === selectedWeekKey)) {
      setSelectedWeekKey(weekOptions[0].key);
    }
  }, [weekOptions, selectedWeekKey]);
  useEffect(() => {
    if (dayOptions.length > 0 && !dayOptions.some((d) => d.key === selectedDayKey)) {
      setSelectedDayKey(dayOptions[0].key);
    }
  }, [dayOptions, selectedDayKey]);

  const isAllTime = periodType === "all";

  // The backend's period_key format (see insights.py's _period_key) —
  // null for "All time", which every nykaaPm* API call already treats as
  // "omit period_type/period_key entirely" (see api.js).
  const periodKey = isAllTime
    ? null
    : periodType === "yearly"
      ? String(selectedYear)
      : periodType === "monthly"
        ? `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`
        : periodType === "weekly"
          ? selectedWeekKey
          : selectedDayKey;

  // [start, end) for whatever's currently selected — for pages that filter
  // an already-fetched item list client-side (Analytics, All Feedback)
  // rather than asking the backend to re-aggregate. null for "All time".
  const range = useMemo(() => {
    if (isAllTime) return null;
    if (periodType === "daily") {
      const [y, m, d] = selectedDayKey.split("-").map(Number);
      return [new Date(y, m - 1, d), new Date(y, m - 1, d + 1)];
    }
    if (periodType === "weekly") {
      const [isoYearStr, weekStr] = selectedWeekKey.split("-W");
      const monday = mondayOfIsoWeek(Number(isoYearStr), Number(weekStr));
      const start = new Date(monday.getUTCFullYear(), monday.getUTCMonth(), monday.getUTCDate());
      const end = new Date(start);
      end.setDate(end.getDate() + 7);
      return [start, end];
    }
    if (periodType === "monthly") return [new Date(selectedYear, selectedMonth - 1, 1), new Date(selectedYear, selectedMonth, 1)];
    return [new Date(selectedYear, 0, 1), new Date(selectedYear + 1, 0, 1)];
  }, [isAllTime, periodType, selectedYear, selectedMonth, selectedWeekKey, selectedDayKey]);

  return {
    periodType,
    setPeriodType,
    selectedYear,
    setSelectedYear,
    selectedMonth,
    setSelectedMonth,
    selectedWeekKey,
    setSelectedWeekKey,
    selectedDayKey,
    setSelectedDayKey,
    yearOptionsList,
    weekOptions,
    dayOptions,
    isAllTime,
    periodKey,
    range,
  };
}

// Just the year/month/week/day dropdowns — shown only for the currently
// selected period type, so their count (0 for "All time" up to 3 for
// "Weekly") varies. Split out from the type toggle below so a page can put
// other filters (category, sentiment, survey picker...) between them while
// still pinning the toggle to a fixed spot instead of it sliding around
// whenever these dropdowns appear/disappear.
export function NykaaPeriodDateControls({ picker }) {
  const {
    periodType,
    selectedYear,
    setSelectedYear,
    selectedMonth,
    setSelectedMonth,
    selectedWeekKey,
    setSelectedWeekKey,
    selectedDayKey,
    setSelectedDayKey,
    yearOptionsList,
    weekOptions,
    dayOptions,
  } = picker;

  return (
    <>
      {periodType !== "all" && (
        <select
          value={selectedYear}
          onChange={(e) => setSelectedYear(Number(e.target.value))}
          className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
        >
          {yearOptionsList.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      )}

      {(periodType === "monthly" || periodType === "weekly" || periodType === "daily") && (
        <select
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(Number(e.target.value))}
          className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
        >
          {MONTHS.map((m, i) => (
            <option key={m} value={i + 1}>
              {m}
            </option>
          ))}
        </select>
      )}

      {periodType === "weekly" && (
        <select
          value={selectedWeekKey}
          onChange={(e) => setSelectedWeekKey(e.target.value)}
          className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
        >
          {weekOptions.map((w) => (
            <option key={w.key} value={w.key}>
              {w.label}
            </option>
          ))}
        </select>
      )}

      {periodType === "daily" && (
        <select
          value={selectedDayKey}
          onChange={(e) => setSelectedDayKey(e.target.value)}
          className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
        >
          {dayOptions.map((d) => (
            <option key={d.key} value={d.key}>
              {d.label}
            </option>
          ))}
        </select>
      )}
    </>
  );
}

// The All time/Daily/Weekly/Monthly/Yearly buttons on their own — pass
// `className="ml-auto"` (every current caller does) so this stays pinned to
// a fixed spot in its flex row no matter what else is in that row or how
// wide it is.
export function NykaaPeriodTypeToggle({ picker, className = "" }) {
  const { periodType, setPeriodType } = picker;
  return (
    <div className={`grid grid-cols-5 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1 ${className}`}>
      {NYKAA_PERIOD_TYPES.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => setPeriodType(id)}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
            periodType === id
              ? "bg-surface dark:bg-surface-dark text-brand dark:text-brand-dim shadow-sm"
              : "text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
