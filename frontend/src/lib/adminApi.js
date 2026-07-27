import axios from "axios";

// Empty-string fallback, so an unset env var yields a same-origin relative base
// rather than the literal string "undefined/api". See lib/api.js for detail.
const BACKEND = process.env.REACT_APP_BACKEND_URL || "";
const API = `${BACKEND}/api`;
const TOKEN_KEY = "rtr_admin_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const admin = axios.create({ baseURL: API });
admin.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const adminLogin = (email, password) =>
  axios.post(`${API}/auth/login`, { email, password }).then((r) => r.data);
export const adminMe = () => admin.get(`/auth/me`).then((r) => r.data);

export const listContent = (type) => admin.get(`/admin/content/${type}`).then((r) => r.data);
export const createContent = (type, data) =>
  admin.post(`/admin/content/${type}`, data).then((r) => r.data);
export const updateContent = (type, id, data) =>
  admin.put(`/admin/content/${type}/${id}`, data).then((r) => r.data);
export const deleteContent = (type, id) =>
  admin.delete(`/admin/content/${type}/${id}`).then((r) => r.data);

export const uploadFile = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return admin
    .post(`/admin/uploads`, fd, { headers: { "Content-Type": "multipart/form-data" } })
    .then((r) => ({ ...r.data, absoluteUrl: `${BACKEND}${r.data.url}` }));
};

export const listSubmissions = (kind) =>
  admin.get(`/admin/submissions/${kind}`).then((r) => r.data);

export const listAdminUsers = () => admin.get(`/admin/users`).then((r) => r.data);
export const createAdminUser = (data) => admin.post(`/admin/users`, data).then((r) => r.data);
export const updateAdminUser = (id, data) => admin.put(`/admin/users/${id}`, data).then((r) => r.data);
export const deleteAdminUser = (id) => admin.delete(`/admin/users/${id}`).then((r) => r.data);

export const getPageviewAnalytics = (days = 30) =>
  admin.get(`/admin/analytics/pageviews`, { params: { days } }).then((r) => r.data);

export { API, BACKEND };
