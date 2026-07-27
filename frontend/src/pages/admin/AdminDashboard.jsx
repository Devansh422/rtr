import { useEffect, useState } from "react";
import { LogOut, ExternalLink, Users, Loader2, LayoutGrid, Inbox, BarChart3 } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { SCHEMAS, TYPE_ORDER } from "@/pages/admin/schemas";
import ContentManager from "@/components/admin/ContentManager";
import Analytics from "@/components/admin/Analytics";
import { listSubmissions } from "@/lib/adminApi";

const SUBMISSION_KINDS = [
  { key: "supporters", label: "Supporters" },
  { key: "volunteers", label: "Volunteers" },
  { key: "contacts", label: "Messages" },
  { key: "newsletter", label: "Newsletter" },
];

function SubmissionsViewer() {
  const [kind, setKind] = useState("supporters");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listSubmissions(kind)
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [kind]);

  const columns = rows[0] ? Object.keys(rows[0]).filter((k) => k !== "id") : [];

  return (
    <div data-testid="submissions-viewer">
      <h2 className="mb-1 font-heading text-title-3 font-bold tracking-tight">Submissions</h2>
      <p className="mb-6 text-body text-muted-foreground">
        People who joined, volunteered, or reached out.
      </p>
      <div className="mb-6 flex flex-wrap gap-2">
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
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-secondary" />
        </div>
      ) : rows.length === 0 ? (
        <p className="rounded border border-border bg-card p-10 text-center text-muted-foreground">
          No records yet.
        </p>
      ) : (
        <div className="overflow-x-auto rounded border border-border bg-card">
          <table className="w-full text-left text-body">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                {columns.map((c) => (
                  <th
                    key={c}
                    className="whitespace-nowrap px-4 py-3 font-bold uppercase tracking-widest text-muted-foreground"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-border last:border-0">
                  {columns.map((c) => (
                    <td key={c} className="max-w-xs truncate px-4 py-3">
                      {String(r[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function AdminDashboard() {
  const { user, logout } = useAdminAuth();
  const [active, setActive] = useState(TYPE_ORDER[0]);

  return (
    <div className="min-h-screen bg-background text-foreground" data-testid="admin-dashboard">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-8 md:flex-row md:px-8">
        {/* Sidebar */}
        <aside className="md:w-64 md:shrink-0">
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="RTR" className="h-10 w-10 rounded object-cover" />
            <div className="leading-none">
              <p className="font-heading text-body font-bold">Admin</p>
              <p className="text-meta text-muted-foreground">{user?.email}</p>
            </div>
          </div>

          <p className="mt-8 mb-2 flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
            <LayoutGrid className="h-3.5 w-3.5" /> Content
          </p>
          <nav className="flex flex-col gap-1">
            {TYPE_ORDER.map((t) => (
              <button
                key={t}
                data-testid={`tab-${t}`}
                onClick={() => setActive(t)}
                className={`rounded px-3 py-2 text-left text-body font-medium transition-colors ${active === t ? "bg-primary text-primary-foreground" : "text-foreground/70 hover:bg-muted"}`}
              >
                {SCHEMAS[t].label}
              </button>
            ))}
          </nav>

          <p className="mt-6 mb-2 flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
            <Inbox className="h-3.5 w-3.5" /> People
          </p>
          <button
            data-testid="tab-submissions"
            onClick={() => setActive("__submissions")}
            className={`w-full rounded px-3 py-2 text-left text-body font-medium transition-colors ${active === "__submissions" ? "bg-primary text-primary-foreground" : "text-foreground/70 hover:bg-muted"}`}
          >
            <span className="flex items-center gap-2">
              <Users className="h-4 w-4" /> Submissions
            </span>
          </button>

          <p className="mt-6 mb-2 flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
            <BarChart3 className="h-3.5 w-3.5" /> Insights
          </p>
          <button
            data-testid="tab-analytics"
            onClick={() => setActive("__analytics")}
            className={`w-full rounded px-3 py-2 text-left text-body font-medium transition-colors ${active === "__analytics" ? "bg-primary text-primary-foreground" : "text-foreground/70 hover:bg-muted"}`}
          >
            <span className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" /> Analytics
            </span>
          </button>

          <div className="mt-8 space-y-1 border-t border-border pt-4">
            <a
              href="/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded px-3 py-2 text-body font-medium text-foreground/70 transition-colors hover:bg-muted"
            >
              <ExternalLink className="h-4 w-4" /> View site
            </a>
            <button
              data-testid="admin-logout"
              onClick={logout}
              className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-body font-medium text-destructive transition-colors hover:bg-destructive/10"
            >
              <LogOut className="h-4 w-4" /> Log out
            </button>
          </div>
        </aside>

        {/* Main */}
        <main className="min-w-0 flex-1">
          {active === "__submissions" ? (
            <SubmissionsViewer />
          ) : active === "__analytics" ? (
            <Analytics />
          ) : (
            <ContentManager key={active} type={active} schema={SCHEMAS[active]} />
          )}
        </main>
      </div>
    </div>
  );
}
