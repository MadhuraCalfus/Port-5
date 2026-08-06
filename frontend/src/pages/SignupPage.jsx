import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { AuthFloatingIcons } from "../components/AuthFloatingIcons";
import { BrandMark } from "../components/BrandMark";
import { Button, Card } from "../components/primitives";

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signup(name, email, password);
      navigate("/user", { replace: true });
    } catch (err) {
      setError(err.message.includes("409") ? "An account with that email already exists." : "Couldn't sign up — please try again.");
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
        <h2 className="text-base font-semibold text-ink dark:text-ink-dark">Create your account</h2>
        <p className="mt-1 text-sm text-ink/60 dark:text-ink-dark/60">Submit support tickets and track their status.</p>

        <form onSubmit={submit} className="mt-4 space-y-3">
          <label className="block text-xs text-ink/70 dark:text-ink-dark/70">
            Name
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
            />
          </label>
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
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-black/10 dark:border-white/15 bg-transparent px-3 py-2 text-sm text-ink dark:text-ink-dark"
            />
          </label>

          {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}

          <Button type="submit" className="w-full" disabled={loading}>
            <UserPlus size={15} /> {loading ? "Creating account..." : "Sign up"}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-ink/50 dark:text-ink-dark/50">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand dark:text-brand-dim hover:underline">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  );
}
