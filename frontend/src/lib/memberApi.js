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

/*
 * Member-authenticated calls for the platform modules.
 *
 * All of these go through the `member` instance above, so they carry the member JWT
 * and never the admin one -- the backend issues two distinct token types precisely
 * so one cannot be replayed against the other's endpoints.
 */

// ---- Community identity ----
export const updateMyProfile = (displayName, stateCode) =>
  member
    .put(`/me/profile`, null, { params: { display_name: displayName, state_code: stateCode } })
    .then((r) => r.data);

// ---- Petitions ----
export const createPetition = (payload) => member.post(`/petitions`, payload).then((r) => r.data);
export const signPetition = (slug, payload) =>
  member.post(`/petitions/${slug}/sign`, payload).then((r) => r.data);
export const withdrawSignature = (slug) =>
  member.delete(`/petitions/${slug}/sign`).then((r) => r.data);
export const listMyPetitions = () => member.get(`/me/petitions`).then((r) => r.data);

// ---- Citizen reports ----
export const fileReport = (payload) => member.post(`/reports`, payload).then((r) => r.data);
export const confirmReport = (slug, note) =>
  member.post(`/reports/${slug}/confirm`, null, { params: { note } }).then((r) => r.data);
export const listMyReports = () => member.get(`/me/reports`).then((r) => r.data);

// ---- Forum ----
export const createThread = (payload) => member.post(`/forum/threads`, payload).then((r) => r.data);
export const replyToThread = (slug, payload) =>
  member.post(`/forum/threads/${slug}/replies`, payload).then((r) => r.data);
export const upvote = (targetType, targetId) =>
  member.post(`/forum/${targetType}/${targetId}/upvote`).then((r) => r.data);
export const getMyForumActivity = () => member.get(`/me/forum`).then((r) => r.data);

// ---- Volunteer portal ----
export const getMyVolunteerDashboard = () => member.get(`/me/volunteer`).then((r) => r.data);
export const saveVolunteerProfile = (payload) =>
  member.put(`/me/volunteer/profile`, payload).then((r) => r.data);
export const claimTask = (slug) => member.post(`/volunteer/tasks/${slug}/claim`).then((r) => r.data);
export const submitTaskWork = (assignmentId, payload) =>
  member.post(`/me/volunteer/assignments/${assignmentId}/submit`, payload).then((r) => r.data);
export const abandonTask = (assignmentId) =>
  member.delete(`/me/volunteer/assignments/${assignmentId}`).then((r) => r.data);
export const requestVolunteerCertificate = () =>
  member.post(`/me/volunteer/certificate`).then((r) => r.data);

// ---- Events ----
export const registerForEvent = (slug) =>
  member.post(`/events/${slug}/register`).then((r) => r.data);
export const cancelEventRegistration = (slug) =>
  member.delete(`/events/${slug}/register`).then((r) => r.data);
export const listMyEvents = () => member.get(`/me/events`).then((r) => r.data);

// ---- Academy ----
export const enrollInCourse = (slug) =>
  member.post(`/academy/courses/${slug}/enroll`).then((r) => r.data);
export const completeLesson = (lessonId) =>
  member.post(`/academy/lessons/${lessonId}/complete`).then((r) => r.data);
export const getQuiz = (slug) => member.get(`/academy/courses/${slug}/quiz`).then((r) => r.data);
export const submitQuiz = (slug, answers) =>
  member.post(`/academy/courses/${slug}/quiz`, { answers }).then((r) => r.data);
export const getMyAcademy = () => member.get(`/me/academy`).then((r) => r.data);

// ---- DPDP ----
export const getMyConsent = () => member.get(`/me/consent`).then((r) => r.data);
export const withdrawConsent = (purpose) =>
  member.post(`/me/consent/withdraw`, { purpose }).then((r) => r.data);
export const eraseMyData = () => member.delete(`/me/data`).then((r) => r.data);
