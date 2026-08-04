import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { RequireRole } from "./auth/RequireRole";
import { WelcomePage } from "./pages/WelcomePage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { UserDashboard } from "./pages/user/UserDashboard";
import { TeamDashboard } from "./pages/team/TeamDashboard";
import { AdminDashboard } from "./pages/admin/AdminDashboard";
import { PmDashboard } from "./pages/pm/PmDashboard";

function HomeRedirect() {
  const { auth } = useAuth();
  if (!auth) return <Navigate to="/welcome" replace />;
  return <Navigate to={`/${auth.role}`} replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/welcome" element={<WelcomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/user"
        element={
          <RequireRole role="user">
            <UserDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/team"
        element={
          <RequireRole role="team">
            <TeamDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireRole role="admin">
            <AdminDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/pm"
        element={
          <RequireRole role="pm">
            <PmDashboard />
          </RequireRole>
        }
      />
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
