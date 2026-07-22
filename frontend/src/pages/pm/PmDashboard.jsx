import { useState } from "react";
import { LayoutDashboard, TrendingUp, Upload } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { useTheme } from "../../hooks/useTheme";
import { Header } from "../../components/Header";
import { OverviewPage } from "./OverviewPage";
import { ThemesTrendsPage } from "./ThemesTrendsPage";
import { ImportFeedbackPage } from "./ImportFeedbackPage";

// Reports/actions tabs land in later phases, added to this same TABS list.
const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "themes", label: "Themes & Trends", icon: TrendingUp },
  { id: "import", label: "Import Feedback", icon: Upload },
];

export function PmDashboard() {
  const [tab, setTab] = useState("overview");
  const { theme, toggle } = useTheme();
  const { auth, logout } = useAuth();

  return (
    <div className="app-backdrop min-h-screen">
      <Header
        tabs={TABS}
        tab={tab}
        onTab={setTab}
        theme={theme}
        onToggleTheme={toggle}
        userLabel={`${auth.name} · product manager`}
        onLogout={logout}
      />
      <main className="mx-auto max-w-6xl px-4 py-8">
        {tab === "overview" && <OverviewPage />}
        {tab === "themes" && <ThemesTrendsPage />}
        {tab === "import" && <ImportFeedbackPage />}
      </main>
    </div>
  );
}
