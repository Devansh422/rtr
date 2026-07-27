import axios from "axios";
import { BACKEND } from "@/lib/adminApi";

/*
 * Client for the supporter/volunteer dashboards. A separate axios instance
 * and token from the admin client (lib/adminApi.js) and the public client
 * (lib/api.js): the backend issues a distinct "member" JWT type specifically
 * so this token can never be replayed against an admin-only endpoint or vice
 * versa, and mixing the interceptors here would defeat that.
 */
const API = `${BACKEND}/api`;
const TOKEN_KEY = "rtr_member_token";

export const getMemberToken = () => localStorage.getItem(TOKEN_KEY);
export const setMemberToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearMemberToken = () => localStorage.removeItem(TOKEN_KEY);

const member = axios.create({ baseURL: API });
member.interceptors.request.use((cfg) => {
  const t = getMemberToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const memberLogin = (email, code) =>
  axios.post(`${API}/auth/member-login`, { email, code }).then((r) => r.data);

export const getMyProfile = () => member.get(`/me`).then((r) => r.data);

export const listMyOpportunities = () => member.get(`/me/opportunities`).then((r) => r.data);
export const completeOpportunity = (id) =>
  member.post(`/me/opportunities/${id}/complete`).then((r) => r.data);
export const uncompleteOpportunity = (id) =>
  member.delete(`/me/opportunities/${id}/complete`).then((r) => r.data);
