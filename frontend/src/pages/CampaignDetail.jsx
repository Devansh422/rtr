import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Circle,
  Download,
  Loader2,
  MapPin,
  Target,
} from "lucide-react";
import { toast } from "sonner";
import { Reveal, MaskedLines } from "@/components/motion/Reveal";
import ShareButtons from "@/components/ShareButtons";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { useJoin } from "@/context/JoinContext";
import { gsap, prefersReducedMotion } from "@/lib/motion";
import { getCampaign, getResources } from "@/lib/api";
import {
  toParagraphs,
  toLines,
  parseMilestones,
  progressPercent,
  formatCount,
  formatMonth,
} from "@/lib/content";

const STATUS_STYLES = {
  ACTIVE: "bg-primary text-primary-foreground",
  UPCOMING: "bg-secondary text-secondary-foreground",
  VICTORY: "bg-foreground text-background",
};

const MILESTONE_STYLES = {
  DONE: { dot: "bg-secondary text-secondary-foreground", Icon: Check, label: "Complete" },
  ACTIVE: { dot: "bg-primary text-primary-foreground", Icon: Circle, label: "In progress" },
  NEXT: { dot: "bg-muted text-muted-foreground", Icon: Circle, label: "Planned" },
};

/**
 * Supporter-count progress bar. The fill animates from 0 on scroll-in so the
 * number lands with the bar rather than before it.
 */
function ProgressBar({ supporters, goal }) {
  const pct = progressPercent(supporters, goal);
  const fillRef = useRef(null);

  useEffect(() => {
    const el = fillRef.current;
    if (!el || pct === null) return;

    if (prefersReducedMotion()) {
      gsap.set(el, { width: `${pct}%` });
      return;
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { width: "0%" },
        {
          width: `${pct}%`,
          duration: 1.2,
          ease: "power3.out",
          scrollTrigger: { trigger: el, start: "top bottom-=80", once: true },
        }
      );
    }, el);

    return () => ctx.revert();
  }, [pct]);

  // Nothing meaningful to show without a valid goal.
  if (pct === null) return null;

  return (
    <div data-testid="campaign-progress">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <p className="font-heading text-title-2 font-extrabold">
          {formatCount(supporters)}
          <span className="ml-2 text-body font-semibold text-muted-foreground">
            of {formatCount(goal)} supporters
          </span>
        </p>
        <p className="font-heading text-title-4 font-bold text-secondary">{Math.round(pct)}%</p>
      </div>
      <div
        className="mt-4 h-2.5 w-full overflow-hidden rounded bg-muted"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Campaign progress toward supporter goal"
      >
        <div ref={fillRef} className="h-full rounded bg-primary" style={{ width: 0 }} />
      </div>
    </div>
  );
}

export default function CampaignDetail() {
  const { id } = useParams();
  const { openJoin } = useJoin();
  const [campaign, setCampaign] = useState(null);
  const [resources, setResources] = useState([]);
  const [state, setState] = useState("loading"); // loading | ready | missing

  useEffect(() => {
    let cancelled = false;
    setState("loading");

    getCampaign(id)
      .then((data) => {
        if (cancelled) return;
        setCampaign(data);
        setState(data ? "ready" : "missing");
      })
      .catch(() => {
        if (!cancelled) setState("missing");
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  // Shared resource library, shown as this campaign's downloads. Failure here
  // is non-fatal -- the section simply doesn't render.
  useEffect(() => {
    let cancelled = false;
    getResources()
      .then((list) => {
        if (!cancelled) setResources(list.slice(0, 4));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return (
      <div className="full-section-hero px-6 md:px-12" data-testid="campaign-loading">
        <div className="mx-auto flex w-full max-w-5xl justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-secondary" aria-label="Loading campaign" />
        </div>
      </div>
    );
  }

  if (state === "missing" || !campaign) {
    return (
      <div className="full-section-hero px-6 md:px-12" data-testid="campaign-missing">
        <div className="mx-auto w-full max-w-3xl text-center">
          <p className="text-label font-bold uppercase text-secondary">404</p>
          <h1 className="mt-4 font-heading text-title-1 font-extrabold">
            We couldn't find that campaign.
          </h1>
          <p className="mt-4 text-foreground/70">
            It may have concluded or been renamed. All active campaigns are listed here.
          </p>
          <LinkButton to="/campaigns" variant="outline" className="mt-8">
            <ArrowLeft className="h-4 w-4" /> All campaigns
          </LinkButton>
        </div>
      </div>
    );
  }

  const background = toParagraphs(campaign.background);
  const milestones = parseMilestones(campaign.milestones);
  const participate = toLines(campaign.participate);
  const volunteerAreas = toLines(campaign.volunteerAreas);

  const handleDownload = async (resource) => {
    // The resource `file` field is not yet wired to real object storage, so this
    // acknowledges the request rather than streaming bytes.
    await new Promise((resolve) => setTimeout(resolve, 600));
    toast.success(`${resource.title} is coming to your inbox soon!`);
  };

  return (
    <div data-testid="campaign-detail-page">
      {/* HERO */}
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          <Link
            to="/campaigns"
            className="inline-flex items-center gap-2 text-label font-bold uppercase text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> All campaigns
          </Link>

          <div className="mt-8 grid gap-12 lg:grid-cols-12 lg:gap-16">
            <div className="lg:col-span-7">
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`inline-block rounded px-3 py-1 text-label font-bold uppercase ${
                    STATUS_STYLES[campaign.status] || "bg-muted"
                  }`}
                >
                  {campaign.status}
                </span>
                {campaign.location && (
                  <span className="inline-flex items-center gap-1.5 text-label font-semibold uppercase text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" aria-hidden="true" /> {campaign.location}
                  </span>
                )}
              </div>

              <h1 className="mt-6 font-heading text-title-1 font-extrabold leading-[0.95]">
                <MaskedLines lines={[campaign.title]} start={0.1} />
              </h1>

              <div className="tricolor-bar mt-8 h-1.5 w-24 rounded" aria-hidden="true" />

              <p className="mt-8 max-w-2xl text-title-4 text-foreground/70">
                {campaign.description}
              </p>

              <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
                <DynamicButton
                  onClick={() => openJoin(campaign.id)}
                  size="lg"
                  data-testid="campaign-detail-cta"
                >
                  {campaign.cta || "Join this campaign"}
                  <ArrowRight className="h-5 w-5" />
                </DynamicButton>
                <LinkButton to="/volunteer" variant="outline" size="sm">
                  Volunteer
                </LinkButton>
              </div>
            </div>

            <div className="lg:col-span-5">
              {campaign.image && (
                <div className="overflow-hidden rounded border border-border">
                  <img
                    src={campaign.image}
                    alt=""
                    className="h-64 w-full object-cover md:h-80"
                    loading="lazy"
                  />
                </div>
              )}
              <div className="mt-6 rounded border border-border bg-card p-6">
                {/*
                 * liveSupporters (baseline + real /join signups attributed to
                 * this campaign) falls back to the raw admin baseline if the API
                 * hasn't computed it for some reason -- never render nothing.
                 */}
                <ProgressBar
                  supporters={campaign.liveSupporters ?? campaign.supporters}
                  goal={campaign.goal}
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* OBJECTIVE + BACKGROUND */}
      {(campaign.objective || background.length > 0) && (
        <section className="full-section border-t border-border px-6 md:px-12">
          <div className="mx-auto w-full max-w-7xl">
            <div className="grid gap-12 lg:grid-cols-12 lg:gap-16">
              <div className="lg:col-span-5">
                <Reveal>
                  <p className="text-label font-bold uppercase text-secondary">The objective</p>
                  <h2 className="mt-4 font-heading text-title-1 font-extrabold leading-tight">
                    What this campaign sets out to do.
                  </h2>
                </Reveal>
                {campaign.objective && (
                  <Reveal delay={0.1}>
                    <div className="mt-8 flex gap-4 rounded border border-border bg-card p-6">
                      <Target className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                      <p className="text-foreground/80">{campaign.objective}</p>
                    </div>
                  </Reveal>
                )}
              </div>

              {background.length > 0 && (
                <div className="lg:col-span-7">
                  <Reveal delay={0.15}>
                    <p className="text-label font-bold uppercase text-muted-foreground">
                      Background
                    </p>
                  </Reveal>
                  <div className="mt-6 space-y-5">
                    {background.map((para, i) => (
                      <Reveal key={i} delay={0.2 + i * 0.05}>
                        <p className="leading-relaxed text-foreground/80">{para}</p>
                      </Reveal>
                    ))}
                  </div>
                  {campaign.why && (
                    <Reveal delay={0.3}>
                      <blockquote className="mt-8 border-l-2 border-primary pl-6">
                        <p className="font-heading text-title-3 font-bold leading-snug">
                          {campaign.why}
                        </p>
                        <footer className="mt-3 text-label font-bold uppercase text-muted-foreground">
                          Why it matters
                        </footer>
                      </blockquote>
                    </Reveal>
                  )}
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* MILESTONES */}
      {milestones.length > 0 && (
        <section className="full-section border-t border-border bg-muted/30 px-6 md:px-12">
          <div className="mx-auto w-full max-w-5xl">
            <Reveal>
              <p className="text-label font-bold uppercase text-secondary">Progress</p>
              <h2 className="mt-4 font-heading text-title-1 font-extrabold leading-tight">
                Milestones, in the open.
              </h2>
            </Reveal>

            <ol className="mt-12 space-y-0" data-testid="campaign-milestones">
              {milestones.map((m, i) => {
                const style = MILESTONE_STYLES[m.status] || MILESTONE_STYLES.NEXT;
                const isLast = i === milestones.length - 1;
                return (
                  <li key={i} className="relative flex gap-5 pb-8 last:pb-0">
                    {/* Connector rail, omitted on the final item. */}
                    {!isLast && (
                      <span
                        className="absolute left-[15px] top-8 h-full w-px bg-border"
                        aria-hidden="true"
                      />
                    )}
                    <span
                      className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded ${style.dot}`}
                    >
                      <style.Icon
                        className={m.status === "DONE" ? "h-4 w-4" : "h-2.5 w-2.5 fill-current"}
                        aria-hidden="true"
                      />
                    </span>
                    <Reveal delay={i * 0.06} className="flex-1">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        {m.date && (
                          <span className="font-heading text-body font-bold text-secondary">
                            {formatMonth(m.date)}
                          </span>
                        )}
                        <span className="text-[0.65rem] font-bold uppercase tracking-widest text-muted-foreground">
                          {style.label}
                        </span>
                      </div>
                      <p className="mt-1.5 font-heading text-lead font-bold leading-snug">
                        {m.title}
                      </p>
                    </Reveal>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>
      )}

      {/* PARTICIPATE */}
      {participate.length > 0 && (
        <section className="full-section border-t border-border px-6 md:px-12">
          <div className="mx-auto w-full max-w-7xl">
            <Reveal>
              <p className="text-label font-bold uppercase text-secondary">Get involved</p>
              <h2 className="mt-4 max-w-2xl font-heading text-title-1 font-extrabold leading-tight">
                How citizens can take part.
              </h2>
            </Reveal>

            <div className="mt-12 grid gap-4 md:grid-cols-2">
              {participate.map((action, i) => (
                <Reveal key={i} delay={i * 0.06}>
                  <div className="flex h-full items-start gap-4 rounded border border-border bg-card p-6">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-primary font-heading text-meta font-bold text-primary-foreground">
                      {i + 1}
                    </span>
                    <p className="text-foreground/80">{action}</p>
                  </div>
                </Reveal>
              ))}
            </div>

            {volunteerAreas.length > 0 && (
              <Reveal delay={0.2}>
                <div className="mt-12 rounded border border-border bg-card p-8">
                  <p className="text-label font-bold uppercase text-muted-foreground">
                    Volunteer skills this campaign needs
                  </p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {volunteerAreas.map((area) => (
                      <span
                        key={area}
                        className="rounded border border-border bg-muted/50 px-3 py-1.5 text-body font-medium"
                      >
                        {area}
                      </span>
                    ))}
                  </div>
                  <LinkButton
                    to="/volunteer"
                    data-testid="campaign-volunteer-link"
                    variant="secondary"
                    size="sm"
                    className="mt-6"
                  >
                    Sign up to volunteer <ArrowRight className="h-4 w-4" />
                  </LinkButton>
                </div>
              </Reveal>
            )}
          </div>
        </section>
      )}

      {/* RESOURCES + SHARE */}
      <section className="full-section border-t border-border bg-muted/30 px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          {resources.length > 0 && (
            <>
              <Reveal>
                <p className="text-label font-bold uppercase text-secondary">Resources</p>
                <h2 className="mt-4 font-heading text-title-1 font-extrabold leading-tight">
                  Downloads and shareables.
                </h2>
              </Reveal>

              <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {resources.map((r, i) => (
                  <Reveal key={r.id} delay={i * 0.06}>
                    <div className="flex h-full flex-col rounded border border-border bg-card p-6">
                      <Download className="h-5 w-5 text-primary" aria-hidden="true" />
                      {r.type && (
                        <p className="mt-4 text-[0.65rem] font-bold uppercase tracking-widest text-muted-foreground">
                          {r.type}
                        </p>
                      )}
                      <h3 className="mt-1.5 font-heading text-lead font-bold leading-snug">
                        {r.title}
                      </h3>
                      <p className="mt-2 flex-1 text-body text-foreground/70">{r.description}</p>
                      <DynamicButton
                        variant="outline"
                        size="sm"
                        className="mt-5 self-start"
                        data-testid={`campaign-resource-${r.id}`}
                        onClick={() => handleDownload(r)}
                      >
                        {r.downloadLabel || "Download"}
                      </DynamicButton>
                    </div>
                  </Reveal>
                ))}
              </div>
            </>
          )}

          <Reveal delay={0.15}>
            <div className="mt-16 flex flex-col items-start justify-between gap-6 rounded border border-border bg-card p-8 md:flex-row md:items-center">
              <div>
                <h3 className="font-heading text-title-3 font-extrabold">Spread the word.</h3>
                <p className="mt-2 text-body text-foreground/70">
                  Every share puts the demand in front of someone new.
                </p>
              </div>
              <ShareButtons title={`${campaign.title} · #RightToRecall`} />
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
