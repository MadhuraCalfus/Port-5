import { useEffect, useMemo, useState } from "react";
import { MONTHS, isoWeekKey, weeksInMonth, yearOptions } from "../periodNav";

// Weekly/Monthly/Yearly + Year/Month/Week dropdowns — the same period-picker
// pattern already used on the PM side (pages/pm/AnalyticsPage.jsx), lifted
// out here so Admin's Analytics tabs (previously all-time only, no period
// filter at all) can reuse it instead of duplicating ~50 lines of JSX per
// tab. No "Daily" option — neither Admin analytics tab needs day-level
// granularity, unlike the PM page this pattern was copied from.
const PERIOD_TYPES = [
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "yearly", label: "Yearly" },
];

export function usePeriodPicker(defaultType = "weekly") {
  const [periodType, setPeriodType] = useState(defaultType);
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedWeekKey, setSelectedWeekKey] = useState(() => isoWeekKey(new Date()));

  const weekOptions = useMemo(() => weeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);

  // Keep the selected week valid whenever the year/month narrows its options.
  useEffect(() => {
    if (weekOptions.length > 0 && !weekOptions.some((w) => w.key === selectedWeekKey)) {
      setSelectedWeekKey(weekOptions[0].key);
    }
  }, [weekOptions, selectedWeekKey]);

  const periodKey =
    periodType === "yearly"
      ? String(selectedYear)
      : periodType === "monthly"
        ? `${selectedYear}-${String(selectedMonth).padStart(2, "0")}`
        : selectedWeekKey;

  return {
    periodType,
    setPeriodType,
    selectedYear,
    setSelectedYear,
    selectedMonth,
    setSelectedMonth,
    selectedWeekKey,
    setSelectedWeekKey,
    weekOptions,
    periodKey,
  };
}

export function PeriodPicker({ picker }) {
  const { periodType, setPeriodType, selectedYear, setSelectedYear, selectedMonth, setSelectedMonth, selectedWeekKey, setSelectedWeekKey, weekOptions } =
    picker;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {(periodType === "monthly" || periodType === "weekly") && (
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

      <select
        value={selectedYear}
        onChange={(e) => setSelectedYear(Number(e.target.value))}
        className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1.5 text-xs text-ink dark:text-ink-dark"
      >
        {yearOptions().map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>

      <div className="grid grid-cols-3 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
        {PERIOD_TYPES.map(({ id, label }) => (
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
    </div>
  );
}
