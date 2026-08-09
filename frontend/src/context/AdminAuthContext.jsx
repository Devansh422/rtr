import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { adminMe, adminLogin, setToken, clearToken, getToken } from "@/lib/adminApi";

const Ctx = createContext(null);
export const useAdminAuth = () => useContext(Ctx);

/*
 * permissions: null/undefined means "legacy full access" -- an admin account
 * that predates RBAC, which the backend grants everything rather than lock out
 * of a live deployment (see resolve_legacy_principal in backend/core/rbac.py).
 * Any other account carries an explicit array, even an empty one; a Super Admin
 * simply carries every key.
 */
export function hasPermission(user, key) {
  if (!user) return false;
  const perms = user.permissions;
  if (perms == null) return true;
  return perms.includes(key);
}

export const AdminAuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | in | out

  useEffect(() => {
    (async () => {
      if (!getToken()) {
        setStatus("out");
        return;
      }
      try {
        const u = await adminMe();
        setUser(u);
        setStatus("in");
      } catch {
        clearToken();
        setStatus("out");
      }
    })();
  }, []);

  const login = async (email, password) => {
    const res = await adminLogin(email, password);
    setToken(res.access_token);
    // The login response's `user` is a partial shape (no `permissions`) --
    // fetch the full profile immediately so permission checks are accurate
    // from the first render rather than only after a later page refresh.
    const full = await adminMe();
    setUser(full);
    setStatus("in");
    return res;
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setStatus("out");
  };

  return (
    <Ctx.Provider value={{ user, status, login, logout, hasPermission: (key) => hasPermission(user, key) }}>
      {children}
    </Ctx.Provider>
  );
};

export const RequireAdmin = ({ children }) => {
  const { status } = useAdminAuth();
  const location = useLocation();
  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-secondary" />
      </div>
    );
  }
  if (status === "out") return <Navigate to="/admin/login" replace state={{ from: location }} />;
  return children;
};

/** Gates a section of the dashboard behind a specific permission key. */
export const RequirePermission = ({ permission, fallback = null, children }) => {
  const { hasPermission: check } = useAdminAuth();
  return check(permission) ? children : fallback;
};
