import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, Loader2, Paperclip, Send } from "lucide-react";
import { api } from "../api";
import { downloadBlob } from "../downloadBlob";
import { useAuth } from "../auth/AuthContext";

const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;

function AttachmentChip({ comment, onOpen }) {
  return (
    <button
      onClick={() => onOpen(comment)}
      className="mt-0.5 flex max-w-[80%] items-center gap-2 rounded-2xl border border-black/10 dark:border-white/15 bg-black/[0.03] dark:bg-white/[0.06] px-3 py-2 text-left text-sm text-ink dark:text-ink-dark hover:bg-black/[0.06] dark:hover:bg-white/[0.1]"
    >
      <FileText size={16} className="shrink-0 text-ink/50 dark:text-ink-dark/50" />
      <span className="truncate">{comment.attachment_name}</span>
    </button>
  );
}

export function CommentThread({ ticketId, readOnly = false }) {
  const { auth } = useAuth();
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [messagingOpen, setMessagingOpen] = useState(true);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const r = await api.ticketComments(ticketId);
      setComments(r.comments);
      setMessagingOpen(r.messaging_open);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    load().then(() => api.markTicketCommentsRead(ticketId).catch(() => {}));
  }, [ticketId, load]);

  async function send(e) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    setSending(true);
    setError(null);
    try {
      await api.postTicketComment(ticketId, trimmed);
      setBody("");
      await load();
    } catch {
      setError("Couldn't send that message.");
    } finally {
      setSending(false);
    }
  }

  async function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_ATTACHMENT_BYTES) {
      setError("That file is too large (max 5MB).");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await api.uploadTicketAttachment(ticketId, file);
      await load();
    } catch {
      setError("Couldn't upload that file.");
    } finally {
      setUploading(false);
    }
  }

  async function openAttachment(comment) {
    try {
      const blob = await api.downloadTicketAttachment(ticketId, comment.id);
      downloadBlob(blob, comment.attachment_name);
    } catch {
      setError("Couldn't download that file.");
    }
  }

  return (
    <div>
      <div className="thin-scroll flex h-[32rem] flex-col gap-3 overflow-y-auto rounded-xl border border-black/8 dark:border-white/10 p-3">
        {loading ? (
          <p className="my-auto text-center text-xs text-ink/40 dark:text-ink-dark/40">Loading...</p>
        ) : comments.length === 0 ? (
          <p className="my-auto text-center text-xs text-ink/40 dark:text-ink-dark/40">No messages yet — say something below.</p>
        ) : (
          comments.map((c) => {
            // Admin is an observer, not a participant — there's no "you" in
            // that view, so align by role instead (customer left, team
            // right) rather than by who's logged in.
            const mine = readOnly ? c.author_role === "team" : c.author_role === auth.role;
            return (
              <div key={c.id} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
                <span className="px-1 text-[10px] text-ink/40 dark:text-ink-dark/40">
                  {readOnly ? c.author_name : mine ? "You" : c.author_name} · {new Date(c.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                </span>
                {c.attachment_name ? (
                  <AttachmentChip comment={c} onOpen={openAttachment} />
                ) : (
                  <span
                    className={`mt-0.5 max-w-[80%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                      mine ? "bg-brand text-white" : "bg-black/[0.05] dark:bg-white/10 text-ink dark:text-ink-dark"
                    }`}
                  >
                    {c.body}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

      {readOnly ? (
        !loading && <p className="mt-3 text-center text-xs text-ink/40 dark:text-ink-dark/40">Read-only — admin view</p>
      ) : messagingOpen ? (
        <form onSubmit={send} className="mt-3 flex items-center gap-2">
          <input ref={fileInputRef} type="file" onChange={handleFile} className="hidden" />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            aria-label="Attach a file"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ink/50 dark:text-ink-dark/50 hover:bg-black/5 dark:hover:bg-white/10 disabled:opacity-40"
          >
            {uploading ? <Loader2 size={15} className="animate-spin" /> : <Paperclip size={15} />}
          </button>
          <input
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
          />
          <button
            type="submit"
            disabled={sending || !body.trim()}
            aria-label="Send"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand text-white transition hover:opacity-90 disabled:opacity-40"
          >
            {sending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </form>
      ) : (
        !loading && (
          <p className="mt-3 text-center text-xs text-ink/40 dark:text-ink-dark/40">
            This ticket isn't in progress right now — messaging is closed.
          </p>
        )
      )}
    </div>
  );
}
