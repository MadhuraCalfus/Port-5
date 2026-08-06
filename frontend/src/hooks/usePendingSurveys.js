import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const SEEN_KEY = "nykaa_seen_survey_ids";

function loadSeen() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function saveSeen(set) {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify([...set]));
  } catch {
    // best-effort — a full/blocked localStorage just means the "new survey"
    // toast may repeat, not a functional break.
  }
}

// Polls for pending (PM-authored, unanswered) surveys so the customer
// header's avatar can show a badge count and pop a one-time toast the first
// time a survey id shows up that this browser hasn't seen before. There's
// no server-side "seen" timestamp for custom surveys, so "new" is tracked
// client-side in localStorage.
export function usePendingSurveys() {
  const [pending, setPending] = useState([]);
  const [newSurvey, setNewSurvey] = useState(null);
  const seenRef = useRef(loadSeen());

  async function refresh() {
    try {
      const r = await api.pendingSurveys();
      setPending(r.surveys);
      const unseen = r.surveys.find((s) => !seenRef.current.has(s.id));
      if (unseen) setNewSurvey(unseen);
    } catch {
      // best-effort — surveys are a notification, not core flow.
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 45000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function markAllSeen() {
    setPending((current) => {
      current.forEach((s) => seenRef.current.add(s.id));
      saveSeen(seenRef.current);
      return current;
    });
    setNewSurvey(null);
  }

  return { pending, newSurvey, refresh, markAllSeen };
}
