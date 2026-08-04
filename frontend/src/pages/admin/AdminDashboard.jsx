import { useEffect, useState } from "react";
import { BarChart3, Building2, Clock, Inbox, Sparkles, Table2, Users, Zap } from "lucide-react";
import { api } from "../../api";
import { useAuth } from "../../auth/AuthContext";
import { useTheme } from "../../hooks/useTheme";
import { Header } from "../../components/Header";
import { MegaTabs } from "../../components/MegaTabs";
import { RaceTab } from "../../components/RaceTab";
import { DemoTab } from "../../components/DemoTab";
import { AnalyticsTab } from "../../components/AnalyticsTab";
import { NewTicketsQueuePage } from "./NewTicketsQueuePage";
import { AllTicketsPage } from "./AllTicketsPage";
import { AiResolvedPage } from "./AiResolvedPage";
import { TeamsOverviewPage } from "./TeamsOverviewPage";
import { TeamMembersPage } from "./TeamMembersPage";
import { NykaaAdminTicketsPage } from "./nykaa/NykaaAdminTicketsPage";
import { NykaaAiResolvedPage } from "../../components/NykaaAiResolvedPage";
import { NykaaTeamsPage } from "./nykaa/NykaaTeamsPage";
import { NykaaTeamMembersPage } from "./nykaa/NykaaTeamMembersPage";
import { NykaaAnalyticsTab } from "./nykaa/NykaaAnalyticsTab";

const TABS = [
  { id: "queue", label: "New Tickets", icon: Inbox },
  { id: "all", label: "All Tickets", icon: Table2 },
  { id: "ai-resolved", label: "AI Resolved", icon: Sparkles },
  { id: "teams", label: "Teams", icon: Building2 },
  { id: "team-members", label: "Team Members", icon: Users },
  { id: "race", label: "Manual vs AI Race", icon: Clock },
  { id: "demo", label: "Demo (30 Tickets)", icon: Zap },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
];

const MEGA_TABS = [
  { id: "tickets", label: "TicketTrident" },
  { id: "nykaa-pulse", label: "Nykaa Pulse" },
];

const NYKAA_TABS = [
  { id: "tickets", label: "Tickets", icon: Table2 },
  { id: "ai-resolved", label: "AI Resolved", icon: Sparkles },
  { id: "teams", label: "Teams", icon: Building2 },
  { id: "team-members", label: "Team Members", icon: Users },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
];

export function AdminDashboard() {
  const [megaTab, setMegaTab] = useState("tickets");
  const [tab, setTab] = useState("queue");
  const [nykaaTab, setNykaaTab] = useState("tickets");
  const { theme, toggle } = useTheme();
  const [health, setHealth] = useState(null);
  const { logout } = useAuth();

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, [tab]);

  const nykaaWide = nykaaTab === "tickets" || nykaaTab === "ai-resolved" || nykaaTab === "analytics";

  return (
    <div className="app-backdrop min-h-screen">
      <MegaTabs tabs={MEGA_TABS} value={megaTab} onChange={setMegaTab} />

      {megaTab === "tickets" && (
        <>
          <Header
            tabs={TABS}
            tab={tab}
            onTab={setTab}
            theme={theme}
            onToggleTheme={toggle}
            health={health}
            userLabel="Admin"
            onLogout={logout}
          />
          <main className={`mx-auto px-4 py-8 ${tab === "all" || tab === "ai-resolved" ? "max-w-[1600px]" : "max-w-6xl"}`}>
            {tab === "queue" && <NewTicketsQueuePage />}
            {tab === "all" && <AllTicketsPage />}
            {tab === "ai-resolved" && <AiResolvedPage />}
            {tab === "teams" && <TeamsOverviewPage />}
            {tab === "team-members" && <TeamMembersPage />}
            {tab === "race" && <RaceTab />}
            {tab === "demo" && <DemoTab />}
            {tab === "analytics" && <AnalyticsTab />}
          </main>
        </>
      )}

      {megaTab === "nykaa-pulse" && (
        <>
          <Header
            tabs={NYKAA_TABS}
            tab={nykaaTab}
            onTab={setNykaaTab}
            theme={theme}
            onToggleTheme={toggle}
            userLabel="Admin"
            onLogout={logout}
          />
          <main className={`mx-auto px-4 py-8 ${nykaaWide ? "max-w-[1600px]" : "max-w-6xl"}`}>
            <div>
              {nykaaTab === "tickets" && <NykaaAdminTicketsPage />}
              {nykaaTab === "ai-resolved" && <NykaaAiResolvedPage />}
              {nykaaTab === "teams" && <NykaaTeamsPage />}
              {nykaaTab === "team-members" && <NykaaTeamMembersPage />}
              {nykaaTab === "analytics" && <NykaaAnalyticsTab />}
            </div>
          </main>
        </>
      )}
    </div>
  );
}
