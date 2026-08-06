import { useEffect, useState } from "react";
import { MessageCircle, RefreshCw, ShoppingBag } from "lucide-react";
import { api } from "../../../api";
import { Card, ConfidenceMeter, Modal, PriorityBadge, ToneBadge } from "../../../components/primitives";
import { NykaaCommentThread } from "../../../components/NykaaCommentThread";

// Same status-select convention as TeamTicketsPage.jsx — status only ever
// moves forward, mirrored here rather than imported since it's presentation
// logic tied to this table's own columns, not shared state.
const TEAM_STATUS_LABELS = { Routed: "New", "In Progress": "In Progress", Resolved: "Resolved" };
const ALLOWED_NEXT_STATUSES = {
  Routed: ["Routed", "In Progress", "Resolved"],
  "In Progress": ["In Progress", "Resolved"],
  Resolved: ["Resolved"],
};
const STATUS_SELECT_STYLES = {
  Routed: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
  "In Progress": "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  Resolved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
};

// This team's queue of Nykaa Pulse's own tickets (np_tickets — a table
// entirely separate from the shared tickets table "TicketTrident" uses),
// shown with which product/brand each one is about so a team member
// doesn't have to open each ticket to find that context.
export function NykaaTeamOrderTicketsPage() {
  const [tickets, setTickets] = useState(null);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState(null);
  const [activeThread, setActiveThread] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.nykaaTeamOrderTickets();
      setTickets(r.tickets);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function updateStatus(id, status) {
    setUpdating(id);
    try {
      await api.nykaaTeamUpdateTicketStatus(id, status);
      await load();
    } finally {
      setUpdating(null);
    }
  }

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-semibold">Nykaa Pulse tickets</h2>
          <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
            Tickets raised from a customer order, with which product/brand each one is about.
          </p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {!tickets ? (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink/50 dark:text-ink-dark/50">
          Loading...
        </div>
      ) : tickets.length === 0 ? (
        <p className="mt-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
          No order-linked tickets for your team yet.
        </p>
      ) : (
        <div className="thin-scroll mt-4 max-h-[650px] overflow-auto rounded-xl border border-black/10 dark:border-white/15">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-black/[0.03] dark:bg-white/[0.05] text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
              <tr>
                <th className="px-3 py-2">Customer</th>
                <th className="px-3 py-2">Ticket ID</th>
                <th className="px-3 py-2">Product</th>
                <th className="px-3 py-2">Issue</th>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Tone</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Chat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5 dark:divide-white/10">
              {tickets.map((t) => (
                <tr key={t.id} className="align-top">
                  <td className="max-w-[140px] px-3 py-2.5">
                    <div className="font-medium text-ink dark:text-ink-dark">{t.user_name ?? "—"}</div>
                    <div className="text-[11px] text-ink/40 dark:text-ink-dark/40">{t.user_email ?? t.user_id}</div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-ink/50 dark:text-ink-dark/50">#{t.id}</td>
                  <td className="max-w-[160px] px-3 py-2.5">
                    <div className="flex items-center gap-1.5 text-ink/80 dark:text-ink-dark/80">
                      <ShoppingBag size={12} className="shrink-0 text-brand dark:text-brand-dim" />
                      <span className="truncate">{t.product_name ?? `Order #${t.order_id}`}</span>
                    </div>
                    {t.brand && (
                      <div className="mt-0.5 text-[11px] text-ink/40 dark:text-ink-dark/40">{t.brand}</div>
                    )}
                  </td>
                  <td className="max-w-xs px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">{t.summary ?? t.message}</td>
                  <td className="px-3 py-2.5"><PriorityBadge priority={t.priority} escalated={t.escalated} /></td>
                  <td className="px-3 py-2.5"><ToneBadge tone={t.tone} /></td>
                  <td className="px-3 py-2.5"><ConfidenceMeter value={t.confidence} ambiguous={t.is_ambiguous} /></td>
                  <td className="px-3 py-2.5">
                    <select
                      value={t.status}
                      disabled={updating === t.id || t.status === "Resolved"}
                      onChange={(e) => updateStatus(t.id, e.target.value)}
                      className={`rounded-full border-0 px-2.5 py-1 text-xs font-semibold outline-none disabled:cursor-not-allowed disabled:opacity-80 ${STATUS_SELECT_STYLES[t.status] ?? STATUS_SELECT_STYLES.Routed}`}
                    >
                      {(ALLOWED_NEXT_STATUSES[t.status] ?? ["Resolved"]).map((value) => (
                        <option key={value} value={value} className="bg-surface dark:bg-surface-dark text-ink dark:text-ink-dark">
                          {TEAM_STATUS_LABELS[value]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2.5">
                    <button
                      onClick={() => setActiveThread(t.id)}
                      disabled={t.status !== "In Progress"}
                      aria-label={`Message customer for ticket ${t.id}`}
                      title={
                        t.status === "In Progress"
                          ? undefined
                          : t.status === "Resolved"
                            ? "This ticket is resolved — messaging is closed."
                            : "Move this ticket to In Progress to start messaging the customer."
                      }
                      className="relative grid h-7 w-7 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      <MessageCircle size={15} />
                      {t.unread_comments > 0 && (
                        <span className="absolute -right-1 -top-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-none text-white">
                          {t.unread_comments}
                        </span>
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeThread && (
        <Modal
          title={`Ticket #${activeThread} — Messages`}
          onClose={() => {
            setActiveThread(null);
            load();
          }}
        >
          <NykaaCommentThread ticketId={activeThread} />
        </Modal>
      )}
    </Card>
  );
}
