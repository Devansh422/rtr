import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Award,
  Check,
  Copy,
  ExternalLink,
  LogOut,
  Medal,
  Trophy,
  Undo2,
  Users,
} from "lucide-react";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { listMyOpportunities, completeOpportunity, uncompleteOpportunity } from "@/lib/memberApi";
import SupporterCertificate from "@/components/SupporterCertificate";
import ShareButtons from "@/components/ShareButtons";
import DynamicButton from "@/components/DynamicButton";
import Eyebrow from "@/components/Eyebrow";

/*
 * The unified home for anyone who has joined as a supporter, signed up to
 * volunteer, or both -- one email, one login, sections rendered for whichever
 * profiles actually exist. A person who is only a supporter never sees an
 * empty volunteer panel, and vice versa.
 */
const TIER_ICON = { Gold: Trophy, Silver: Medal, Bronze: Award };

const tierIcon = (badge) => {
  const key = Object.keys(TIER_ICON).find((k) => badge?.startsWith(k));
  return TIER_ICON[key] || Users;
};

export default function MemberDashboard() {
  const { profile, logout } = useMemberAuth();
  const navigate = useNavigate();

  const doLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="min-h-svh bg-background" data-testid="member-dashboard">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-5">
          <Link to="/" className="flex items-center gap-3">
            <img src="/logo.png" alt="Right to Recall" className="h-9 w-9 rounded object-cover" />
            <span className="hidden font-heading text-body font-bold sm:block">
              Right to Recall
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <p className="hidden text-meta text-muted-foreground sm:block">{profile?.email}</p>
            <button
              type="button"
              data-testid="member-logout"
              onClick={doLogout}
              className="inline-flex items-center gap-1.5 rounded border border-border px-3 py-2 text-meta font-semibold text-foreground transition-colors hover:bg-muted"
            >
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10 md:py-14">
        <div className="mb-10">
          <Eyebrow>Your dashboard</Eyebrow>
          <h1 className="mt-2 font-heading text-title-2 font-bold">
            Welcome back{profile?.supporter?.name ? `, ${profile.supporter.name.split(" ")[0]}` : profile?.volunteer?.name ? `, ${profile.volunteer.name.split(" ")[0]}` : ""}.
          </h1>
        </div>

        <div className="space-y-10">
          {profile?.supporter && <SupporterSection supporter={profile.supporter} />}
          {profile?.volunteer && <VolunteerSection volunteer={profile.volunteer} />}
        </div>
      </main>
    </div>
  );
}

function SectionHeading({ eyebrow, title, badge }) {
  const Icon = tierIcon(badge);
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2 className="mt-1.5 font-heading text-title-3 font-bold">{title}</h2>
      </div>
      {badge && (
        <div
          className="flex items-center gap-2 rounded border border-border bg-card px-4 py-2"
          data-testid="badge-pill"
        >
          <Icon className="h-4 w-4 text-secondary" aria-hidden="true" />
          <span className="text-label font-bold uppercase">{badge}</span>
        </div>
      )}
    </div>
  );
}

function SupporterSection({ supporter }) {
  const referralLink = useMemo(() => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    return `${origin}/join?ref=${encodeURIComponent(supporter.movement_id)}`;
  }, [supporter.movement_id]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(referralLink);
      toast.success("Referral link copied!");
    } catch {
      toast.error("Could not copy link");
    }
  };

  return (
    <section data-testid="supporter-section">
      <SectionHeading eyebrow="Supporter" title="Your certificate & impact" badge={supporter.badge} />

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <div className="rounded border border-border bg-card p-6">
          <div className="grid grid-cols-2 gap-5">
            <Stat label="Movement ID" value={supporter.movement_id} mono />
            <Stat label="Referrals" value={supporter.referralCount} />
            <Stat label="State" value={supporter.state || "—"} />
            <Stat label="Pledge" value={supporter.pledge ? "Taken" : "Not yet"} />
          </div>

          <div className="mt-6 border-t border-border pt-5">
            <p className="mb-2 text-label font-bold uppercase text-muted-foreground">
              Invite others, grow your badge
            </p>
            <p className="mb-3 text-meta text-muted-foreground">
              Every friend who joins through your link counts toward your advocate tier.
            </p>
            <div className="flex items-stretch gap-2">
              <input
                readOnly
                data-testid="referral-link"
                value={referralLink}
                onFocus={(e) => e.target.select()}
                className="h-10 flex-1 truncate rounded border border-input bg-background px-3 text-meta text-foreground outline-none"
              />
              <button
                type="button"
                data-testid="copy-referral-link"
                onClick={copyLink}
                aria-label="Copy referral link"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-foreground text-background transition-opacity hover:opacity-85"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-3">
              <ShareButtons
                url={referralLink}
                title="Join me in supporting the #RightToRecall Movement"
              />
            </div>
          </div>
        </div>

        <SupporterCertificate
          name={supporter.name}
          movementId={supporter.movement_id}
          date={supporter.created_at}
        />
      </div>
    </section>
  );
}

function VolunteerSection({ volunteer }) {
  const [opportunities, setOpportunities] = useState(null);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    listMyOpportunities()
      .then(setOpportunities)
      .catch(() => setOpportunities([]));
  }, []);

  const toggle = async (opp) => {
    setBusyId(opp.id);
    try {
      if (opp.completed) {
        await uncompleteOpportunity(opp.id);
      } else {
        await completeOpportunity(opp.id);
        toast.success("Marked complete. Thank you!");
      }
      setOpportunities((list) =>
        list.map((o) => (o.id === opp.id ? { ...o, completed: !o.completed } : o))
      );
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setBusyId(null);
    }
  };

  const open = (opportunities || []).filter((o) => o.status !== "CLOSED");
  const closed = (opportunities || []).filter((o) => o.status === "CLOSED");
  const ordered = [...open, ...closed];

  return (
    <section data-testid="volunteer-section">
      <SectionHeading
        eyebrow="Volunteer"
        title="Your opportunities & contributions"
        badge={volunteer.badge}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        <div className="rounded border border-border bg-card p-6">
          <div className="grid grid-cols-2 gap-5">
            <Stat label="Volunteer ID" value={volunteer.volunteer_id} mono />
            <Stat label="Completed" value={volunteer.completedCount} />
            <Stat label="Profession" value={volunteer.profession || "—"} />
            <Stat label="State" value={volunteer.state || "—"} />
          </div>
        </div>

        <div className="overflow-hidden rounded border border-border">
          <div className="flex items-center justify-between gap-4 bg-muted/40 px-5 py-3">
            <p className="text-label font-bold uppercase text-muted-foreground">
              Open opportunities
            </p>
            {opportunities && (
              <span className="text-micro font-bold uppercase text-muted-foreground">
                {open.length} open
              </span>
            )}
          </div>

          {opportunities === null && (
            <div className="bg-card px-5 py-8 text-center text-body text-muted-foreground">
              Loading opportunities…
            </div>
          )}

          {opportunities !== null && ordered.length === 0 && (
            <div className="bg-card px-5 py-8 text-center text-body text-muted-foreground">
              Nothing posted yet. Check back soon.
            </div>
          )}

          <div className="grid gap-px bg-border">
            {ordered.map((o) => (
              <div
                key={o.id}
                data-testid="opportunity-row"
                className={`flex flex-col gap-3 bg-card px-5 py-4 sm:flex-row sm:items-center sm:justify-between ${
                  o.status === "CLOSED" ? "opacity-60" : ""
                }`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-heading text-body font-bold">{o.title}</p>
                    {o.status === "CLOSED" && (
                      <span className="rounded bg-muted px-2 py-0.5 text-micro font-bold uppercase text-muted-foreground">
                        Closed
                      </span>
                    )}
                  </div>
                  {o.description && (
                    <p className="mt-1 line-clamp-2 text-meta text-muted-foreground">
                      {o.description}
                    </p>
                  )}
                  <div className="mt-1.5 flex flex-wrap items-center gap-3 text-micro font-semibold uppercase text-muted-foreground">
                    {o.area && <span>{o.area}</span>}
                    {o.effort && <span>{o.effort}</span>}
                    {o.link && (
                      <a
                        href={o.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-secondary hover:underline"
                      >
                        Resource <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                </div>
                <DynamicButton
                  data-testid={o.completed ? "undo-opportunity" : "complete-opportunity"}
                  size="sm"
                  variant={o.completed ? "outline" : "secondary"}
                  loading={busyId === o.id}
                  onClick={() => toggle(o)}
                  className="shrink-0"
                >
                  {o.completed ? (
                    <>
                      <Undo2 className="h-3.5 w-3.5" /> Undo
                    </>
                  ) : (
                    <>
                      <Check className="h-3.5 w-3.5" /> Mark complete
                    </>
                  )}
                </DynamicButton>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, mono }) {
  return (
    <div>
      <p className="text-micro font-bold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={`mt-1 text-body-sm font-bold ${mono ? "font-heading" : ""}`}>{value}</p>
    </div>
  );
}
