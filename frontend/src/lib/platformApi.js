import client from "@/lib/api";

/*
 * API client for the platform modules (constitution, representatives, petitions,
 * forum, reports, tools, academy, research, events, assistant, legal).
 *
 * Kept separate from lib/api.js, which covers the original campaign site's CMS and
 * form endpoints. Same axios instance and same relative /api base -- splitting the
 * file rather than the client, because lib/api.js was already the longest import in
 * every page and these are a different surface.
 *
 * Two conventions worth knowing:
 *
 * 1. Reads never throw for a caller that just wants to render something. Functions
 *    ending in `OrEmpty` swallow the error and return a neutral value, because a
 *    failed sidebar request should not blank a page. Everything else propagates, so
 *    a form submission's error can be shown to the person who submitted it.
 * 2. Member-authenticated calls go through memberApi's interceptor, so nothing here
 *    handles tokens.
 */

const unwrap = (promise) => promise.then((r) => r.data);
const orEmpty = (promise, fallback) => promise.then((r) => r.data).catch(() => fallback);

// --------------------------------------------------------------------------
// Constitution Library
// --------------------------------------------------------------------------
export const getConstitutionParts = () => orEmpty(client.get("/constitution/parts"), []);

export const getArticles = (params = {}) =>
  orEmpty(client.get("/constitution/articles", { params }), { total: 0, items: [] });

export const getArticle = (number, locale = "en") =>
  unwrap(client.get(`/constitution/articles/${number}`, { params: { locale } }));

export const getArticleHistory = (number) =>
  orEmpty(client.get(`/constitution/articles/${number}/history`), []);

// --------------------------------------------------------------------------
// Representatives, claims and promises
// --------------------------------------------------------------------------
export const getRepresentatives = (params = {}) =>
  orEmpty(client.get("/representatives", { params }), { total: 0, items: [] });

export const getRepresentative = (slug) => unwrap(client.get(`/representatives/${slug}`));

export const getRepresentativeHistory = (slug) =>
  orEmpty(client.get(`/representatives/${slug}/history`), []);

export const getMyRepresentatives = (state, constituency) =>
  unwrap(client.get("/my-representatives", { params: { state, constituency } }));

export const getClaimFields = () =>
  orEmpty(client.get("/claim-fields"), { fields: [], disclaimer: "" });

export const getParties = () => orEmpty(client.get("/parties"), []);
export const getHouses = () => orEmpty(client.get("/houses"), []);
export const getConstituencies = (params = {}) =>
  orEmpty(client.get("/constituencies", { params }), []);

export const getPromises = (params = {}) =>
  orEmpty(client.get("/promises", { params }), { total: 0, items: [], tally: null, statuses: [] });

export const getPromise = (slug) => unwrap(client.get(`/promises/${slug}`));

// --------------------------------------------------------------------------
// States and the campaign pipeline
// --------------------------------------------------------------------------
export const getStates = () => orEmpty(client.get("/states"), []);
export const getState = (slug) => unwrap(client.get(`/states/${slug}`));
export const getStateHistory = (slug) => orEmpty(client.get(`/states/${slug}/history`), []);
export const getCampaignStages = () => orEmpty(client.get("/campaign-stages"), []);

// --------------------------------------------------------------------------
// Petitions
// --------------------------------------------------------------------------
export const getPetitions = (params = {}) =>
  orEmpty(client.get("/petitions", { params }), { total: 0, items: [] });

export const getPetition = (slug) => unwrap(client.get(`/petitions/${slug}`));
export const getPetitionSignatures = (slug) =>
  orEmpty(client.get(`/petitions/${slug}/signatures`), { items: [], totalSignatures: 0 });

/**
 * The common cause: the one national petition, with its state-wise breakdown.
 *
 * Fetched from `/petitions/national` rather than by a slug written here, so which
 * petition that is stays decided in one place on the backend.
 */
export const getNationalPetition = () => unwrap(client.get("/petitions/national"));

export const getPetitionByState = (slug) =>
  orEmpty(client.get(`/petitions/${slug}/by-state`), null);

/**
 * Sign and become a member in one request, for a visitor with no account.
 *
 * Propagates errors rather than swallowing them: a 409 (this address has already
 * signed) and a 429 (rate limited) both need to reach the person who pressed the
 * button. Returns a member token, which the caller stores so the browser is
 * signed in afterwards.
 */
export const signPetitionPublicly = (slug, payload) =>
  unwrap(client.post(`/petitions/${slug}/sign-public`, payload));

// --------------------------------------------------------------------------
// Citizen reports
// --------------------------------------------------------------------------
export const getReportServices = () => orEmpty(client.get("/reports/services"), []);
export const getReports = (params = {}) =>
  orEmpty(client.get("/reports", { params }), { total: 0, items: [] });
export const getReport = (slug) => unwrap(client.get(`/reports/${slug}`));
export const getScorecard = (params) => orEmpty(client.get("/reports/scorecard", { params }), null);

// --------------------------------------------------------------------------
// Forum
// --------------------------------------------------------------------------
export const getForumCategories = () => orEmpty(client.get("/forum/categories"), []);
export const getThreads = (params = {}) =>
  orEmpty(client.get("/forum/threads", { params }), { total: 0, items: [] });
export const getThread = (slug) => unwrap(client.get(`/forum/threads/${slug}`));

// --------------------------------------------------------------------------
// Volunteer portal and events
// --------------------------------------------------------------------------
export const getVolunteerSkills = () => orEmpty(client.get("/volunteer/skills"), []);
export const getVolunteerTasks = (params = {}) =>
  orEmpty(client.get("/volunteer/tasks", { params }), { total: 0, items: [] });
export const getVolunteerTask = (slug) => unwrap(client.get(`/volunteer/tasks/${slug}`));

export const getEvents = (params = {}) => orEmpty(client.get("/events", { params }), []);
export const getEvent = (slug) => unwrap(client.get(`/events/${slug}`));
export const getEventKinds = () => orEmpty(client.get("/events/kinds"), []);

// --------------------------------------------------------------------------
// Academy
// --------------------------------------------------------------------------
export const getCourses = (params = {}) => orEmpty(client.get("/academy/courses", { params }), []);
export const getCourse = (slug) => unwrap(client.get(`/academy/courses/${slug}`));
export const getLesson = (courseSlug, lessonSlug) =>
  unwrap(client.get(`/academy/courses/${courseSlug}/lessons/${lessonSlug}`));
export const getAcademyLevels = () => orEmpty(client.get("/academy/levels"), []);

// --------------------------------------------------------------------------
// Research Centre and Media Library
// --------------------------------------------------------------------------
export const getDocumentKinds = () =>
  orEmpty(client.get("/research/kinds"), { kinds: [], licences: [] });
export const getDocuments = (params = {}) =>
  orEmpty(client.get("/research/documents", { params }), { total: 0, items: [] });
export const getDocument = (slug) => unwrap(client.get(`/research/documents/${slug}`));
export const registerDownload = (slug) =>
  unwrap(client.post(`/research/documents/${slug}/download`));

// --------------------------------------------------------------------------
// Civic tools
// --------------------------------------------------------------------------
export const getTools = () => orEmpty(client.get("/tools"), { kinds: [], guides: [] });
export const getTemplate = (key) => unwrap(client.get(`/tools/templates/${key}`));
export const getRtiGuide = () => orEmpty(client.get("/tools/guides/rti"), null);
export const getPilGuide = () => orEmpty(client.get("/tools/guides/pil"), null);

export const generateDocument = (templateKey, values, stateCode) =>
  unwrap(client.post("/tools/generate", { template_key: templateKey, values, state_code: stateCode }));

/**
 * Download the generated DOCX.
 *
 * Posts and turns the response into a blob download rather than navigating, because
 * the generator is a POST (the inputs are the body, and putting an RTI application's
 * contents in a query string would put them in server logs and browser history).
 */
export const downloadDocx = async (templateKey, values, filename) => {
  const response = await client.post(
    "/tools/generate.docx",
    { template_key: templateKey, values },
    { responseType: "blob" }
  );
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename || `${templateKey}.docx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

/**
 * Open the print view in a new tab, from which the browser's own "Save as PDF"
 * produces a correctly shaped Devanagari PDF (see backend/core/documents.py).
 *
 * Uses a real form submission rather than fetch + document.write, so the new tab
 * gets a normal document with a working print dialog and its own URL.
 */
export const openPrintView = (templateKey, values) => {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/api/tools/generate.html";
  form.target = "_blank";
  form.enctype = "text/plain";

  // The endpoint expects JSON, and text/plain is the only enctype that lets a form
  // POST a raw body. A hidden input named with the whole JSON works because the
  // browser serialises `name=value` -- so the name carries the payload and the
  // value is empty.
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = JSON.stringify({ template_key: templateKey, values });
  input.value = "";
  form.appendChild(input);

  document.body.appendChild(form);
  form.submit();
  form.remove();
};

// --------------------------------------------------------------------------
// AI Constitution Assistant
// --------------------------------------------------------------------------
export const getAssistantStatus = () => orEmpty(client.get("/assistant/status"), null);
export const askAssistant = (question, locale = "en") =>
  unwrap(client.post("/assistant/ask", { question, locale }));
export const rateAnswer = (question, helpful) =>
  client.post("/assistant/feedback", null, { params: { question, helpful } }).catch(() => {});

// --------------------------------------------------------------------------
// Search
// --------------------------------------------------------------------------
export const searchSite = (q, params = {}) =>
  orEmpty(client.get("/search", { params: { q, ...params } }), { total: 0, items: [], groups: [] });
export const suggest = (q) => orEmpty(client.get("/search/suggest", { params: { q } }), []);
export const getSearchCoverage = () => orEmpty(client.get("/search/coverage"), { types: [], total: 0 });

// --------------------------------------------------------------------------
// Corrections (§7 trust layer)
// --------------------------------------------------------------------------
export const getCorrections = (entityType, entityId) =>
  orEmpty(client.get("/corrections", { params: { entityType, entityId } }), {
    total: 0,
    openCount: 0,
    acceptedCount: 0,
    items: [],
  });

export const submitCorrection = (payload) => unwrap(client.post("/corrections", payload));

// --------------------------------------------------------------------------
// Legal / DPDP
// --------------------------------------------------------------------------
export const getPrivacyPolicy = () => orEmpty(client.get("/legal/privacy"), null);
export const getContentPolicy = () => orEmpty(client.get("/legal/content-policy"), null);
export const getDisclaimer = () => orEmpty(client.get("/legal/disclaimer"), null);
export const getConsentNotices = () =>
  orEmpty(client.get("/legal/consent-notices"), { purposes: [], policyVersion: "" });
export const getLocales = () => orEmpty(client.get("/locales"), null);

/**
 * Record consent alongside a form submission.
 *
 * Never blocks the submission it accompanies: if the consent write fails, the
 * signup still happened and a lost audit row is a smaller problem than a member
 * who filled in a form and got an error.
 */
export const recordConsent = (email, purposes, source) =>
  client.post("/legal/consent", { email, purposes, source }).catch(() => {});

// --------------------------------------------------------------------------
// Certificates
// --------------------------------------------------------------------------
export const verifyCertificate = (code) => unwrap(client.get(`/certificates/${code}`));
