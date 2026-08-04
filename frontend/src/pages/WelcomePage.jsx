import { useNavigate } from "react-router-dom";
import { LineChart, Moon, Shield, Sun, User, Users } from "lucide-react";
import { useTheme } from "../hooks/useTheme";
import { AuthFloatingIcons } from "../components/AuthFloatingIcons";
import { Card } from "../components/primitives";

// Role values match ROLE_TABS in LoginPage.jsx exactly — a card here just
// deep-links into the matching login tab via ?role=.
const ROLE_CARDS = [
  { role: "user", label: "Customer", icon: User, hint: "Submit tickets, track status, and shop Nykaa Pulse." },
  { role: "pm", label: "Product Manager", icon: LineChart, hint: "See customer voice trends and act on them." },
  { role: "admin", label: "Support Admin", icon: Shield, hint: "Route tickets and manage the system." },
  { role: "team", label: "Support Team", icon: Users, hint: "Work the tickets assigned to your team." },
];

export function WelcomePage() {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();

  return (
    <div className="auth-backdrop relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <AuthFloatingIcons />
      <div className="relative z-10 w-full max-w-3xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">💄</span>
            <h1 className="font-display text-lg font-semibold text-ink dark:text-ink-dark">NykaaPulse</h1>
          </div>
          <button
            onClick={toggle}
            className="grid h-8 w-8 place-items-center rounded-lg text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>

        <div className="text-center">
          <h2 className="font-display text-2xl font-semibold text-ink dark:text-ink-dark sm:text-3xl">
            Welcome to NykaaPulse
          </h2>
          <p className="mt-2 text-sm text-ink/60 dark:text-ink-dark/60">Choose how you'd like to sign in.</p>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {ROLE_CARDS.map(({ role, label, icon: Icon, hint }) => (
            <button
              key={role}
              type="button"
              onClick={() => navigate(`/login?role=${role}`)}
              className="text-left"
            >
              <Card className="flex h-full items-start gap-4 p-5 transition hover:border-brand/40 hover:shadow-md">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand dark:text-brand-dim">
                  <Icon size={20} />
                </span>
                <div>
                  <h3 className="text-base font-semibold text-ink dark:text-ink-dark">{label}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-ink/60 dark:text-ink-dark/60">{hint}</p>
                </div>
              </Card>
            </button>
          ))}
        </div>

        <p className="mt-6 text-center text-xs text-ink/40 dark:text-ink-dark/40">
          Already know your way around?{" "}
          <button
            type="button"
            onClick={() => navigate("/login")}
            className="font-medium text-brand dark:text-brand-dim hover:underline"
          >
            Go straight to login
          </button>
        </p>
      </div>
    </div>
  );
}
