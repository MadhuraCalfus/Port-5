import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { KeyRound } from "lucide-react";
import { api } from "../api";
import { AuthFloatingIcons } from "../components/AuthFloatingIcons";
import { BrandMark } from "../components/BrandMark";
import { Button, Card } from "../components/primitives";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch {
      setError("That reset link is invalid or has expired — request a new one.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-backdrop relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <AuthFloatingIcons />
      <Card className="relative z-10 w-full max-w-sm p-6">
        <div className="mb-5 flex items-center justify-center">
          <div className="flex items-center gap-2.5">
            <BrandMark />
            <h1 className="font-display text-lg font-semibold text-ink dark:text-ink-dark">NykaaPulse</h1>
          </div>
        </div>

        <h2 className="text-base font-semibold text-ink dark:text-ink-dark">Set a new password</h2>

        {!token ? (
          <p className="mt-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">
            Missing reset token — open the link from your email again.
          </p>
        ) : done ? (
          <>
            <p className="mt-4 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600 dark:text-emerald-400">
              Password updated. You can log in now.
            </p>
            <Button className="mt-4 w-full" onClick={() => navigate("/login", { replace: true })}>
              Go to login
            </Button>
          </>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-3">
            <label className="block text-xs text-ink/70 dark:text-ink-dark/70">
              New password
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
              />
            </label>

            {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

            <Button type="submit" className="w-full" disabled={loading}>
              <KeyRound size={15} /> {loading ? "Updating..." : "Update password"}
            </Button>
          </form>
        )}

        <p className="mt-4 text-center text-xs text-ink/50 dark:text-ink-dark/50">
          <Link to="/login" className="font-medium text-brand dark:text-brand-dim hover:underline">
            Back to login
          </Link>
        </p>
      </Card>
    </div>
  );
}
