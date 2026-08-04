import { useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowDownUp, Building2, FileDown, Loader2, MessageCircle, RefreshCw, Search } from "lucide-react";
import { api } from "../../../api";
import { TEAMS } from "../../../constants";
import { downloadBlob } from "../../../downloadBlob";
import { filterTickets } from "../../../filterTickets";
import { sortTickets } from "../../../sortTickets";
import { Card, ConfidenceMeter, Modal, PriorityBadge, StatusBadge, ToneBadge, Toast } from "../../../components/primitives";
import { NykaaCommentThread } from "../../../components/NykaaCommentThread";

// np_tickets are born already-classified/"Routed" (see nykaa_store.py) —
// there's no pre-routing "New" stage the shared tickets table has.
const STATUS_ORDER = ["Routed", "In Progress", "Resolved"];

const STATUS_TABS = [
  { id: "all", label: "All", status: null },
  { id: "routed", label: "Routed", status: "Routed" },
  { id: "in_progress", label: "In Progress", status: "In Progress" },
  { id: "resolved", label: "Resolved", status: "Resolved" },
];

// Admin's Nykaa Pulse ticket oversight — same columns/PDF-export/read-only
// chat treatment Admin already gets for the shared tickets table
// (AllTicketsPage.jsx), sourced from np_tickets across every team instead.
export function NykaaAdminTicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState("date");
  const [search, setSearch] = useState("");
  const [statusTab, setStatusTab] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");
  const [activeThread, setActiveThread] = useState(null);
  const [downloadingReport, setDownloadingReport] = useState(null);
  const [toast, setToast] = useState(null);

  function showToast(message) {
    setToast(message);
    setTimeout(() => setToast(null), 2500);
  }

  async function load() {
    setLoading(true);
    try {
      const r = await api.nykaaAdminListTickets();
      setTickets(r.tickets);
    } finally {
      setLoading(false);
    }
  }

  async function downloadReport(id) {
    setDownloadingReport(id);
    try {
      const blob = await api.nykaaDownloadTicketReport(id);
      downloadBlob(blob, `nykaa-ticket-${id}-report.pdf`);
    } catch {
      showToast("Couldn't generate that report.");
    } finally {
      setDownloadingReport(null);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const activeStatus = STATUS_TABS.find((t) => t.id === statusTab)?.status;
  const byStatus = activeStatus ? tickets.filter((t) => t.status === activeStatus) : tickets;
  const byTeam = teamFilter === "all" ? byStatus : byStatus.filter((t) => t.team === teamFilter);
  const sorted = sortTickets(filterTickets(byTeam, search), sortBy, STATUS_ORDER);

  return (
    <Card className="p-5">
      <Toast message={toast} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold">Nykaa Pulse tickets ({tickets.length})</h2>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 rounded-lg border border-black/10 dark:border-white/15 px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50">
            <Search size={13} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by ID, name, or message..."
              className="w-44 bg-transparent text-xs text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40 outline-none"
            />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-ink/50 dark:text-ink-dark/50">
            <Building2 size={13} />
            <select
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1 text-xs text-ink dark:text-ink-dark"
            >
              <option value="all">All teams</option>
              {TEAMS.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-ink/50 dark:text-ink-dark/50">
            <ArrowDownUp size={13} />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-2 py-1 text-xs text-ink dark:text-ink-dark"
            >
              <option value="date">Date (newest first)</option>
              <option value="priority">Priority (High first)</option>
              <option value="status">Status (Routed → In Progress → Resolved)</option>
            </select>
          </label>
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {STATUS_TABS.map((t) => {
          const count = t.status ? tickets.filter((x) => x.status === t.status).length : tickets.length;
          return (
            <button
              key={t.id}
              onClick={() => setStatusTab(t.id)}
              className={clsx(
                "rounded-full px-3 py-1 text-xs font-medium transition",
                statusTab === t.id
                  ? "bg-brand text-white"
                  : "bg-black/5 dark:bg-white/10 text-ink/60 dark:text-ink-dark/60 hover:bg-black/10 dark:hover:bg-white/15",
              )}
            >
              {t.label} ({count})
            </button>
          );
        })}
      </div>

      <div className="thin-scroll mt-3 max-h-[650px] overflow-auto rounded-xl border border-black/10 dark:border-white/15">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-black/[0.03] dark:bg-white/[0.05] text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Issue</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Priority</th>
              <th className="px-3 py-2">Team</th>
              <th className="px-3 py-2">Tone</th>
              <th className="px-3 py-2">Confidence</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Chat</th>
              <th className="px-3 py-2">Report</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5 dark:divide-white/10">
            {sorted.map((t) => (
              <tr key={t.id} className="align-top">
                <td className="px-3 py-2.5 font-mono text-[11px] text-ink/50 dark:text-ink-dark/50">#{t.id}</td>
                <td className="max-w-[140px] px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                  <div className="font-medium">{t.user_name ?? "—"}</div>
                  <div className="text-[11px] text-ink/40 dark:text-ink-dark/40">{t.user_email ?? t.user_id}</div>
                </td>
                <td className="w-40 px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                  <div className="break-words">{t.product_name}</div>
                  {t.brand && <div className="text-[11px] text-ink/40 dark:text-ink-dark/40">{t.brand}</div>}
                </td>
                <td className="w-64 px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                  <span className="break-words">{t.summary ?? t.message}</span>
                </td>
                <td className="px-3 py-2.5 whitespace-nowrap">{t.category ?? "—"}</td>
                <td className="px-3 py-2.5">{t.priority ? <PriorityBadge priority={t.priority} escalated={t.escalated} /> : "—"}</td>
                <td className="px-3 py-2.5 whitespace-nowrap">{t.team ?? "—"}</td>
                <td className="px-3 py-2.5">{t.tone ? <ToneBadge tone={t.tone} /> : "—"}</td>
                <td className="px-3 py-2.5">{t.confidence != null ? <ConfidenceMeter value={t.confidence} ambiguous={t.is_ambiguous} /> : "—"}</td>
                <td className="px-3 py-2.5"><StatusBadge status={t.status} /></td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[11px] text-ink/50 dark:text-ink-dark/50">
                  {new Date(t.created_at).toLocaleString()}
                </td>
                <td className="px-3 py-2.5">
                  <button
                    onClick={() => setActiveThread(t.id)}
                    aria-label={`View chat history for ticket ${t.id}`}
                    className="grid h-7 w-7 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
                  >
                    <MessageCircle size={15} />
                  </button>
                </td>
                <td className="px-3 py-2.5">
                  <button
                    onClick={() => downloadReport(t.id)}
                    disabled={downloadingReport === t.id}
                    aria-label={`Download PDF report for ticket ${t.id}`}
                    className="grid h-7 w-7 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:cursor-wait"
                  >
                    {downloadingReport === t.id ? <Loader2 size={15} className="animate-spin" /> : <FileDown size={15} />}
                  </button>
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={13} className="px-3 py-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                  {search ? `No tickets match "${search}".` : "No tickets in this status."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {activeThread && (
        <Modal title={`Ticket #${activeThread} — Chat history`} onClose={() => setActiveThread(null)}>
          <NykaaCommentThread ticketId={activeThread} readOnly />
        </Modal>
      )}
    </Card>
  );
}
