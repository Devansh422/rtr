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
      // supporters/goal drive the progress bar on the campaign detail page. These
      // existed in the seed data but were previously not editable here.
      { name: "supporters", label: "Supporters so far (number)" },
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
];
