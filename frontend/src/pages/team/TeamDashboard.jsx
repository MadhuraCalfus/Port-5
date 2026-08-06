import { useEffect, useState } from "react";
import { Table2 } from "lucide-react";
import { api } from "../../api";
import { useAuth } from "../../auth/AuthContext";
import { Header } from "../../components/Header";
import { MegaTabs } from "../../components/MegaTabs";
import { TeamTicketsPage } from "./TeamTicketsPage";
import { NykaaTeamOrderTicketsPage } from "./nykaa/NykaaTeamOrderTicketsPage";

const NYKAA_TABS = [{ id: "tickets", label: "Tickets", icon: Table2 }];

export function TeamDashboard() {
  const [megaTab, setMegaTab] = useState("tickets");
  const [nykaaTab, setNykaaTab] = useState("tickets");
  // Rolled-up unread-reply count across this team's Nykaa Pulse tickets —
  // shown as a badge on the mega-tab pill itself, visible before even
  // opening the Tickets sub-tab. Fetched once on load, same as everything
  // else in this app (nothing pushes in real time anywhere today).
  const [nykaaUnread, setNykaaUnread] = useState(0);
  const { auth, logout } = useAuth();

  useEffect(() => {
    api
      .nykaaTeamOrderTickets()
      .then((r) => setNykaaUnread(r.tickets.reduce((sum, t) => sum + (t.unread_comments || 0), 0)))
      .catch(() => {});
  }, []);

  const MEGA_TABS = [
    { id: "tickets", label: "TicketTrident" },
    { id: "nykaa-pulse", label: "Nykaa Pulse", badge: nykaaUnread },
  ];

  return (
    <div className="app-backdrop min-h-screen">
      <MegaTabs tabs={MEGA_TABS} value={megaTab} onChange={setMegaTab} />

      {megaTab === "tickets" && (
        <>
          <Header userName={auth.name} roleLabel={`${auth.team} team`} onLogout={logout} />
          <main className="container-app px-4 py-8">
            <TeamTicketsPage />
          </main>
        </>
      )}

      {megaTab === "nykaa-pulse" && (
        <>
          <Header
            tabs={NYKAA_TABS}
            tab={nykaaTab}
            onTab={setNykaaTab}
            userName={auth.name}
            roleLabel={`${auth.team} team`}
            onLogout={logout}
          />
          <main className="container-app px-4 py-8">
            <div>
              {nykaaTab === "tickets" && <NykaaTeamOrderTicketsPage />}
            </div>
          </main>
        </>
      )}
    </div>
  );
}
