import { useState } from "react";
import {
  LogOut,
  ExternalLink,
  Users,
  LayoutGrid,
  Inbox,
  BarChart3,
  UserCog,
} from "lucide-react";
import { useAdminAuth, hasPermission } from "@/context/AdminAuthContext";
import { SCHEMAS, TYPE_ORDER } from "@/pages/admin/schemas";
import ContentManager from "@/components/admin/ContentManager";
import Analytics from "@/components/admin/Analytics";
import SubmissionsViewer from "@/components/admin/SubmissionsViewer";
import Team from "@/components/admin/Team";

export default function AdminDashboard() {
  const { user, logout } = useAdminAuth();
  // Analytics first: it's the one view that answers "how is the movement
  // doing" at a glance, so it's what an admin should land on rather than
  // whichever content type happened to be first in TYPE_ORDER. Falls through
  // to the first section a restricted admin actually has, so a teammate
  // without analytics.view doesn't land on a section they can't see.
  const [active, setActive] = useState(() => {
    if (hasPermission(user, "analytics.view")) return "__analytics";
    const firstType = TYPE_ORDER.find((t) => hasPermission(user, `content.${t}`));
    if (firstType) return firstType;
    if (hasPermission(user, "submissions.view")) return "__submissions";
    if (hasPermission(user, "users.manage")) return "__team";
    return "__analytics";
  });

  const visibleTypes = TYPE_ORDER.filter((t) => hasPermission(user, `content.${t}`));
  const canViewSubmissions = hasPermission(user, "submissions.view");
  const canViewAnalytics = hasPermission(user, "analytics.view");
  const canManageUsers = hasPermission(user, "users.manage");

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

          {canViewAnalytics && (
            <>
              <p className="mt-8 mb-2 flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
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
            </>
          )}

          {visibleTypes.length > 0 && (
            <>
              <p className="mt-6 mb-2 flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
                <LayoutGrid className="h-3.5 w-3.5" /> Content
              </p>
              <nav className="flex flex-col gap-1">
                {visibleTypes.map((t) => (
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
            </>
          )}

          {canViewSubmissions && (
            <>
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
            </>
          )}

          {canManageUsers && (
            <>
              <p className="mt-6 mb-2 flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
                <UserCog className="h-3.5 w-3.5" /> Team
              </p>
              <button
                data-testid="tab-team"
                onClick={() => setActive("__team")}
                className={`w-full rounded px-3 py-2 text-left text-body font-medium transition-colors ${active === "__team" ? "bg-primary text-primary-foreground" : "text-foreground/70 hover:bg-muted"}`}
              >
                <span className="flex items-center gap-2">
                  <UserCog className="h-4 w-4" /> Manage team
                </span>
              </button>
            </>
          )}

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
          {active === "__submissions" && canViewSubmissions ? (
            <SubmissionsViewer />
          ) : active === "__analytics" && canViewAnalytics ? (
            <Analytics />
          ) : active === "__team" && canManageUsers ? (
            <Team />
          ) : SCHEMAS[active] && visibleTypes.includes(active) ? (
            <ContentManager key={active} type={active} schema={SCHEMAS[active]} />
          ) : (
            <p className="rounded border border-border bg-card p-10 text-center text-muted-foreground">
              You don't have access to any dashboard section yet. Ask an admin with "Manage admin
              users" permission to grant you access.
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
