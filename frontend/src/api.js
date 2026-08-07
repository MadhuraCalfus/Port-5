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

// FastAPI error bodies are JSON (a plain `{detail: "..."}` or a Pydantic
// validation list of `{msg: "..."}` entries) — surfacing that raw blob to
// the user (e.g. in a chat error bubble) reads as a crash. Pull out the
// human-readable message instead, falling back to the raw body for
// non-JSON error responses (proxies, 502s, etc).
function errorMessageFromBody(status, statusText, body) {
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
  } catch {
    // not JSON — fall through to the raw body below
  }
  return body || `${status} ${statusText}`;
}

async function request(path, options) {
  const res = await fetch(`/api${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...authHeader() },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(errorMessageFromBody(res.status, res.statusText, body));
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
    throw new Error(errorMessageFromBody(res.status, res.statusText, body));
  }
  return res.json();
}

async function downloadFile(path) {
  const res = await fetch(`/api${path}`, { cache: "no-store", headers: { ...authHeader() } });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(errorMessageFromBody(res.status, res.statusText, body));
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

  analytics: (periodType, periodKey) =>
    request(`/analytics${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

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

  pmTrend: (periodType = "weekly", periodKey) =>
    request(`/pm/insights/trend?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  pmGetReport: (periodType = "weekly", periodKey) =>
    request(`/pm/insights/report?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  pmGenerateReport: (periodType = "weekly", periodKey) =>
    request(`/pm/insights/report/generate?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`, { method: "POST" }),

  pmListActions: (periodType = "weekly", periodKey) =>
    request(`/pm/insights/actions?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  pmGenerateActions: (periodType = "weekly", periodKey) =>
    request(`/pm/insights/actions/generate?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`, { method: "POST" }),

  pmUpdateActionStatus: (id, status) =>
    request(`/pm/insights/actions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),

  pmSentimentSeries: (periodType = "weekly", numPeriods = 8, endPeriodKey) =>
    request(
      `/pm/insights/sentiment-series?period_type=${periodType}&num_periods=${numPeriods}${endPeriodKey ? `&end_period_key=${endPeriodKey}` : ""}`,
    ),

  pmPeriodItems: (periodType = "weekly", periodKey) =>
    request(`/pm/insights/items?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  pmInsightsRange: (start, end) => request(`/pm/insights/range?start=${start}&end=${end}`),

  // ---- pm: custom surveys ----
  pmCreateSurvey: (title, questions) =>
    request("/pm/surveys", { method: "POST", body: JSON.stringify({ title, questions }) }),

  pmListSurveys: () => request("/pm/surveys"),

  pmSurveysOverview: (periodType, periodKey) =>
    request(`/pm/surveys/overview${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

  pmSendSurvey: (id) => request(`/pm/surveys/${id}/send`, { method: "POST" }),

  pmSurveyResults: (id, periodType, periodKey) =>
    request(`/pm/surveys/${id}/results${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

  // ---- customer: answering custom surveys ----
  pendingSurveys: () => request("/surveys/pending"),

  answerSurvey: (id, answers) => request(`/surveys/${id}/answer`, { method: "POST", body: JSON.stringify({ answers }) }),

  // ---- team ----
  teamTickets: () => request("/team/tickets"),

  teamUpdateStatus: (id, status) =>
    request(`/team/tickets/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  nykaaTeamOrderTickets: () => request("/nykaa/team/order-tickets"),

  nykaaTeamUpdateTicketStatus: (ticketId, status) =>
    request(`/nykaa/team/order-tickets/${ticketId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  // ---- nykaa pulse: catalog (any logged-in role can browse) ----
  nykaaListCategories: () => request("/nykaa/catalog/categories"),

  nykaaListBrands: (categoryId) =>
    request(`/nykaa/catalog/brands${categoryId ? `?category_id=${categoryId}` : ""}`),

  nykaaListSubcategories: (categoryId) =>
    request(`/nykaa/catalog/subcategories${categoryId ? `?category_id=${categoryId}` : ""}`),

  nykaaListProducts: ({ categoryId, brandId, subcategoryId, search } = {}) => {
    const params = new URLSearchParams();
    if (categoryId) params.set("category_id", categoryId);
    if (brandId) params.set("brand_id", brandId);
    if (subcategoryId) params.set("subcategory_id", subcategoryId);
    if (search) params.set("search", search);
    const qs = params.toString();
    return request(`/nykaa/catalog/products${qs ? `?${qs}` : ""}`);
  },

  nykaaGetProduct: (id) => request(`/nykaa/catalog/products/${id}`),

  // Phase 4 "what customers say" — lazy-fetched per product (only once its
  // panel is expanded), never eagerly for the whole grid.
  nykaaProductSummary: (productId) => request(`/nykaa/catalog/products/${productId}/summary`),

  // Phase 4 "ask the reviews" — grounded Q&A over one product's published reviews.
  nykaaAskReviews: (productId, question) =>
    request(`/nykaa/catalog/products/${productId}/ask`, { method: "POST", body: JSON.stringify({ question }) }),

  // PM Analytics chatbot — free-text question over feedback/reviews/tickets,
  // answered via a guardrailed generated SQL query (backend nykaa_chat_sql.py).
  nykaaAnalyticsChat: (question) =>
    request(`/nykaa/pm/analytics-chat`, { method: "POST", body: JSON.stringify({ question }) }),

  // "Didn't find what you're looking for?" follow-up — other products in
  // the same subcategory, ranked by rating.
  nykaaProductAlternatives: (productId) => request(`/nykaa/catalog/products/${productId}/alternatives`),

  // Beauty Portfolio — published reviews for one product, each tagged with
  // the reviewer's current skin_type/hair_type (nullable). Same lazy-fetch-
  // on-expand pattern as nykaaProductSummary.
  nykaaProductReviews: (productId) => request(`/nykaa/catalog/products/${productId}/reviews`),

  // ---- nykaa pulse: beauty portfolio (customer) ----
  nykaaGetBeautyProfile: () => request("/nykaa/beauty-profile"),

  nykaaUpdateBeautyProfile: (body) => request("/nykaa/beauty-profile", { method: "PUT", body: JSON.stringify(body) }),

  nykaaRecommendedProducts: (section = "skin") => request(`/nykaa/catalog/recommended?section=${section}`),

  nykaaBeautyRoutine: () => request("/nykaa/beauty-profile/routine"),

  // ---- nykaa pulse: orders, reviews, delivery rating, raise-ticket (customer) ----
  nykaaPlaceOrder: (items) => request("/nykaa/orders", { method: "POST", body: JSON.stringify({ items }) }),

  nykaaMyOrders: () => request("/nykaa/orders/mine"),

  nykaaSubmitReview: (orderId, itemId, body) =>
    request(`/nykaa/orders/${orderId}/items/${itemId}/review`, { method: "POST", body: JSON.stringify(body) }),

  nykaaGenerateReviewTitle: (description) =>
    request("/nykaa/reviews/generate-title", { method: "POST", body: JSON.stringify({ description }) }),

  nykaaSubmitDeliveryRating: (orderId, body) =>
    request(`/nykaa/orders/${orderId}/delivery-rating`, { method: "POST", body: JSON.stringify(body) }),

  nykaaSubmitAppFeedback: (body) => request("/nykaa/app-feedback", { method: "POST", body: JSON.stringify(body) }),

  // Multi-turn "Raise a Ticket" chat — one turn per call; keeps returning
  // {reply, escalated: false} while the bot is still trying to help, then
  // {reply, escalated: true, ticket} once it hands off to a human team.
  nykaaChatTurn: (orderId, itemId, message) =>
    request(`/nykaa/orders/${orderId}/items/${itemId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  // Prior bot-phase turns for this item — lets a reopened chat restore
  // where it left off instead of restarting from the greeting.
  nykaaChatHistory: (orderId, itemId) => request(`/nykaa/orders/${orderId}/items/${itemId}/chat`),

  // A file attached during the bot phase, before any ticket exists yet.
  nykaaUploadChatAttachment: (orderId, itemId, file) =>
    uploadFile(`/nykaa/orders/${orderId}/items/${itemId}/chat/attachments`, file),

  nykaaDownloadChatAttachment: (orderId, itemId, turnId) =>
    downloadFile(`/nykaa/orders/${orderId}/items/${itemId}/chat/attachments/${turnId}`),

  // ---- nykaa pulse: np_ticket comment threads (post-escalation, customer <-> team) ----
  nykaaTicketComments: (ticketId) => request(`/nykaa/tickets/${ticketId}/comments`),

  nykaaPostTicketComment: (ticketId, body) =>
    request(`/nykaa/tickets/${ticketId}/comments`, { method: "POST", body: JSON.stringify({ body }) }),

  nykaaUploadTicketAttachment: (ticketId, file) => uploadFile(`/nykaa/tickets/${ticketId}/attachments`, file),

  nykaaDownloadTicketAttachment: (ticketId, commentId) => downloadFile(`/nykaa/tickets/${ticketId}/attachments/${commentId}`),

  nykaaMarkTicketCommentsRead: (ticketId) => request(`/nykaa/tickets/${ticketId}/comments/read`, { method: "POST" }),

  nykaaSubmitCsat: (ticketId, rating, comment) =>
    request(`/nykaa/tickets/${ticketId}/csat`, { method: "POST", body: JSON.stringify({ rating, comment: comment ?? null }) }),

  // "Show off your look!" — an optional photo attached to a review.
  nykaaUploadReviewPhoto: (orderId, itemId, file) =>
    uploadFile(`/nykaa/orders/${orderId}/items/${itemId}/review/photo`, file),

  // The photo endpoint requires an Authorization header, so a plain
  // <img src="..."> can't authenticate against it directly. Instead this
  // downloads the image as a blob (same authenticated-fetch pattern as
  // downloadFile/downloadTicketAttachment) and hands back an object URL —
  // that IS a plain string an <img> tag can use directly. Mirrors how
  // CommentThread.jsx's openAttachment() downloads ticket attachments.
  // Caller is responsible for URL.revokeObjectURL() once done with it.
  nykaaReviewPhotoUrl: async (orderId, itemId) => {
    const blob = await downloadFile(`/nykaa/orders/${orderId}/items/${itemId}/review/photo`);
    return URL.createObjectURL(blob);
  },

  // ---- nykaa pulse: admin (order oversight) ----
  nykaaAdminListOrders: () => request("/nykaa/admin/orders"),

  nykaaAdminListTickets: () => request("/nykaa/admin/tickets"),

  nykaaAdminAnalytics: (periodType, periodKey) =>
    request(`/nykaa/admin/analytics${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

  nykaaDownloadTicketReport: (ticketId) => downloadFile(`/nykaa/admin/tickets/${ticketId}/report.pdf`),

  // ---- nykaa pulse: resolved by AI, no ticket raised (admin + team) ----
  nykaaAiResolvedChats: () => request("/nykaa/ai-resolved-chats"),

  nykaaAiResolvedChatTranscript: (orderId, itemId) => request(`/nykaa/ai-resolved-chats/${orderId}/${itemId}`),

  // ---- nykaa pulse: pm catalog-aware analytics (Phase 3) ----
  nykaaPmOverview: (periodType, periodKey) =>
    request(`/nykaa/pm/overview${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

  nykaaPmFeedback: () => request("/nykaa/pm/feedback"),

  nykaaPmProductRollup: () => request("/nykaa/pm/product-rollup"),

  nykaaPmAppFeedback: () => request("/nykaa/pm/app-feedback"),

  nykaaPmAppFeedbackAnalytics: (periodType, periodKey) =>
    request(`/nykaa/pm/app-feedback/analytics${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

  nykaaPmDeliveryFeedbackAnalytics: (periodType, periodKey) =>
    request(`/nykaa/pm/delivery-feedback/analytics${periodType ? `?period_type=${periodType}&period_key=${periodKey}` : ""}`),

  nykaaPmBrandBreakdown: (periodType = "monthly", periodKey) =>
    request(`/nykaa/pm/brand-breakdown?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  nykaaPmCategoryBreakdown: (periodType = "monthly", periodKey) =>
    request(`/nykaa/pm/category-breakdown?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  nykaaPmWeeklyReport: (periodType = "weekly", periodKey) =>
    request(`/nykaa/pm/weekly-report?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),

  // Phase 4 "brand scorecards" — one short AI-written line per brand, layered
  // on top of the same brand-breakdown numbers the Brands tab already shows.
  nykaaPmBrandScorecards: (periodType = "monthly", periodKey) =>
    request(`/nykaa/pm/brand-scorecards?period_type=${periodType}${periodKey ? `&period_key=${periodKey}` : ""}`),
};
