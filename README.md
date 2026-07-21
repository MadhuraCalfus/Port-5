#  TicketTrident – Route Smarter. Resolve Faster.

An AI-powered support ticket platform. A customer describes an issue; AI tries to resolve it on the spot with concrete steps, and only becomes a real ticket — classified into **category, priority, team, tone, and a one-line reason** as strict, schema-validated JSON — if that isn't enough. Three account types (Customer, Team, Admin) each get their own dashboard, and a customer and their assigned team can message each other, attachments included, right on the ticket.

Built for **Port·04 — The Senate of Gods**.

---

## Why this exists

Support teams drown in tickets because triage is repetitive, low-judgment work that still requires reading and context. That's exactly the profile of task an LLM is good at: it reads the message, understands intent (including sarcasm, negation, and multi-issue tickets a keyword filter can't), and returns a structured decision in under two seconds.


## What's actually in the app

Three account types, each with their own login and dashboard:

### Customer
- Describes an issue in plain language — **AI tries to resolve it immediately**, suggesting concrete steps before any ticket is created. If that's not enough, one click ("Still not solved — raise a ticket") files a real ticket; if it helped ("That solved it"), no ticket is ever created — the case is just logged as AI-resolved so an Admin can still see it.
- Tracks their own tickets and status (In queue → Assigned → In Progress → Resolved).
- Once a ticket is **In Progress**, can message the assigned team directly on that ticket, attachments included — closed again once it's Resolved.

### Team member
- Account created by an Admin (who sets the password directly — no auto-generated password to relay), scoped to one team.
- Works only their own team's queue; status only moves forward (Routed → In Progress → Resolved, never back).
- Chats with the customer on any ticket they're actively working, with an unread-message badge.
- Self-service password reset via a time-limited emailed link.

### Admin
- **New Tickets queue**: every incoming ticket is classified by AI automatically the moment it's seen — no manual "route" click. Review the AI's pick (or override category/priority/team), select any number, and "Confirm Route" assigns them all at once.
- **All Tickets**: every ticket ever submitted, filterable by status and by team (dropdown), searchable by ID/customer name/message text, with a read-only view into each ticket's chat history and a one-click **PDF report** per ticket.
- **AI Resolved**: every case where AI's self-service suggestion solved the customer's issue before a ticket ever existed — a running total, searchable by customer/message, sortable by date — visibility into deflected volume that would otherwise never show up anywhere.
- **Teams**: workload summary (total/assigned/in-progress/resolved) across every team that actually exists in this deployment, plus a PDF export.
- **Team Members**: create/remove team accounts.
- **Manual vs AI Race**: pick a ticket, triage it yourself with a real stopwatch, then let AI classify the same ticket — a genuine measured comparison, not an assumed number.
- **Demo**: routes all 30 bundled sample tickets in one pass.
- **Analytics**: tickets routed vs. resolved by AI (with a deflection-rate callout), tickets generated over time, AI vs. manual time (clearly labeled as measured vs. assumed), status/priority/category/team/tone breakdowns, ambiguity/escalation/agreement stats — exportable as a PDF.

---

## Per-ticket PDF reports

Beyond the Analytics and Teams PDF exports, an Admin can generate a full report for any single ticket: its details, who's handled it, and the entire chat transcript — with every attachment rendered as its own page in the same PDF. Images get embedded directly; an uploaded PDF has its actual pages merged straight in (not just linked); text and Word documents get their content extracted and typeset as a page. Built with `reportlab` + `pypdf`, entirely in memory.

---

## Quick start

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL (required) + a provider key (optional)
uvicorn app.main:app --reload --port 8000
```

`DATABASE_URL` is the one required setting — a Postgres connection string. With [Supabase](https://supabase.com): create a free project, then **Project Settings → Database → Connection string → URI**, and use the "Session" pooler string (port 5432) for this app's single long-running process. Any Postgres works, including a local one for dev (`createdb tickettrident && DATABASE_URL=postgresql://localhost/tickettrident`).

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api/*` to the backend on port 8000 in dev.

### One command for both

```bash
./dev.sh
```

### Single-server "production" mode

```bash
cd frontend && npm run build && cd ..
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
```

FastAPI detects `frontend/dist` and serves the built UI directly from `http://localhost:8000/` — one process, one port, nothing else running.

### CLI

```bash
cd backend && source .venv/bin/activate
python -m app.cli route "I was charged twice and support has ignored me for a week!!"
python -m app.cli route "I was charged twice" --compare   # + keyword baseline side by side
python -m app.cli demo                                     # routes all 30 sample tickets
python -m app.cli health                                   # live vs mock mode, current model
```

---

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| LLM | OpenAI - Structured Outputs / JSON Schema on each | JSON Schema enforcement at the API level, not a prompt convention. 
| Backend | FastAPI + Pydantic | Schema-first by default; the same Pydantic models that validate an LLM's output also generate the OpenAPI docs. |
| Auth | PyJWT + bcrypt | Stateless JWTs carrying role (`user`/`team`/`admin`) and identity; bcrypt-hashed passwords, never stored or logged in plaintext. |
| Storage | Postgres (Supabase) via `psycopg` | Real persistence and a full audit trail — tickets, users, team members, chat messages, and attachment bytes — with a managed host that survives restarts/redeploys and supports more than one backend process. |
| PDF generation | `reportlab` + `pypdf` (backend, per-ticket reports); `jsPDF` + `jspdf-autotable` (frontend, Analytics/Teams exports) | Per-ticket reports need to merge real pages from arbitrary uploaded PDFs and embed images — a proper PDF library, not just a print-to-PDF trick. |
| Frontend | React + JavaScript + Vite + React Router | Fast dev loop with no build-time type layer; three role-gated route trees (`/user`, `/team`, `/admin`). |
| Styling | Tailwind CSS v4 | Design tokens (`@theme`) keep light/dark and priority/tone/status colors consistent across every component without a component library dependency. |
| Charts | Recharts | Composable, React-native chart primitives for the analytics dashboard. |

---

## Workflow

How one issue actually moves through the system, end to end:

```mermaid
flowchart TD
    A["Customer describes an issue"] --> B{"AI suggests self-service steps"}
    B -->|"Solved"| C["Logged as AI-resolved\nno ticket, no team ever involved"]
    C --> P["Visible in Admin's AI Resolved tab + Analytics"]
    B -->|"Still stuck"| D["Raise a ticket · status: New"]
    D --> E["Admin's New Tickets queue"]
    E --> F["AI auto-classifies:\ncategory / priority / team / tone"]
    F --> G{"Admin reviews the pick"}
    G -->|"Approve as-is"| H["Confirm Route"]
    G -->|"Override category/priority/team"| H
    H --> I["Status: Routed — assigned to a team"]
    I --> J["Team moves it to In Progress"]
    J --> K["Customer + Team chat on the ticket\nattachments included"]
    K --> L["Team resolves it"]
    L --> M["Status: Resolved — chat closes"]
    M --> N["Shows up in All Tickets, Analytics, Teams"]
    N --> O["Admin can pull a full PDF report anytime"]
```

1. **Customer describes an issue.** No ticket exists yet — AI reads it and suggests concrete steps to try immediately.
2. **Solved?** If so, no ticket is ever created — the case is logged separately as AI-resolved, so an Admin can still see it in the **AI Resolved** tab and in Analytics' deflection-rate stats.
3. **Still stuck** → one click ("raise a ticket") actually creates it, with status `New` and no classification yet.
4. **Admin's New Tickets queue** picks it up automatically — every ticket there gets classified by AI (category, priority, team, tone, confidence, one-line reasoning) the moment it's seen, no manual "route" click required.
5. **Admin reviews** the AI's pick — approve it as-is, or override category/priority/team — then selects any number of reviewed tickets and hits **Confirm Route**, which assigns them all at once. Status moves to `Routed`.
6. **The assigned team** picks it up from their own queue and moves it to `In Progress`.
7. **Once In Progress**, the customer and that team can message each other directly on the ticket, attachments included — this is enforced server-side, not just hidden in the UI.
8. **The team resolves it** → status `Resolved`, and the chat closes on both sides.
9. **From here it's just visible**, everywhere an Admin looks: All Tickets, the Teams workload summary, and Analytics — and an Admin can generate a full PDF report for that one ticket at any point, transcript and attachments included.

---

## Screenshots

### Getting started

**Sign in**
Three account types — Customer, Team, and Admin — each with their own login on one page.

<img src="screenshots/Sign up Sign In Page.png" width="700" />

### Customer

**Describe an issue**
The customer describes a problem in plain language; AI tries to help before any ticket exists.

<img src="screenshots/customer ui.png" width="700" />

**AI suggests steps to try**
AI returns concrete self-service steps and a summary — from here the customer confirms it worked or raises a ticket anyway.

<img src="screenshots/customer ai resolved.png" width="700" />

**Resolved by AI**
Every issue AI solved on the spot is logged here, with the exact steps that fixed it — no ticket, no team ever involved.

<img src="screenshots/customer ai history.png" width="700" />

**AI defers to a human**
For a genuine billing dispute, AI recognizes it should be handled by a person and points straight to raising a ticket instead of guessing.

<img src="screenshots/customer ui 2.png" width="700" />

**A freshly raised ticket**
Right after raising a ticket it shows status "In queue", waiting for an admin to review the AI's routing.

<img src="screenshots/customer my tickets.png" width="700" />

**Tracking a ticket to resolution**
The status stepper shows a ticket's full journey from In queue to Resolved.

<img src="screenshots/Customer - issue resolved.png" width="700" />

**New reply from the team**
An unread-message badge on "Message team" tells the customer their assigned team just replied.

<img src="screenshots/customer- chat received.png" width="700" />

**Chatting with the team**
Customer and team message each other directly on the ticket once it's In Progress, right through to resolution.

<img src="screenshots/chat.png" width="700" />

### Team member

**Replying to a customer**
A team member opens a ticket's chat thread to ask for more detail before working the issue.

<img src="screenshots/chat application from team.png" width="700" />

**Marking a ticket resolved**
Once the issue is fixed, the team moves the ticket to Resolved, closing the chat on both sides.

<img src="screenshots/Team - issue resolved.png" width="700" />

### Admin

**AI's classification, up close**
Category, priority, team, tone, and confidence for one ticket, plus the naive keyword baseline shown for comparison.

<img src="screenshots/Admin - routing.png" width="700" />

**New Tickets queue**
Every incoming ticket is classified automatically the moment it's seen; select any number and Confirm Route to assign them all at once.

<img src="screenshots/Admin - new tickets.png" width="700" />

**All Tickets**
Every ticket ever submitted, filterable by status and by team, searchable by ID, name, or message.

<img src="screenshots/Admin - all tickets.png" width="700" />

**Reading a ticket's chat history**
An admin gets a read-only view into any ticket's full conversation, without being able to reply.

<img src="screenshots/Admin - access to chats.png" width="700" />

**Filtered to Resolved**
The same All Tickets table, narrowed instantly to just the resolved ones.

<img src="screenshots/Admin - resolved.png" width="700" />

**AI Resolved, across every customer**
Every case where a customer's issue was closed out by AI on its own, with a running total and the exact steps it suggested.

<img src="screenshots/Admin - ai resolved.png" width="700" />

**Team workload**
Assigned / in-progress / resolved counts for every team that actually exists in this deployment.

<img src="screenshots/Admin - Teams.png" width="700" />

**Managing team accounts**
An admin creates a login for a support team member, scoped to exactly one team.

<img src="screenshots/Admin - team members.png" width="700" />

**Manual vs AI — timing yourself**
An admin classifies a real ticket by hand with a stopwatch running, before letting AI take the exact same ticket.

<img src="screenshots/Admin - manual ai race.png" width="700" />

**Manual vs AI — the result**
A genuine, measured comparison — here AI was 6x faster than manual triage on the same ticket.

<img src="screenshots/Admin - manual ai race 2.png" width="700" />

**Demo: 30 sample tickets**
One click routes the full bundled demo set, spanning every tone, priority, and team.

<img src="screenshots/Admin - demo 1.png" width="700" />

**Demo results**
Every one of the 30 sample tickets routed, with category, priority, team, tone, and confidence for each.

<img src="screenshots/Admin -  demo.png" width="700" />

**Analytics**
Tickets routed vs. resolved by AI, time saved, tickets over time, and every breakdown in one dashboard.

<img src="screenshots/Admin - analytics.png" width="700" />

**Analytics, exported**
The same numbers as a shareable PDF report, one click away from the dashboard.

<img src="screenshots/Analytics report.png" width="700" />

**A single ticket's full story**
Details, the entire chat transcript, and every attachment merged into one PDF report.

<img src="screenshots/Admin - entire process report.png" width="700" />
