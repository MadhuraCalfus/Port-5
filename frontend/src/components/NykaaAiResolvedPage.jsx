import { useEffect, useMemo, useState } from "react";
import { MessageCircle, RefreshCw, Search, Sparkles } from "lucide-react";
import { api } from "../api";
import { Card, Modal } from "../components/primitives";

// Nykaa Pulse's mirror of the existing project's "AI Resolved" tab — except
// here the AI's own resolution is a multi-turn conversation (np_chat_turns),
// not a single suggest/confirm exchange, so each row opens the full
// transcript rather than showing it inline. Team-agnostic (these chats were
// never routed anywhere), so the same component is shown to both Admin and
// Team with zero role-specific logic.
function TranscriptModal({ orderId, itemId, onClose }) {
  const [turns, setTurns] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .nykaaAiResolvedChatTranscript(orderId, itemId)
      .then((r) => setTurns(r.turns))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [orderId, itemId]);

  return (
    <Modal title="AI conversation" onClose={onClose}>
      <div className="thin-scroll flex max-h-[28rem] flex-col gap-3 overflow-y-auto pr-1">
        {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
        {!turns && !error ? (
          <p className="my-auto text-center text-xs text-ink/40 dark:text-ink-dark/40">Loading...</p>
        ) : (
          turns?.map((t, i) => (
            <div key={i} className={`flex flex-col ${t.role === "user" ? "items-end" : "items-start"}`}>
              <span
                className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                  t.role === "user"
                    ? "rounded-br-sm bg-brand text-white"
                    : "rounded-bl-sm bg-black/5 dark:bg-white/10 text-ink dark:text-ink-dark"
                }`}
              >
                {t.text}
              </span>
            </div>
          ))
        )}
      </div>
    </Modal>
  );
}

export function NykaaAiResolvedPage() {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.nykaaAiResolvedChats();
      setChats(r.chats);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return chats;
    return chats.filter(
      (c) =>
        String(c.user_name ?? "").toLowerCase().includes(q) ||
        String(c.user_email ?? "").toLowerCase().includes(q) ||
        String(c.product_name ?? "").toLowerCase().includes(q) ||
        String(c.first_message ?? "").toLowerCase().includes(q),
    );
  }, [chats, search]);

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold">Resolved by AI, no ticket raised</h2>
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>
      <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">
        The customer chatted with the bot about an order issue and it was resolved without ever escalating —
        this never became a ticket and never touched a team's queue.
      </p>

      <div className="mt-4 flex items-center gap-3 rounded-xl bg-brand/10 p-4">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/15 text-brand dark:text-brand-dim">
          <Sparkles size={18} />
        </span>
        <div>
          <div className="font-display text-2xl font-bold text-brand dark:text-brand-dim">{chats.length}</div>
          <div className="text-[11px] uppercase tracking-wide text-ink/50 dark:text-ink-dark/50">
            Conversations solved by AI
          </div>
        </div>
      </div>

      <label className="mt-4 flex w-64 items-center gap-1.5 rounded-lg border border-black/10 dark:border-white/15 px-2 py-1 text-xs text-ink/50 dark:text-ink-dark/50">
        <Search size={13} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by customer or product..."
          className="w-full bg-transparent text-xs text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40 outline-none"
        />
      </label>

      <div className="thin-scroll mt-3 max-h-[650px] overflow-auto rounded-xl border border-black/10 dark:border-white/15">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-black/[0.03] dark:bg-white/[0.05] text-[11px] uppercase tracking-wide text-ink/40 dark:text-ink-dark/40">
            <tr>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">First message</th>
              <th className="px-3 py-2">Turns</th>
              <th className="px-3 py-2">Last activity</th>
              <th className="px-3 py-2">Conversation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5 dark:divide-white/10">
            {filtered.map((c) => (
              <tr key={`${c.order_id}-${c.item_id}`} className="align-top">
                <td className="max-w-[140px] px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                  <div className="font-medium">{c.user_name ?? "—"}</div>
                  <div className="text-[11px] text-ink/40 dark:text-ink-dark/40">{c.user_email ?? ""}</div>
                </td>
                <td className="max-w-[160px] px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                  <div className="truncate">{c.product_name}</div>
                  {c.brand && <div className="text-[11px] text-ink/40 dark:text-ink-dark/40">{c.brand}</div>}
                </td>
                <td className="max-w-xs px-3 py-2.5 text-ink/80 dark:text-ink-dark/80">
                  <span className="line-clamp-2">{c.first_message}</span>
                </td>
                <td className="px-3 py-2.5 text-ink/70 dark:text-ink-dark/70">{c.turn_count}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[11px] text-ink/50 dark:text-ink-dark/50">
                  {new Date(c.last_message_at).toLocaleString()}
                </td>
                <td className="px-3 py-2.5">
                  <button
                    onClick={() => setActive(c)}
                    aria-label="View conversation"
                    className="grid h-7 w-7 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10"
                  >
                    <MessageCircle size={15} />
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-sm text-ink/50 dark:text-ink-dark/50">
                  {search ? `No AI-resolved conversations match "${search}".` : "No AI-resolved conversations yet."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {active && <TranscriptModal orderId={active.order_id} itemId={active.item_id} onClose={() => setActive(null)} />}
    </Card>
  );
}
