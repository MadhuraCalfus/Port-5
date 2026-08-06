import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { FileText, Loader2, Paperclip, RefreshCw, Send, Star } from "lucide-react";
import { api } from "../../../api";
import { downloadBlob } from "../../../downloadBlob";
import { Button, Modal } from "../../../components/primitives";

const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;

// Same display name the backend uses when it bulk-copies the bot-phase
// transcript into np_ticket_comments at escalation time (see
// nykaa_routes.chat_turn) — kept as one literal here too so the label reads
// identically whether a message is still live in the bot phase or has
// already landed in the ticket thread.
const BOT_NAME = "NykaaPulse Assistant";

// Shared by every star-rating surface in Nykaa Pulse (review rating, CSAT) —
// moved here (rather than staying private to NykaaOrdersPage.jsx) so the
// CSAT prompt inside useTicketChat/TicketChatBody below can use it too,
// without NykaaOrdersPage.jsx and this module importing each other.
export function StarInput({ value, onChange, size = 15 }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(value === n ? null : n)}
          className="grid place-items-center rounded hover:bg-black/5 dark:hover:bg-white/10"
          style={{ height: size + 10, width: size + 10 }}
          aria-label={`${n} star${n === 1 ? "" : "s"}`}
        >
          <Star size={size} className={value && n <= value ? "fill-amber-400 text-amber-400" : "text-ink/25 dark:text-ink-dark/25"} />
        </button>
      ))}
    </div>
  );
}

function formatInr(amount) {
  return `₹${Number(amount).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function ChatContextCard({ order, item }) {
  return (
    <div className="rounded-xl border border-black/8 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] p-3 text-xs">
      <p className="mb-1.5 font-semibold text-ink dark:text-ink-dark">Order Details</p>
      <p className="text-ink/60 dark:text-ink-dark/60">
        Order #{order.id} · {item.product_name}
      </p>
      <p className="text-ink/60 dark:text-ink-dark/60">Amount: {formatInr(item.unit_price_at_purchase * item.quantity)}</p>
      <p className="text-ink/60 dark:text-ink-dark/60">Order date: {new Date(order.placed_at).toLocaleDateString("en-IN")}</p>
    </div>
  );
}

// Same chip shape as the Mission side's CommentThread.jsx — a document
// attached instead of a text body, opened (downloaded) on click rather than
// rendered inline.
function AttachmentChip({ name, onOpen }) {
  return (
    <button
      onClick={onOpen}
      className="mt-0.5 flex max-w-[80%] items-center gap-2 rounded-2xl border border-black/10 dark:border-white/15 bg-black/[0.03] dark:bg-white/[0.06] px-3 py-2 text-left text-sm text-ink dark:text-ink-dark hover:bg-black/[0.06] dark:hover:bg-white/[0.1]"
    >
      <FileText size={16} className="shrink-0 text-ink/50 dark:text-ink-dark/50" />
      <span className="truncate">{name}</span>
    </button>
  );
}

// Every bubble is labeled with who sent it — "You" for the viewer's own
// message, the bot's fixed name while a human hasn't joined yet, or the
// human agent's real name once one has (author_name, straight from
// np_ticket_comments) — never left blank, so a reopened or admin-viewed
// conversation is never ambiguous about who said what.
function ChatBubble({ mine, name, text, attachmentName, onOpenAttachment }) {
  return (
    <div className={clsx("flex flex-col", mine ? "items-end" : "items-start")}>
      <span className="mb-0.5 px-1 text-[10px] text-ink/40 dark:text-ink-dark/40">{mine ? "You" : name}</span>
      {attachmentName ? (
        <AttachmentChip name={attachmentName} onOpen={onOpenAttachment} />
      ) : (
        <span
          className={clsx(
            "max-w-[80%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
            mine ? "rounded-br-sm bg-brand text-white" : "rounded-bl-sm bg-black/5 dark:bg-white/10 text-ink dark:text-ink-dark",
          )}
        >
          {text}
        </span>
      )}
    </div>
  );
}

// Shared logic behind the "Raise a Ticket" chat — multi-turn: the bot keeps
// trying to help (nykaaChatTurn, one call per turn) until it either resolves
// things or escalates. On escalation, a real ticket exists and this switches
// to showing that ticket's own live comment thread (the same np_ticket_
// comments a team member replies in) — so the bot-phase transcript and the
// human hand-off both live in one continuous, reopenable conversation. Kept
// as a hook (not a component) so both the centered "Help" modal
// (TicketChatModal) and the bottom-anchored floating chatbot can share the
// exact same behavior behind two different visual shells.
export function useTicketChat({ order, item, onTicketRaised }) {
  const alreadyEscalated = Boolean(item.linked_ticket_id);
  const [phase, setPhase] = useState(alreadyEscalated ? "escalated" : "chat");
  const [messages, setMessages] = useState([]); // bot-phase turns, while phase === "chat"
  const [historyLoading, setHistoryLoading] = useState(!alreadyEscalated);
  const [thread, setThread] = useState(null); // live np_ticket_comments, once escalated
  const [messagingOpen, setMessagingOpen] = useState(false);
  const [ticketStatus, setTicketStatus] = useState(null);
  const [csatRating, setCsatRating] = useState(null);
  const [threadLoading, setThreadLoading] = useState(alreadyEscalated);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);

  // CSAT — "how was your support experience" — asked once, right when a
  // Resolved ticket has no rating yet.
  const [csatDraft, setCsatDraft] = useState(null);
  const [csatComment, setCsatComment] = useState("");
  const [csatSubmitting, setCsatSubmitting] = useState(false);

  const bottomRef = useRef(null);

  async function loadThread(ticketId) {
    if (thread === null) setThreadLoading(true);
    try {
      const r = await api.nykaaTicketComments(ticketId);
      setThread(r.comments);
      setMessagingOpen(r.messaging_open);
      setTicketStatus(r.status);
      setCsatRating(r.csat_rating);
      api.nykaaMarkTicketCommentsRead(ticketId).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setThreadLoading(false);
    }
  }

  async function submitCsat() {
    if (!csatDraft) return;
    setCsatSubmitting(true);
    setError(null);
    try {
      await api.nykaaSubmitCsat(item.linked_ticket_id, csatDraft, csatComment.trim() || null);
      setCsatRating(csatDraft);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCsatSubmitting(false);
    }
  }

  // Restore a still-in-progress (not yet escalated) conversation from
  // np_chat_turns instead of always restarting from the greeting — a
  // customer who closes and reopens the chat (or hits Sync) sees exactly
  // where they left off.
  async function loadBotHistory() {
    try {
      const r = await api.nykaaChatHistory(order.id, item.id);
      setMessages(
        r.turns.length > 0
          ? r.turns.map((t) => ({ id: t.id, role: t.role, text: t.text, attachmentName: t.attachment_name }))
          : [{ role: "bot", text: "Hi! Tell me what went wrong with this order and I'll get it logged for you." }],
      );
    } catch (e) {
      setMessages((prev) =>
        prev.length > 0 ? prev : [{ role: "bot", text: "Hi! Tell me what went wrong with this order and I'll get it logged for you." }],
      );
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    if (alreadyEscalated) {
      loadThread(item.linked_ticket_id);
      return;
    }
    loadBotHistory().finally(() => setHistoryLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetches whichever side of the conversation is currently showing (the
  // persisted bot-phase transcript, or the ticket thread once escalated) so
  // a customer/agent who's been idle for a while — or has this chat open on
  // another tab/device — can pull in whatever the other side has sent since
  // it last loaded.
  async function sync() {
    if (syncing) return;
    setSyncing(true);
    setError(null);
    try {
      if (phase === "escalated") {
        await loadThread(item.linked_ticket_id);
      } else {
        await loadBotHistory();
      }
    } finally {
      setSyncing(false);
    }
  }

  // Auto-sync — once a ticket is escalated (waiting for pickup, or already
  // being worked by a team member), poll for updates in the background
  // instead of making the customer click a Sync button.
  useEffect(() => {
    if (phase !== "escalated") return;
    const id = setInterval(sync, 8000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, thread]);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setError(null);
    setSending(true);
    try {
      if (phase === "chat") {
        setMessages((m) => [...m, { role: "user", text }, { role: "typing" }]);
        const outcome = await api.nykaaChatTurn(order.id, item.id, text);
        setMessages((m) => m.filter((msg) => msg.role !== "typing"));
        if (!outcome.escalated) {
          setMessages((m) => [...m, { role: "bot", text: outcome.reply }]);
        } else {
          onTicketRaised?.(outcome.ticket);
          setPhase("escalated");
          await loadThread(outcome.ticket.id);
        }
      } else {
        await api.nykaaPostTicketComment(item.linked_ticket_id, text);
        await loadThread(item.linked_ticket_id);
      }
    } catch (e) {
      setMessages((m) => m.filter((msg) => msg.role !== "typing"));
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  async function uploadAttachment(file) {
    if (uploading) return;
    if (file.size > MAX_ATTACHMENT_BYTES) {
      setError("That file is too large (max 5MB).");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      if (phase === "escalated") {
        await api.nykaaUploadTicketAttachment(item.linked_ticket_id, file);
        await loadThread(item.linked_ticket_id);
      } else {
        await api.nykaaUploadChatAttachment(order.id, item.id, file);
        await loadBotHistory();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  async function openAttachment(entry) {
    try {
      const blob =
        phase === "escalated"
          ? await api.nykaaDownloadTicketAttachment(item.linked_ticket_id, entry.id)
          : await api.nykaaDownloadChatAttachment(order.id, item.id, entry.id);
      downloadBlob(blob, entry.attachment_name || entry.attachmentName);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const inputDisabled = phase === "escalated" && !messagingOpen;

  return {
    phase,
    messages,
    historyLoading,
    thread,
    threadLoading,
    ticketStatus,
    csatRating,
    draft,
    setDraft,
    sending,
    uploading,
    syncing,
    sync,
    error,
    send,
    uploadAttachment,
    openAttachment,
    inputDisabled,
    bottomRef,
    csatDraft,
    setCsatDraft,
    csatComment,
    setCsatComment,
    csatSubmitting,
    submitCsat,
  };
}

// Shared body markup — order context, message list (bot transcript or
// escalated ticket thread), CSAT prompt, and the input row. The two shells
// (centered Modal vs bottom-anchored floating panel) just wrap this in
// different chrome, so the conversation itself looks/behaves identically
// wherever it's opened from.
export function TicketChatBody({ order, item, chat }) {
  const {
    phase,
    messages,
    historyLoading,
    thread,
    threadLoading,
    ticketStatus,
    csatRating,
    draft,
    setDraft,
    sending,
    uploading,
    syncing,
    error,
    send,
    uploadAttachment,
    openAttachment,
    inputDisabled,
    bottomRef,
    csatDraft,
    setCsatDraft,
    csatComment,
    setCsatComment,
    csatSubmitting,
    submitCsat,
  } = chat;
  const fileInputRef = useRef(null);

  function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) uploadAttachment(file);
  }

  return (
    <>
      {phase === "escalated" && (
        <div className="flex items-center justify-end gap-1.5 px-2 py-1 text-[11px] text-ink/40 dark:text-ink-dark/40">
          <RefreshCw size={11} className={syncing ? "animate-spin" : ""} />
          {syncing ? "Checking for updates..." : "Auto-syncing"}
        </div>
      )}
      <div className="thin-scroll flex max-h-[420px] min-h-[200px] flex-col gap-3 overflow-y-auto overscroll-contain pr-1">
        <ChatContextCard order={order} item={item} />

        {phase === "chat" ? (
          historyLoading ? (
            <p className="my-auto text-center text-xs text-ink/40 dark:text-ink-dark/40">Loading...</p>
          ) : (
            messages.map((m, i) =>
              m.role === "typing" ? (
                <div key={i} className="flex items-center gap-1 self-start rounded-2xl rounded-bl-sm bg-black/5 dark:bg-white/10 px-3 py-2.5">
                  <Loader2 size={13} className="animate-spin text-ink/40 dark:text-ink-dark/40" />
                </div>
              ) : (
                <ChatBubble
                  key={i}
                  mine={m.role === "user"}
                  name={BOT_NAME}
                  text={m.text}
                  attachmentName={m.attachmentName}
                  onOpenAttachment={() => openAttachment(m)}
                />
              ),
            )
          )
        ) : threadLoading ? (
          <p className="my-auto text-center text-xs text-ink/40 dark:text-ink-dark/40">Loading...</p>
        ) : (
          (thread || []).map((c) => (
            <ChatBubble
              key={c.id}
              mine={c.author_role === "user"}
              name={c.author_name}
              text={c.body}
              attachmentName={c.attachment_name}
              onOpenAttachment={() => openAttachment(c)}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="mt-2 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {phase === "escalated" && !threadLoading && ticketStatus === "Resolved" && csatRating == null ? (
        <div className="mt-3 rounded-xl bg-brand/[0.06] p-3">
          <p className="text-center text-xs font-medium text-ink dark:text-ink-dark">How was your support experience?</p>
          <div className="mt-1.5 flex justify-center">
            <StarInput value={csatDraft} onChange={setCsatDraft} size={22} />
          </div>
          <input
            value={csatComment}
            onChange={(e) => setCsatComment(e.target.value)}
            placeholder="Anything you'd like to add? (optional)"
            className="mt-2 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-1.5 text-xs text-ink dark:text-ink-dark"
          />
          <Button onClick={submitCsat} disabled={!csatDraft || csatSubmitting} className="mt-2 w-full px-3 py-1.5 text-xs">
            {csatSubmitting ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
            {csatSubmitting ? "Submitting..." : "Submit rating"}
          </Button>
        </div>
      ) : phase === "escalated" && !threadLoading && ticketStatus === "Resolved" && csatRating != null ? (
        <p className="mt-3 text-center text-xs text-emerald-600 dark:text-emerald-400">
          Thanks for rating your support experience {csatRating}★!
        </p>
      ) : inputDisabled ? (
        !threadLoading && (
          <p className="mt-3 text-center text-xs text-ink/40 dark:text-ink-dark/40">
            Waiting for a team member to pick this up — you'll be able to reply once they do.
          </p>
        )
      ) : (
        <div className="mt-3 flex items-center gap-2">
          <input ref={fileInputRef} type="file" onChange={handleFile} className="hidden" />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            aria-label="Attach a file"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
          >
            {uploading ? <Loader2 size={15} className="animate-spin" /> : <Paperclip size={15} />}
          </button>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
            placeholder="Type a message"
            disabled={sending}
            className="flex-1 rounded-full border border-black/10 dark:border-white/15 bg-transparent px-4 py-2.5 text-sm text-ink dark:text-ink-dark disabled:opacity-60"
          />
          <button
            onClick={send}
            disabled={sending || !draft.trim()}
            aria-label="Send"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand text-white disabled:opacity-40"
          >
            {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
      )}
    </>
  );
}

// Opened via an order item's "Help" button (My Orders page) — a centered
// dialog, same as every other modal in that flow (Feedback, Delivery
// Feedback).
export function TicketChatModal({ order, item, onClose, onTicketRaised }) {
  const chat = useTicketChat({ order, item, onTicketRaised });
  return (
    <Modal title="Chat with us" onClose={onClose}>
      <TicketChatBody order={order} item={item} chat={chat} />
    </Modal>
  );
}
