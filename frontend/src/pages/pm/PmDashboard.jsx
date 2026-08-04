import { useState } from "react";
import { BarChart3, ClipboardList, FileText, PieChart, Table2 } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { useTheme } from "../../hooks/useTheme";
import { Header } from "../../components/Header";
import { MegaTabs } from "../../components/MegaTabs";
import { ImportFeedbackPage } from "./ImportFeedbackPage";
import { AnalyticsPage } from "./AnalyticsPage";
import { ReportsActionsPage } from "./ReportsActionsPage";
import { CreateSurveyPage } from "./CreateSurveyPage";
import { SurveyAnalyticsPage } from "./SurveyAnalyticsPage";
import { NykaaPulseOverviewPage } from "./nykaa/NykaaPulseOverviewPage";
import { NykaaAllFeedbackPage } from "./nykaa/NykaaAllFeedbackPage";
import { NykaaAnalyticsPage } from "./nykaa/NykaaAnalyticsPage";
import { NykaaPulseWeeklyReportPage } from "./nykaa/NykaaPulseWeeklyReportPage";
import { NykaaAppFeedbackAnalyticsPage } from "./nykaa/NykaaAppFeedbackAnalyticsPage";
import { NykaaDeliveryFeedbackAnalyticsPage } from "./nykaa/NykaaDeliveryFeedbackAnalyticsPage";

// All Feedback is the raw, sortable/filterable/searchable table everything
// else is aggregated from. Analytics is the general pulse (overall
// sentiment/volume/rating trends, where feedback comes from). Reports is
// the weekly/yearly AI narrative + recommended actions. Create Survey lets
// the PM author their own ad-hoc multi-question surveys and send them to
// every customer; Survey Analytics shows the results — separate from the
// fixed star-rating survey customers already fill out (that one still
// feeds All Feedback directly).
const TABS = [
  { id: "all-feedback", label: "All Feedback", icon: Table2 },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "create-survey", label: "Create Survey", icon: ClipboardList },
  { id: "survey-analytics", label: "Survey Analytics", icon: PieChart },
];

const MEGA_TABS = [
  { id: "mission", label: "TicketTrident" },
  { id: "nykaa-pulse", label: "Nykaa Pulse" },
];

// Overview is the order/GMV/rating headline plus the order -> review ->
// photo -> published drop-off funnel; Analytics merges the old separate
// Brands/Categories/Products sub-tabs into one filterable view (see
// NykaaAnalyticsPage.jsx) — all three are ranked breakdowns off the same
// underlying aggregation (see nykaa_insights.py), just relabeled/regrouped;
// Reports is the brand-scoped weekly/monthly/yearly narrative, mirroring
// the Mission side's own Reports tab. Create Survey / Survey Analytics
// reuse the exact same components as the Mission side — surveys are sent
// to every customer account regardless of which mega-tab they browse in,
// so there's nothing Nykaa-specific to build here, just another place to
// reach the same feature.
const NYKAA_TABS = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "all-feedback", label: "All Feedback", icon: Table2 },
  { id: "analytics", label: "Analytics", icon: PieChart },
  { id: "app-feedback", label: "App Feedback", icon: BarChart3 },
  { id: "delivery-feedback", label: "Delivery Feedback", icon: BarChart3 },
  { id: "weekly-report", label: "Reports", icon: FileText },
  { id: "create-survey", label: "Create Survey", icon: ClipboardList },
  { id: "survey-analytics", label: "Survey Analytics", icon: PieChart },
];

export function PmDashboard() {
  const [megaTab, setMegaTab] = useState("mission");
  const [tab, setTab] = useState("all-feedback");
  const [nykaaTab, setNykaaTab] = useState("overview");
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
            userLabel={`${auth.name} · product manager`}
            onLogout={logout}
          />
          <main className="mx-auto max-w-6xl px-4 py-8">
            {tab === "all-feedback" && <ImportFeedbackPage />}
            {tab === "analytics" && <AnalyticsPage />}
            {tab === "reports" && <ReportsActionsPage />}
            {tab === "create-survey" && <CreateSurveyPage />}
            {tab === "survey-analytics" && <SurveyAnalyticsPage />}
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
            userLabel={`${auth.name} · product manager`}
            onLogout={logout}
          />
          <main className="mx-auto max-w-6xl px-4 py-8">
            <div>
              {nykaaTab === "overview" && <NykaaPulseOverviewPage />}
              {nykaaTab === "all-feedback" && <NykaaAllFeedbackPage />}
              {nykaaTab === "analytics" && <NykaaAnalyticsPage />}
              {nykaaTab === "app-feedback" && <NykaaAppFeedbackAnalyticsPage />}
              {nykaaTab === "delivery-feedback" && <NykaaDeliveryFeedbackAnalyticsPage />}
              {nykaaTab === "weekly-report" && <NykaaPulseWeeklyReportPage />}
              {nykaaTab === "create-survey" && <CreateSurveyPage />}
              {nykaaTab === "survey-analytics" && <SurveyAnalyticsPage />}
            </div>
          </main>
        </>
      )}
    </div>
  );
}
