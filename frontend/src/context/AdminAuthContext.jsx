import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { adminMe, adminLogin, setToken, clearToken, getToken } from "@/lib/adminApi";

const Ctx = createContext(null);
export const useAdminAuth = () => useContext(Ctx);

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
    setUser(res.user);
    setStatus("in");
    return res;
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setStatus("out");
  };

  return <Ctx.Provider value={{ user, status, login, logout }}>{children}</Ctx.Provider>;
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
