import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Download, Eye, Loader2, Search, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { listSubmissions } from "@/lib/adminApi";

const SUBMISSION_KINDS = [
  { key: "supporters", label: "Supporters" },
  { key: "volunteers", label: "Volunteers" },
  { key: "contacts", label: "Messages" },
  { key: "newsletter", label: "Newsletter" },
];

/*
 * Curated, per-kind column sets rather than a raw Object.keys dump -- each
 * document has a couple of fields (id, hashes already excluded server-side)
 * that aren't worth a column, and a raw dump put them in whatever order Mongo
 * happened to return, which drifted from record to record if fields were
 * ever added later.
 */
const COLUMNS = {
  supporters: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "movement_id", label: "Movement ID", mono: true },
    { key: "state", label: "State" },
    { key: "city", label: "City" },
    { key: "campaign_id", label: "Campaign" },
    { key: "referred_by", label: "Referred by", mono: true },
    { key: "pledge", label: "Pledge", type: "bool" },
    { key: "created_at", label: "Joined", type: "date" },
  ],
  volunteers: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "volunteer_id", label: "Volunteer ID", mono: true },
    { key: "phone", label: "Phone" },
    { key: "state", label: "State" },
    { key: "profession", label: "Profession" },
    { key: "reason", label: "Reason", truncate: true },
    { key: "created_at", label: "Joined", type: "date" },
  ],
  contacts: [
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "subject", label: "Subject" },
    { key: "message", label: "Message", truncate: true },
    { key: "created_at", label: "Sent", type: "date" },
  ],
  newsletter: [
    { key: "email", label: "Email" },
    { key: "created_at", label: "Subscribed", type: "date" },
  ],
};

const fmtDate = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? String(v)
    : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

const cellValue = (col, row) => {
  const raw = row[col.key];
  if (col.type === "bool") return raw ? "Yes" : "No";
  if (col.type === "date") return fmtDate(raw);
  return raw ?? "—";
};

/** Quotes a CSV field only when it needs it, so simple values stay readable raw. */
const csvField = (v) => {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function downloadCsv(kind, columns, rows) {
  const header = columns.map((c) => c.label).join(",");
  const lines = rows.map((r) => columns.map((c) => csvField(cellValue(c, r))).join(","));
  const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `rtr-${kind}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function SubmissionsViewer() {
  const [kind, setKind] = useState("supporters");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    setLoading(true);
    setQuery("");
    listSubmissions(kind)
      .then(setRows)
      .catch(() => {
        setRows([]);
        toast.error("Could not load submissions");
      })
      .finally(() => setLoading(false));
  }, [kind]);

  const columns = COLUMNS[kind];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) =>
      columns.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q))
    );
  }, [rows, columns, query]);

  return (
    <div data-testid="submissions-viewer">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-heading text-title-3 font-bold tracking-tight">Submissions</h2>
          <p className="text-body text-muted-foreground">
            People who joined, volunteered, or reached out.
          </p>
        </div>
        <button
          data-testid="submissions-export"
          onClick={() => downloadCsv(kind, columns, filtered)}
          disabled={filtered.length === 0}
          className="inline-flex items-center gap-2 rounded border border-border bg-card px-4 py-2.5 text-body font-semibold text-foreground/80 transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Download className="h-4 w-4" /> Export CSV
        </button>
      </div>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {SUBMISSION_KINDS.map((k) => (
            <button
              key={k.key}
              data-testid={`sub-tab-${k.key}`}
              onClick={() => setKind(k.key)}
              className={`rounded px-4 py-2 text-body font-semibold transition-colors ${kind === k.key ? "bg-foreground text-background" : "border border-border bg-card text-foreground/70 hover:bg-muted"}`}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="submissions-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search this list..."
            className="h-10 rounded pl-9"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-secondary" />
        </div>
      ) : rows.length === 0 ? (
        <p className="rounded border border-border bg-card p-10 text-center text-muted-foreground">
          No records yet.
        </p>
      ) : filtered.length === 0 ? (
        <p className="rounded border border-border bg-card p-10 text-center text-muted-foreground">
          Nothing matches "{query}".
        </p>
      ) : (
        <>
          <p className="mb-2 text-meta text-muted-foreground">
            {filtered.length} of {rows.length} record{rows.length !== 1 ? "s" : ""}
          </p>
          <div className="overflow-x-auto rounded border border-border bg-card">
            <table className="w-full text-left text-body">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  {columns.map((c) => (
                    <th
                      key={c.key}
                      className="whitespace-nowrap px-4 py-3 text-label font-bold uppercase tracking-widest text-muted-foreground"
                    >
                      {c.label}
                    </th>
                  ))}
                  <th className="w-10 px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr
                    key={r.id}
                    data-testid={`sub-row-${r.id}`}
                    className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/30"
                    onClick={() => setDetail(r)}
                  >
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={`max-w-xs truncate px-4 py-3 ${c.mono ? "font-heading" : ""}`}
                      >
                        {cellValue(c, r)}
                      </td>
                    ))}
                    <td className="px-4 py-3 text-muted-foreground">
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Dialog open={!!detail} onOpenChange={(v) => !v && setDetail(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto rounded">
          <DialogHeader>
            <DialogTitle className="font-heading text-title-4">
              {SUBMISSION_KINDS.find((k) => k.key === kind)?.label} record
            </DialogTitle>
            <DialogDescription>Full record, nothing truncated.</DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="space-y-3.5 py-2">
              {columns.map((c) => (
                <div key={c.key}>
                  <p className="text-label font-bold uppercase text-muted-foreground">{c.label}</p>
                  <p className={`mt-0.5 whitespace-pre-wrap text-body ${c.mono ? "font-heading" : ""}`}>
                    {cellValue(c, detail)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
