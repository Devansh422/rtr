import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import {
  getMyProfile,
  memberLogin,
  setMemberToken,
  clearMemberToken,
  getMemberToken,
} from "@/lib/memberApi";

const Ctx = createContext(null);
export const useMemberAuth = () => useContext(Ctx);

export const MemberAuthProvider = ({ children }) => {
  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | in | out

  const refresh = async () => {
    try {
      const p = await getMyProfile();
      setProfile(p);
      setStatus("in");
      return p;
    } catch {
      clearMemberToken();
      setProfile(null);
      setStatus("out");
      return null;
    }
  };

  useEffect(() => {
    if (!getMemberToken()) {
      setStatus("out");
      return;
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email, code) => {
    const res = await memberLogin(email, code);
    setMemberToken(res.access_token);
    await refresh();
    return res;
  };

  const logout = () => {
    clearMemberToken();
    setProfile(null);
    setStatus("out");
  };

  return (
    <Ctx.Provider value={{ profile, status, login, logout, refresh }}>{children}</Ctx.Provider>
  );
};

export const RequireMember = ({ children }) => {
  const { status } = useMemberAuth();
  const location = useLocation();
  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-secondary" />
      </div>
    );
  }
  if (status === "out") return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
};
