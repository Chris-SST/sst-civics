import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { RequireRole } from "./auth";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Signup from "./pages/Signup";
import VerifyEmail from "./pages/VerifyEmail";
import LinkSignIn from "./pages/LinkSignIn";
import Account from "./pages/Account";
import AccountDeleted from "./pages/AccountDeleted";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import TwoFactor from "./pages/TwoFactor";
import BillingReturn from "./pages/BillingReturn";
import LearnerHome from "./pages/LearnerHome";
const LearnerChat = lazy(() => import("./pages/LearnerChat"));
const Learn = lazy(() => import("./pages/Learn"));
const Practise = lazy(() => import("./pages/Practise"));
const Mock = lazy(() => import("./pages/Mock"));
const Glossary = lazy(() => import("./pages/Glossary"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));
import NotFound from "./pages/NotFound";

const LEARNER = ["learner"];

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<p className="muted">…</p>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/login" element={<Login />} />
        <Route path="/auth/link" element={<LinkSignIn />} />
        <Route
          path="/account"
          element={
            <RequireRole roles={LEARNER}>
              <Account />
            </RequireRole>
          }
        />
        <Route path="/account/deleted" element={<AccountDeleted />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/2fa" element={<TwoFactor mode="verify" />} />
        <Route path="/2fa/setup" element={<TwoFactor mode="setup" />} />
        <Route
          path="/billing/return"
          element={
            <RequireRole roles={LEARNER}>
              <BillingReturn />
            </RequireRole>
          }
        />
        <Route
          path="/learner"
          element={
            <RequireRole roles={LEARNER}>
              <LearnerHome />
            </RequireRole>
          }
        />
        <Route
          path="/learner/chat/:id"
          element={
            <RequireRole roles={LEARNER}>
              <LearnerChat />
            </RequireRole>
          }
        />
        <Route
          path="/learn"
          element={
            <RequireRole roles={LEARNER}>
              <Learn />
            </RequireRole>
          }
        />
        <Route
          path="/practise"
          element={
            <RequireRole roles={LEARNER}>
              <Practise />
            </RequireRole>
          }
        />
        <Route
          path="/glossary"
          element={
            <RequireRole roles={LEARNER}>
              <Glossary />
            </RequireRole>
          }
        />
        <Route
          path="/mock"
          element={
            <RequireRole roles={LEARNER}>
              <Mock />
            </RequireRole>
          }
        />
        <Route
          path="/mock/:id"
          element={
            <RequireRole roles={LEARNER}>
              <Mock />
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
      </Suspense>
    </Layout>
  );
}
