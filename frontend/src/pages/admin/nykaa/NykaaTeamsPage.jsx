import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../../../api";
import { TEAMS } from "../../../constants";
import { Card } from "../../../components/primitives";

// Purely the per-team ticket breakdown now — account management (add/list/
// delete team leads) moved to its own Team Members tab (see
// NykaaTeamMembersPage.jsx), mirroring the Mission side's Teams/Team
// Members split. "Routed" here instead of the Mission side's "Assigned",
// since np_tickets are born already-routed and have no separate assigned
// state (see nykaa_store.py).
function Stat({ value, label, className }) {
  return (
    <div className="text-center">
      <div className={`font-display text-lg font-bold ${className}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">{label}</div>
    </div>
  );
}

export function NykaaTeamsPage() {
  const [members, setMembers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [membersRes, ticketsRes] = await Promise.all([api.adminListTeamMembers(), api.nykaaAdminListTickets()]);
      setMembers(membersRes.team_members);
      setTickets(ticketsRes.tickets);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const membersByTeam = useMemo(() => {
    const map = {};
    for (const m of members) (map[m.team] ??= []).push(m);
    return map;
  }, [members]);

  const teamStats = useMemo(
    () =>
      TEAMS.map((t) => {
        const forTeam = tickets.filter((x) => x.team === t);
        return {
          team: t,
          total: forTeam.length,
          routed: forTeam.filter((x) => x.status === "Routed").length,
          in_progress: forTeam.filter((x) => x.status === "In Progress").length,
          resolved: forTeam.filter((x) => x.status === "Resolved").length,
        };
      }),
    [tickets],
  );

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-semibold">Teams</h2>
          <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">Number of tickets per team, across every ticket ever routed to them.</p>
        </div>
        <button onClick={load} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10">
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {teamStats.map((t) => (
          <div key={t.team} className="rounded-xl border border-black/10 dark:border-white/15 p-4">
            <div className="text-sm font-semibold text-ink dark:text-ink-dark">{t.team}</div>
            <div className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{t.total} ticket{t.total === 1 ? "" : "s"} total</div>
            <div className="mt-3 grid grid-cols-3 gap-2 border-t border-black/5 dark:border-white/10 pt-3">
              <Stat value={t.routed} label="Routed" className="text-blue-600 dark:text-blue-400" />
              <Stat value={t.in_progress} label="In Progress" className="text-amber-600 dark:text-amber-400" />
              <Stat value={t.resolved} label="Resolved" className="text-emerald-600 dark:text-emerald-400" />
            </div>
          </div>
        ))}
      </div>

      {TEAMS.filter((t) => !membersByTeam[t]).length > 0 && (
        <p className="mt-4 text-xs text-ink/40 dark:text-ink-dark/40">
          No team lead account yet for: {TEAMS.filter((t) => !membersByTeam[t]).join(", ")}.
        </p>
      )}
    </Card>
  );
}
