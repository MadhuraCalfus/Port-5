function authHeader() {
  try {
    const raw = sessionStorage.getItem("auth");
    if (!raw) return {};
    const { access_token } = JSON.parse(raw);
    return access_token ? { Authorization: `Bearer ${access_token}` } : {};
  } catch {
    return {};
  }
}

async function request(path, options) {
  const res = await fetch(`/api${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...authHeader() },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

// Bypasses request()'s forced JSON content-type — a FormData upload needs
// the browser to set its own multipart boundary header instead.
async function uploadFile(path, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`/api${path}`, { method: "POST", cache: "no-store", headers: { ...authHeader() }, body: formData });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

async function downloadFile(path) {
  const res = await fetch(`/api${path}`, { cache: "no-store", headers: { ...authHeader() } });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.blob();
}

export const api = {
  health: () => request("/health"),

  // ---- auth ----
  signup: (name, email, password) =>
    request("/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) }),

  login: (email, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  me: () => request("/auth/me"),

  forgotPassword: (email) => request("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),

  resetPassword: (token, newPassword) =>
    request("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password: newPassword }) }),

  // ---- admin sandbox tools (Route a Ticket / Race / Demo / Analytics / History) ----
  route: (message, opts) =>
    request("/route", {
      method: "POST",
      body: JSON.stringify({ message, ...opts }),
    }),

  tickets: (limit = 50, offset = 0) => request(`/tickets?limit=${limit}&offset=${offset}`),

  ticket: (id) => request(`/tickets/${id}`),

  feedback: (id, payload) =>
    request(`/tickets/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  analytics: () => request("/analytics"),

  sampleTickets: () => request("/sample-tickets"),

  runDemo: (tickets) =>
    request("/demo/run", {
      method: "POST",
      body: JSON.stringify({ tickets }),
    }),

  // ---- user ----
  suggestResolution: (message) => request("/tickets/suggest", { method: "POST", body: JSON.stringify({ message }) }),

  markSelfResolved: (message, summary, steps) =>
    request("/tickets/self-resolved", { method: "POST", body: JSON.stringify({ message, summary, steps }) }),

  createTicket: (message) => request("/tickets", { method: "POST", body: JSON.stringify({ message }) }),

  myTickets: () => request("/my-tickets"),

  mySelfResolved: () => request("/my-self-resolved"),

  submitSurvey: (rating, comment) =>
    request("/surveys", { method: "POST", body: JSON.stringify({ rating, comment: comment || null }) }),

  // ---- ticket comments (customer <-> team, shared by whichever role owns the ticket) ----
  ticketComments: (id) => request(`/tickets/${id}/comments`),

  postTicketComment: (id, body) =>
    request(`/tickets/${id}/comments`, { method: "POST", body: JSON.stringify({ body }) }),

  markTicketCommentsRead: (id) => request(`/tickets/${id}/comments/read`, { method: "POST" }),

  uploadTicketAttachment: (id, file) => uploadFile(`/tickets/${id}/attachments`, file),

  downloadTicketAttachment: (ticketId, commentId) => downloadFile(`/tickets/${ticketId}/attachments/${commentId}`),

  // ---- admin: ticket queue + team management ----
  adminNewTickets: () => request("/admin/tickets/new"),

  adminRouteTicket: (id) => request(`/admin/tickets/${id}/route`, { method: "POST" }),

  // payload carries category/priority/team (AI's pick, or the admin's
  // override) plus the rest of the previewed classification — Confirm
  // Route persists it in one shot rather than the backend re-classifying.
  adminAssignTicket: (id, payload) =>
    request(`/admin/tickets/${id}/assign`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  adminTeamSummary: () => request("/admin/team-summary"),

  adminAllTickets: () => request("/admin/tickets"),

  adminSelfResolved: () => request("/admin/self-resolved"),

  downloadTicketReport: (id) => downloadFile(`/admin/tickets/${id}/report.pdf`),

  adminListTeamMembers: () => request("/admin/team-members"),

  adminCreateTeamMember: (name, email, password, team) =>
    request("/admin/team-members", {
      method: "POST",
      body: JSON.stringify({ name, email, password, team }),
    }),

  adminDeleteTeamMember: (id) => request(`/admin/team-members/${id}`, { method: "DELETE" }),

  // ---- pm: feedback insights ----
  pmImportFeedback: (sourceType, items) =>
    request("/pm/feedback/import", { method: "POST", body: JSON.stringify({ source_type: sourceType, items }) }),

  pmFeedback: (limit = 200) => request(`/pm/feedback?limit=${limit}`),

  pmInsights: (periodType = "weekly", periodKey) =>
    request(`/pm/insights?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  // ---- team ----
  teamTickets: () => request("/team/tickets"),

  teamUpdateStatus: (id, status) =>
    request(`/team/tickets/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
};
