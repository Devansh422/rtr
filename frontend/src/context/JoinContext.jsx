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

  /*
   * `campaignId`, when passed, is carried to /join as a query param and
   * ultimately submitted with the supporter record, so real signups can be
   * attributed to the specific campaign whose CTA the visitor clicked. Generic
   * "Join Movement" entry points (navbar, footer, hero) call this with no
   * argument, leaving the signup unattributed to any single campaign.
   */
  const openJoin = (campaignId) => {
    navigate(campaignId ? `/join?campaign=${encodeURIComponent(campaignId)}` : "/join");
  };

  return <JoinContext.Provider value={{ openJoin }}>{children}</JoinContext.Provider>;
};
