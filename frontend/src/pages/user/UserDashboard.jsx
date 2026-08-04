import { useState } from "react";
import { PlusCircle, Sparkles, Star, Ticket } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { useTheme } from "../../hooks/useTheme";
import { Header } from "../../components/Header";
import { MegaTabs } from "../../components/MegaTabs";
import { NewTicketPage } from "./NewTicketPage";
import { MyTicketsPage } from "./MyTicketsPage";
import { MyResolvedIssuesPage } from "./MyResolvedIssuesPage";
import { SurveyPage } from "./SurveyPage";
import { NykaaCatalogPage } from "./nykaa/NykaaCatalogPage";

const TABS = [
  { id: "new", label: "New Ticket", icon: PlusCircle },
  { id: "mine", label: "My Tickets", icon: Ticket },
  { id: "resolved", label: "Resolved by AI", icon: Sparkles },
  { id: "survey", label: "Feedback Survey", icon: Star },
];

const MEGA_TABS = [
  { id: "mission", label: "TicketTrident" },
  { id: "nykaa-pulse", label: "Nykaa Pulse" },
];

export function UserDashboard() {
  const [megaTab, setMegaTab] = useState("mission");
  const [tab, setTab] = useState("new");
  const [reloadKey, setReloadKey] = useState(0);
  const { theme, toggle } = useTheme();
  const { auth, logout } = useAuth();

  return (
    <div className="app-backdrop min-h-screen">
      <MegaTabs tabs={MEGA_TABS} value={megaTab} onChange={setMegaTab} />

      {megaTab === "mission" && (
        <>
          <Header
            tabs={TABS}
            tab={tab}
            onTab={setTab}
            theme={theme}
            onToggleTheme={toggle}
            userLabel={`${auth.name} · customer`}
            onLogout={logout}
          />
          <main className="mx-auto max-w-6xl px-4 py-8">
            {tab === "new" && (
              <NewTicketPage
                onSubmitted={() => {
                  setReloadKey((k) => k + 1);
                  setTab("mine");
                }}
              />
            )}
            {tab === "mine" && <MyTicketsPage reloadKey={reloadKey} />}
            {tab === "resolved" && <MyResolvedIssuesPage />}
            {tab === "survey" && <SurveyPage />}
          </main>
        </>
      )}

      {megaTab === "nykaa-pulse" && (
        <>
          <Header
            theme={theme}
            onToggleTheme={toggle}
            userLabel={`${auth.name} · customer`}
            onLogout={logout}
          />
          <main className="mx-auto max-w-[90rem] px-4 py-8">
            <NykaaCatalogPage />
          </main>
        </>
      )}
    </div>
  );
}
