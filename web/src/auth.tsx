import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ApiError, get, post, type LoginOut, type Me, type PublicConfig } from "./api";

interface AuthState {
  me: Me | null;
  config: PublicConfig | null;
  loading: boolean;
  refresh: () => Promise<Me | null>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  me: null,
  config: null,
  loading: true,
  refresh: async () => null,
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await get<Me>("/api/auth/me");
      setMe(data);
      return data;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await post("/api/auth/logout");
    } finally {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    get<PublicConfig>("/api/config").then(setConfig).catch(() => setConfig(null));
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ me, config, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

export function homeFor(role: string): string {
  switch (role) {
    case "learner":
      return "/learner";
    case "admin":
      return "/admin";
    default:
      return "/";
  }
}

/** Where to go after a password or email-link sign-in. `from` is an in-app path only. */
export function pathAfterSignIn(out: LoginOut, from?: string | null): string {
  if (out.status === "mfa_required") return "/2fa";
  if (out.status === "mfa_setup_required") return "/2fa/setup";
  if (from && from.startsWith("/") && !from.startsWith("//") && from !== "/login") return from;
  return homeFor(out.me?.user.role ?? "");
}

/** Route guard. Sends people to login, the 2FA step, or their own home. */
export function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="muted">…</p>;
  if (!me) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (me.session.mfa_pending) return <Navigate to="/2fa" replace />;
  if (me.session.mfa_setup_required) return <Navigate to="/2fa/setup" replace />;
  if (!roles.includes(me.user.role)) return <Navigate to={homeFor(me.user.role)} replace />;
  return <>{children}</>;
}
