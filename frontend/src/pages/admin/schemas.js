// Field schemas for each managed content type.
// type: text (default) | textarea | date | image
export const SCHEMAS = {
  blogs: {
    label: "Blogs",
    titleField: "title",
    subField: "category",
    fields: [
      { name: "title", label: "Title" },
      { name: "excerpt", label: "Excerpt", type: "textarea" },
      { name: "category", label: "Category" },
      { name: "author", label: "Author" },
      { name: "date", label: "Date", type: "date" },
      { name: "readTime", label: "Read time (e.g. 3 min)" },
      { name: "image", label: "Cover image", type: "image" },
      { name: "content", label: "Full content", type: "textarea" },
    ],
    // Grouped into tabs in the edit dialog -- flat, this was 8 fields in one
    // scroll, ending with the two longest (excerpt, content) easy to miss.
    sections: [
      { title: "Basics", fields: ["title", "category", "author", "date", "readTime", "image"] },
      { title: "Content", fields: ["excerpt", "content"] },
    ],
  },
  news: {
    label: "News / Updates",
    titleField: "title",
    subField: "source",
    fields: [
      { name: "title", label: "Title" },
      { name: "summary", label: "Summary", type: "textarea" },
      { name: "date", label: "Date", type: "date" },
      { name: "source", label: "Source" },
      { name: "image", label: "Image", type: "image" },
    ],
  },
  faq: {
    label: "FAQs",
    titleField: "question",
    subField: "category",
    fields: [
      { name: "question", label: "Question" },
      { name: "answer", label: "Answer", type: "textarea" },
      { name: "category", label: "Category" },
    ],
  },
  jurisdictions: {
    label: "Jurisdictions",
    titleField: "place",
    subField: "region",
    fields: [
      { name: "place", label: "Place" },
      { name: "region", label: "Region" },
      { name: "summary", label: "Summary", type: "textarea" },
    ],
  },
  myths: {
    label: "Myth vs Fact",
    titleField: "myth",
    subField: "",
    fields: [
      { name: "myth", label: "Myth", type: "textarea" },
      { name: "fact", label: "Fact", type: "textarea" },
    ],
  },
  resources: {
    label: "Resources / Downloads",
    titleField: "title",
    subField: "type",
    fields: [
      { name: "title", label: "Title" },
      { name: "type", label: "Type (Document/Toolkit/Research)" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "downloadLabel", label: "Button label" },
      { name: "file", label: "File (PDF/doc)", type: "image" },
    ],
  },
  campaigns: {
    label: "Campaigns",
    titleField: "title",
    subField: "status",
    fields: [
      { name: "title", label: "Title" },
      { name: "description", label: "Short description (card + hero)", type: "textarea" },
      { name: "status", label: "Status (ACTIVE/UPCOMING/VICTORY)" },
      { name: "cta", label: "CTA label" },
      { name: "location", label: "Location" },
      { name: "image", label: "Image", type: "image" },
      // supporters/goal drive the progress bar on the campaign detail page.
      // `supporters` is a BASELINE, not the final number the public site shows:
      // real /join signups made through this campaign's CTA are added on top of
      // it automatically (see with_live_supporter_counts in backend/server.py).
      // Raise this if you want to reflect offline/pre-launch support.
      {
        name: "supporters",
        label: "Starting supporter count (baseline -- real signups are added automatically)",
      },
      { name: "goal", label: "Supporter goal (number)" },
      { name: "objective", label: "Objective", type: "textarea" },
      { name: "background", label: "Background (blank line = new paragraph)", type: "textarea" },
      { name: "why", label: "Why this matters", type: "textarea" },
      {
        name: "milestones",
        label: "Milestones, one per line: STATUS | DATE | TITLE (status = DONE/ACTIVE/NEXT)",
        type: "textarea",
      },
      { name: "participate", label: "How to participate, one action per line", type: "textarea" },
      {
        name: "volunteerAreas",
        label: "Relevant volunteer areas, one per line",
        type: "textarea",
      },
    ],
    // 13 fields flat was the worst offender in the old dialog -- grouped by
    // what each one actually feeds: the card/hero, the progress bar, the
    // detail page's story copy, and the timeline + CTA list.
    sections: [
      { title: "Basics", fields: ["title", "status", "cta", "location", "image"] },
      { title: "Progress", fields: ["supporters", "goal"] },
      { title: "Story", fields: ["description", "objective", "background", "why"] },
      { title: "Timeline & Participation", fields: ["milestones", "participate", "volunteerAreas"] },
    ],
  },
  testimonials: {
    label: "Testimonials",
    titleField: "name",
    subField: "role",
    fields: [
      { name: "name", label: "Name" },
      { name: "role", label: "Role / City" },
      { name: "quote", label: "Quote", type: "textarea" },
      { name: "avatar", label: "Avatar image", type: "image" },
    ],
  },
  leaders: {
    label: "Leaders (Legacy)",
    titleField: "name",
    subField: "role",
    fields: [
      { name: "name", label: "Name" },
      { name: "role", label: "Role" },
      { name: "years", label: "Years (e.g. 1869-1948)" },
      { name: "quote", label: "Quote", type: "textarea" },
      { name: "image", label: "Portrait image", type: "image" },
    ],
  },
  // Powers the volunteer dashboard's task board: volunteers see every OPEN
  // opportunity and can mark ones they've completed, which drives their
  // contribution count and badge.
  opportunities: {
    label: "Volunteer Opportunities",
    titleField: "title",
    subField: "area",
    fields: [
      { name: "title", label: "Title" },
      { name: "description", label: "Description", type: "textarea" },
      {
        name: "area",
        label: "Area (Research/Content Writing/Graphic Design/Social Media/Legal Research/RTI & Policy Research/Event Coordination/Technology & Development/Community Outreach)",
      },
      { name: "effort", label: "Time commitment (e.g. 1-2 hours, Ongoing)" },
      { name: "status", label: "Status (OPEN/CLOSED)" },
      { name: "link", label: "External resource link (optional)" },
    ],
  },
};

export const TYPE_ORDER = [
  "blogs",
  "news",
  "faq",
  "jurisdictions",
  "myths",
  "resources",
  "campaigns",
  "testimonials",
  "leaders",
  "opportunities",
];

/*
 * Mirrors ALL_PERMISSIONS in backend/server.py -- one permission key per
 * content type, plus three cross-cutting ones. Kept in sync by hand rather
 * than fetched, since it's small, stable, and used to render checkboxes
 * before any API call could supply it.
 */
export const ALL_PERMISSIONS = [
  ...TYPE_ORDER.map((t) => ({ key: `content.${t}`, label: `Edit ${SCHEMAS[t].label}` })),
  { key: "submissions.view", label: "View submissions (supporters, volunteers, messages)" },
  { key: "analytics.view", label: "View analytics" },
  { key: "users.manage", label: "Manage admin users and permissions" },
];
