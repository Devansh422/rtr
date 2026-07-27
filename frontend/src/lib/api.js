import axios from "axios";

/*
 * API base URL.
 *
 * On Vercel the API is served from /api on the same origin as the site, so no
 * host is needed and a relative base is correct. REACT_APP_BACKEND_URL is only
 * for pointing at a backend on a different origin (local dev against a remote
 * API, or a separately-hosted backend).
 *
 * Note the fallback is an empty string, not undefined -- template-interpolating
 * an unset env var previously produced the literal base URL "undefined/api",
 * which made every request 404 in production.
 */
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

export const getCampaigns = () => client.get("/content/campaigns").then((r) => r.data);
export const getBlogs = () => client.get("/content/blogs").then((r) => r.data);
export const getFaq = () => client.get("/content/faq").then((r) => r.data);
export const getNews = () => client.get("/content/news").then((r) => r.data);
export const getTestimonials = () => client.get("/content/testimonials").then((r) => r.data);
export const getResources = () => client.get("/content/resources").then((r) => r.data);
export const getLeaders = () => client.get("/content/leaders").then((r) => r.data);
export const getJurisdictions = () => client.get("/content/jurisdictions").then((r) => r.data);
export const getMyths = () => client.get("/content/myths").then((r) => r.data);
export const getStats = () => client.get("/stats").then((r) => r.data);

/** Single blog post by slug id. Backed by GET /api/content/blogs/{id}. */
export const getBlog = (id) => client.get(`/content/blogs/${id}`).then((r) => r.data);

/**
 * Single campaign by slug id.
 *
 * There is no per-campaign endpoint, so this filters the list client-side. The
 * collection is small (single digits) and already cached by the browser, so the
 * extra payload is cheaper than adding a round trip.
 */
export const getCampaign = (id) =>
  getCampaigns().then((list) => list.find((c) => c.id === id) || null);

export const submitVolunteer = (data) => client.post("/volunteers", data).then((r) => r.data);
export const submitContact = (data) => client.post("/contact", data).then((r) => r.data);
export const subscribeNewsletter = (email) =>
  client.post("/newsletter", { email }).then((r) => r.data);
export const joinMovement = (data) => client.post("/supporters", data).then((r) => r.data);

/**
 * Fire-and-forget page-visit beacon. Never throws: a blocked/failed analytics
 * request must not surface anywhere or affect navigation, so failures are
 * swallowed here rather than left for each call site to remember to catch.
 */
export const trackPageview = (path, referrerPath, sessionId) =>
  client
    .post("/track/pageview", { path, referrer_path: referrerPath, session_id: sessionId })
    .catch(() => {});

export default client;
