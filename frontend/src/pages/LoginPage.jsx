import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { LineChart, LogIn, Moon, Shield, Sun, User, Users } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../hooks/useTheme";
import { AuthFloatingIcons } from "../components/AuthFloatingIcons";
import { Button, Card } from "../components/primitives";

const ROLE_TABS = [
  { id: "user", label: "Customer", icon: User, hint: "Submit tickets and track their status." },
  { id: "team", label: "Team", icon: Users, hint: "Work the tickets assigned to your team." },
  { id: "admin", label: "Admin", icon: Shield, hint: "Route tickets and manage the system." },
  { id: "pm", label: "PM", icon: LineChart, hint: "See customer voice trends and act on them." },
];

export function LoginPage() {
  const { login, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [roleTab, setRoleTab] = useState("user");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const active = ROLE_TABS.find((r) => r.id === roleTab);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await login(email, password);
      if (res.role !== roleTab) {
        logout();
        const actual = ROLE_TABS.find((r) => r.id === res.role)?.label ?? res.role;
        setError(`That's a ${actual} account — switch to the "${actual}" tab above to log in.`);
        return;
      }
      navigate(`/${res.role}`, { replace: true });
    } catch {
      setError("Incorrect email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-backdrop relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <AuthFloatingIcons />
      <Card className="relative z-10 w-full max-w-sm p-6">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">🎟️</span>
            <h1 className="font-display text-lg font-semibold text-ink dark:text-ink-dark">TicketTrident</h1>
          </div>
          <button
            onClick={toggle}
            className="grid h-8 w-8 place-items-center rounded-lg text-ink/60 dark:text-ink-dark/60 hover:bg-black/5 dark:hover:bg-white/10"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>

        <div className="grid grid-cols-4 gap-1 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] p-1">
          {ROLE_TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setRoleTab(id);
                setError(null);
              }}
              className={clsx(
                "flex flex-col items-center gap-1 rounded-lg py-2 text-xs font-medium transition",
                roleTab === id
                  ? "bg-surface dark:bg-surface-dark text-brand dark:text-brand-dim shadow-sm"
                  : "text-ink/50 dark:text-ink-dark/50 hover:text-ink dark:hover:text-ink-dark",
              )}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>

        <h2 className="mt-4 text-base font-semibold text-ink dark:text-ink-dark">{active.label} login</h2>
        <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">{active.hint}</p>

        <form onSubmit={submit} className="mt-4 space-y-3">
          <label className="block text-xs text-ink/70 dark:text-ink-dark/70">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
            />
          </label>
          <label className="block text-xs text-ink/70 dark:text-ink-dark/70">
            Password
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
            />
          </label>

          {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

          <Button type="submit" className="w-full" disabled={loading}>
            <LogIn size={15} /> {loading ? "Logging in..." : `Log in as ${active.label.toLowerCase()}`}
          </Button>
        </form>

        {roleTab === "user" && (
          <p className="mt-4 text-center text-xs text-ink/50 dark:text-ink-dark/50">
            New customer?{" "}
            <Link to="/signup" className="font-medium text-brand dark:text-brand-dim hover:underline">
              Sign up
            </Link>
          </p>
        )}
      </Card>
    </div>
  );
}
