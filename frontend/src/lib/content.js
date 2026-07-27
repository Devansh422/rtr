/*
 * Parsers for the plain-text conventions used by the admin content fields.
 *
 * The admin panel edits content as text and textarea inputs, so structured data
 * (milestones, participation steps) is stored line-based rather than as JSON.
 * That keeps the editing experience approachable for a non-technical content
 * team; these helpers turn those conventions back into structures for rendering.
 * Every parser tolerates missing, empty, or malformed input by returning an
 * empty result rather than throwing.
 */

/** Splits a textarea body into paragraphs on blank lines. */
export function toParagraphs(text) {
  if (!text || typeof text !== "string") return [];
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}

/** Splits a textarea body into a list, one item per non-empty line. */
export function toLines(text) {
  if (!text || typeof text !== "string") return [];
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

const MILESTONE_STATUSES = new Set(["DONE", "ACTIVE", "NEXT"]);

/**
 * Parses milestone lines of the form `STATUS | DATE | TITLE`.
 *
 * Falls back gracefully: a line with fewer than three parts still yields a
 * milestone with whatever was provided, so a half-filled field renders instead
 * of disappearing. Unrecognised statuses default to NEXT.
 */
export function parseMilestones(text) {
  return toLines(text).map((line) => {
    const parts = line.split("|").map((p) => p.trim());

    if (parts.length >= 3) {
      const [status, date, ...rest] = parts;
      const upper = status.toUpperCase();
      return {
        status: MILESTONE_STATUSES.has(upper) ? upper : "NEXT",
        date,
        title: rest.join(" | "),
      };
    }

    // Not in the documented format -- treat the whole line as the title.
    return { status: "NEXT", date: "", title: line };
  });
}

/**
 * Coerces the supporters/goal fields into a progress percentage.
 *
 * These arrive as numbers from the seed data but as strings when typed into the
 * admin panel, hence the Number() coercion. Returns null when a meaningful
 * percentage cannot be computed, so callers can hide the progress UI entirely
 * rather than render a bar at zero.
 */
export function progressPercent(supporters, goal) {
  const current = Number(supporters);
  const target = Number(goal);
  if (!Number.isFinite(current) || !Number.isFinite(target) || target <= 0) return null;
  return Math.max(0, Math.min(100, (current / target) * 100));
}

/** Formats a count with thousands separators, tolerating string input. */
export function formatCount(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("en-IN") : "0";
}

/** Formats an ISO date as e.g. "28 Nov 2025". Returns "" for unparseable input. */
export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return typeof iso === "string" ? iso : "";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Formats a `YYYY-MM` milestone stamp as e.g. "Mar 2025", passing through anything else. */
export function formatMonth(stamp) {
  if (!stamp) return "";
  const match = /^(\d{4})-(\d{2})$/.exec(stamp.trim());
  if (!match) return stamp;
  const d = new Date(Number(match[1]), Number(match[2]) - 1, 1);
  return d.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}
