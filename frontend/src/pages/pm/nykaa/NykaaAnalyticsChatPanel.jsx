import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2, MessageCircle, Send } from "lucide-react";
import { api } from "../../../api";
import { SlideOver } from "../../../components/primitives";
import { AnalyticsChatChart } from "./NykaaAnalyticsChatChart";

const MAX_TABLE_ROWS = 25;

const EXAMPLE_QUESTIONS = [
  "This week's critical reviews",
  "Feedback for brand Bella Vita by sentiment",
  "Compare review categories in a graph",
];

function ChatTable({ columns, rows }) {
  if (!columns?.length || !rows?.length) return null;
  const shown = rows.slice(0, MAX_TABLE_ROWS);
  return (
    <div className="thin-scroll mt-3 max-w-full overflow-x-auto rounded-xl border border-black/5 dark:border-white/10">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-black/[0.03] dark:bg-white/[0.05]">
          <tr>
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2 font-semibold capitalize text-ink/70 dark:text-ink-dark/70">
                {c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i} className="border-t border-black/5 dark:border-white/10">
              {columns.map((c) => (
                <td key={c} className="whitespace-nowrap px-3 py-2 text-ink/80 dark:text-ink-dark/80">
                  {row[c] === null || row[c] === undefined || row[c] === "" ? "—" : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > shown.length && (
        <p className="px-3 py-2 text-[11px] text-ink/40 dark:text-ink-dark/40">+{rows.length - shown.length} more row(s)</p>
      )}
    </div>
  );
}

function ChatMessage({ message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand px-3.5 py-2 text-sm text-white">{message.text}</div>
      </div>
    );
  }
  return (
    <div className="max-w-full rounded-2xl rounded-bl-sm border border-black/5 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-4 py-3">
      {message.loading ? (
        <p className="flex items-center gap-2 text-sm text-ink/50 dark:text-ink-dark/50">
          <Loader2 size={14} className="animate-spin" /> Thinking...
        </p>
      ) : (
        <>
          <p className="text-sm text-ink dark:text-ink-dark">{message.error ?? message.answer}</p>
          <ChatTable columns={message.columns} rows={message.rows} />
          <AnalyticsChatChart spec={message.chart} />
        </>
      )}
    </div>
  );
}

// PM Analytics chatbot — free-text question over feedback/reviews, answered
// by the backend's guardrailed NL -> SQL pipeline (nykaa_chat_sql.py). Chart
// rendering lives in NykaaAnalyticsChatChart.jsx, not here.
//
// Floats over the page as a launcher button (portaled to document.body, same
// as Modal/SlideOver — see primitives.jsx) rather than sitting inline above
// the dashboard, so it never pushes the charts down. Opens into a wide
// SlideOver drawer instead of a small popup.
export function NykaaAnalyticsChatPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const idRef = useRef(0);

  async function send(question) {
    const text = (question ?? input).trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    const userMsg = { id: idRef.current++, role: "user", text };
    const pendingMsg = { id: idRef.current++, role: "assistant", loading: true };
    setMessages((prev) => [...prev, userMsg, pendingMsg]);
    try {
      const r = await api.nykaaAnalyticsChat(text);
      setMessages((prev) => prev.map((m) => (m.id === pendingMsg.id ? { ...pendingMsg, loading: false, ...r } : m)));
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingMsg.id ? { ...pendingMsg, loading: false, error: e instanceof Error ? e.message : String(e) } : m)),
      );
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return createPortal(
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Ask the analytics chatbot"
        className="fixed bottom-6 right-6 z-40 grid h-14 w-14 place-items-center rounded-full bg-brand text-white shadow-xl hover:brightness-110"
      >
        <MessageCircle size={22} />
      </button>,
      document.body,
    );
  }

  return (
    <SlideOver title="Ask the analytics" onClose={() => setOpen(false)} widthClassName="max-w-xl sm:max-w-2xl lg:max-w-3xl">
      <p className="text-xs text-ink/50 dark:text-ink-dark/50">
        Ask about feedback or reviews — ask for a graph and you'll get one. Read-only: this can only fetch data, never change it.
      </p>

      <div className="thin-scroll mt-4 max-h-[calc(100vh-13rem)] min-h-[64px] space-y-3 overflow-y-auto overscroll-contain pr-1">
        {messages.length === 0 ? (
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => send(q)}
                className="rounded-full border border-black/10 dark:border-white/15 px-3 py-1.5 text-xs text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
              >
                {q}
              </button>
            ))}
          </div>
        ) : (
          messages.map((m) => <ChatMessage key={m.id} message={m} />)
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="mt-4 flex items-center gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about the feedback..."
          disabled={sending}
          className="flex-1 rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark placeholder:text-ink/40 dark:placeholder:text-ink-dark/40"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3.5 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send
        </button>
      </form>
    </SlideOver>
  );
}
