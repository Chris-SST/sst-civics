import { Route, Routes } from "react-router-dom";
import { RequireRole } from "./auth";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Signup from "./pages/Signup";
import VerifyEmail from "./pages/VerifyEmail";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import AcceptInvite from "./pages/AcceptInvite";
import TwoFactor from "./pages/TwoFactor";
import ParentDashboard from "./pages/ParentDashboard";
import BillingReturn from "./pages/BillingReturn";
import StudentHome from "./pages/StudentHome";
import TutorDashboard from "./pages/TutorDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/accept-invite" element={<AcceptInvite />} />
        <Route path="/2fa" element={<TwoFactor mode="verify" />} />
        <Route path="/2fa/setup" element={<TwoFactor mode="setup" />} />
        <Route
          path="/parent/*"
          element={
            <RequireRole roles={["parent", "adult"]}>
              <ParentDashboard />
            </RequireRole>
          }
        />
        <Route
          path="/billing/return"
          element={
            <RequireRole roles={["parent", "adult"]}>
              <BillingReturn />
            </RequireRole>
          }
        />
        <Route
          path="/student"
          element={
            <RequireRole roles={["student", "adult"]}>
              <StudentHome />
            </RequireRole>
          }
        />
        <Route
          path="/tutor"
          element={
            <RequireRole roles={["tutor", "admin"]}>
              <TutorDashboard />
            </RequireRole>
          }
        />
        <Route
          path="/admin/*"
          element={
            <RequireRole roles={["admin"]}>
              <AdminDashboard />
            </RequireRole>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
