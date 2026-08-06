import { useState } from "react";
import { PlusCircle, Sparkles, Star, Ticket } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { usePendingSurveys } from "../../hooks/usePendingSurveys";
import { Header } from "../../components/Header";
import { MegaTabs } from "../../components/MegaTabs";
import { Toast } from "../../components/primitives";
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
  const { auth, logout } = useAuth();
  const { pending, newSurvey, refresh, markAllSeen } = usePendingSurveys();
  const [menuOpen, setMenuOpen] = useState(false);

  function openSurveysFromToast() {
    setMenuOpen(true);
    markAllSeen();
  }

  return (
    <div className="app-backdrop min-h-screen">
      <MegaTabs tabs={MEGA_TABS} value={megaTab} onChange={setMegaTab} />

      {megaTab === "mission" && (
        <>
          <Header
            tabs={TABS}
            tab={tab}
            onTab={setTab}
            userName={auth.name}
            roleLabel="Customer"
            onLogout={logout}
            pendingSurveys={pending}
            onSurveysViewed={markAllSeen}
            onSurveyAnswered={refresh}
            menuOpen={menuOpen}
            onMenuOpenChange={setMenuOpen}
          />
          <main className="container-app px-4 py-8">
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
            userName={auth.name}
            roleLabel="Customer"
            onLogout={logout}
            pendingSurveys={pending}
            onSurveysViewed={markAllSeen}
            onSurveyAnswered={refresh}
            menuOpen={menuOpen}
            onMenuOpenChange={setMenuOpen}
          />
          <main className="container-app px-4 py-8">
            <NykaaCatalogPage />
          </main>
        </>
      )}

      {newSurvey && !menuOpen && (
        <Toast message={`New survey received: "${newSurvey.title}" — tap to answer`} onClick={openSurveysFromToast} />
      )}
    </div>
  );
}
