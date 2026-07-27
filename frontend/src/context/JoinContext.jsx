import { createContext, useContext } from "react";
import { useNavigate } from "react-router-dom";

const JoinContext = createContext(null);

export const useJoin = () => {
  const ctx = useContext(JoinContext);
  if (!ctx) throw new Error("useJoin must be used within JoinProvider");
  return ctx;
};

export const JoinProvider = ({ children }) => {
  const navigate = useNavigate();
  const openJoin = () => navigate("/join");
  return <JoinContext.Provider value={{ openJoin }}>{children}</JoinContext.Provider>;
};
