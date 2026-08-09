import { Link } from "react-router-dom";
import { Reveal, MaskedLines } from "@/components/motion/Reveal";
import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, ExternalLink, FileQuestion, HelpCircle, Info } from "lucide-react";

/*
 * Shared building blocks for the platform pages.
 *
 * These exist because the same three ideas repeat on almost every new page and each
 * one is a place where a careless rendering would break a rule from
 * IMPLEMENTATION_PLAN.md:
 *
 * - VerificationBadge / ClaimValue: an unverified claim must never render as plain
 *   fact (§7). Centralising it means a page cannot forget the marker.
 * - SourceLink: every claim about a person shows where it came from, and shows
 *   whether that source is the public record itself or a report of it.
 * - Disclaimer: the standard wording appears wherever person-data does, and comes
 *   from the API so the frontend cannot serve a stale version of it.
 */

// --------------------------------------------------------------------------
export function PageHero({ eyebrow, lines, lede, children, testId }) {
  return (
    <section className="full-section-hero px-6 md:px-12" data-testid={testId}>
      <div className="mx-auto w-full max-w-7xl">
        {eyebrow ? (
          <p className="text-label font-bold uppercase text-secondary">{eyebrow}</p>
        ) : null}
        <h1 className="mt-6 font-heading text-title-1 font-semibold leading-[0.95] tracking-tighter">
          <MaskedLines lines={Array.isArray(lines) ? lines : [lines]} />
        </h1>
        {lede ? <p className="mt-8 max-w-3xl text-lead text-foreground/70">{lede}</p> : null}
        {children ? <div className="mt-10">{children}</div> : null}
      </div>
    </section>
  );
}

export function Section({ children, className = "", muted = false, testId }) {
  return (
    <section
      className={cn(
        "full-section px-6 md:px-12",
        muted && "border-t border-border bg-muted/30",
        className
      )}
      data-testid={testId}
    >
      <div className="mx-auto w-full max-w-7xl">{children}</div>
    </section>
  );
}

export function SectionHeading({ eyebrow, title, lede, action }) {
  return (
    <Reveal>
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="max-w-2xl">
          {eyebrow ? (
            <p className="text-label font-bold uppercase text-secondary">{eyebrow}</p>
          ) : null}
          <h2 className="mt-3 font-heading text-title-2 font-semibold tracking-tight">{title}</h2>
          {lede ? <p className="mt-3 text-body text-foreground/70">{lede}</p> : null}
        </div>
        {action}
      </div>
    </Reveal>
  );
}

// --------------------------------------------------------------------------
// Verification (§7)
// --------------------------------------------------------------------------
const BADGE_STYLES = {
  fact_checked: {
    className: "border-emerald-600/30 bg-emerald-600/10 text-emerald-800 dark:text-emerald-300",
    Icon: CheckCircle2,
  },
  unverified: {
    className: "border-amber-600/30 bg-amber-600/10 text-amber-800 dark:text-amber-300",
    Icon: HelpCircle,
  },
  disputed: {
    className: "border-orange-700/30 bg-orange-700/10 text-orange-900 dark:text-orange-300",
    Icon: AlertTriangle,
  },
  retracted: {
    className: "border-destructive/30 bg-destructive/10 text-destructive",
    Icon: AlertTriangle,
  },
};

/** The visible marker on every sourced claim. Never omitted, never abbreviated away. */
export function VerificationBadge({ status, label, className }) {
  const style = BADGE_STYLES[status] ?? BADGE_STYLES.unverified;
  const { Icon } = style;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-meta font-medium",
        style.className,
        className
      )}
      data-testid={`verification-${status}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}

/**
 * A citation link that says what kind of source it is.
 *
 * The primary/secondary distinction is surfaced rather than hidden: "ECI affidavit"
 * and "a news report about an ECI affidavit" are both citations, and they are not
 * the same evidence.
 */
export function SourceLink({ citation, className }) {
  if (!citation?.url) return null;
  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noreferrer noopener"
      className={cn(
        "inline-flex items-start gap-1.5 text-meta text-foreground/70 underline-offset-4 hover:text-primary hover:underline",
        className
      )}
    >
      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>
        {citation.title || citation.url}
        {citation.sourceDate ? ` (${citation.sourceDate})` : ""}
        {citation.publisher ? ` - ${citation.publisher}` : ""}
        <span
          className={cn(
            "ml-1.5 rounded border px-1 py-px text-[10px] uppercase tracking-wide",
            citation.isPrimary
              ? "border-emerald-600/30 text-emerald-700 dark:text-emerald-400"
              : "border-border text-muted-foreground"
          )}
        >
          {citation.isPrimary ? "primary" : "secondary"}
        </span>
      </span>
    </a>
  );
}

/**
 * One sourced figure, rendered from the API's claim envelope.
 *
 * The envelope shape is what makes this safe: the component receives
 * `{value, status, statusLabel, citation}` and never a bare number, so there is no
 * way to render the figure without its verification state.
 */
export function ClaimValue({ claim }) {
  const isFact = claim.isFact;
  return (
    <div
      className="rounded border border-border bg-card p-5"
      data-testid={`claim-${claim.fieldKey}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-label font-bold uppercase text-muted-foreground">
            {claim.label}
            {claim.period ? <span className="ml-2 normal-case">{claim.period}</span> : null}
          </p>
          <p
            className={cn(
              "mt-1 font-heading text-title-3 font-semibold tracking-tight",
              !isFact && "text-foreground/70"
            )}
          >
            {claim.display ?? claim.value ?? "-"}
          </p>
        </div>
        <VerificationBadge status={claim.status} label={claim.statusLabel} />
      </div>

      {claim.explanation ? (
        <p className="mt-3 text-meta leading-relaxed text-foreground/70">{claim.explanation}</p>
      ) : null}

      {claim.reviewNote ? (
        <p className="mt-3 rounded border border-orange-700/30 bg-orange-700/5 p-3 text-meta text-foreground/80">
          <strong className="font-semibold">Reviewer's note: </strong>
          {claim.reviewNote}
        </p>
      ) : null}

      <SourceLink citation={claim.citation} className="mt-3" />
    </div>
  );
}

// --------------------------------------------------------------------------
export function Disclaimer({ text, title = "About this information" }) {
  if (!text) return null;
  return (
    <div
      className="rounded border border-border bg-muted/40 p-5"
      data-testid="standard-disclaimer"
    >
      <p className="flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
        <Info className="h-4 w-4" aria-hidden="true" />
        {title}
      </p>
      <p className="mt-2 text-meta leading-relaxed text-foreground/70">{text}</p>
    </div>
  );
}

/**
 * Empty state that says WHY something is empty.
 *
 * "No representatives found" reads as a broken site. "We have published 12 profiles
 * so far, starting with the pilot states -- here is how to help" reads as a project
 * in progress, which is the truth.
 */
export function EmptyState({ title, body, action, testId }) {
  return (
    <div
      className="rounded border border-dashed border-border bg-card/50 p-10 text-center"
      data-testid={testId ?? "empty-state"}
    >
      <FileQuestion className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
      <p className="mt-4 font-heading text-lead font-semibold tracking-tight">{title}</p>
      {body ? <p className="mx-auto mt-2 max-w-lg text-body text-foreground/70">{body}</p> : null}
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function Pill({ children, tone = "default", className }) {
  const tones = {
    default: "border-border bg-muted/50 text-foreground/80",
    primary: "border-primary/30 bg-primary/10 text-primary",
    secondary: "border-secondary/40 bg-secondary/15 text-secondary-foreground",
    muted: "border-border bg-transparent text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 text-meta font-medium",
        tones[tone] ?? tones.default,
        className
      )}
    >
      {children}
    </span>
  );
}

export function StatTile({ label, value, sub, tone = "default" }) {
  return (
    <div className="rounded border border-border bg-card p-5">
      <p className="text-label font-bold uppercase text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 font-heading text-title-2 font-semibold tracking-tight",
          tone === "primary" && "text-primary"
        )}
      >
        {value}
      </p>
      {sub ? <p className="mt-1 text-meta text-foreground/60">{sub}</p> : null}
    </div>
  );
}

/** Newest-first change history, as rendered on every public history tab (§7). */
export function HistoryList({ entries, emptyText = "No changes recorded yet." }) {
  if (!entries?.length) {
    return <p className="text-body text-foreground/60">{emptyText}</p>;
  }
  return (
    <ol className="space-y-4" data-testid="history-list">
      {entries.map((entry) => (
        <li key={entry.id} className="rounded border border-border bg-card p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-heading text-body font-semibold tracking-tight">{entry.summary}</p>
            <time className="text-meta text-muted-foreground" dateTime={entry.createdAt}>
              {entry.createdAt ? new Date(entry.createdAt).toLocaleDateString() : ""}
            </time>
          </div>
          {entry.changes ? (
            <dl className="mt-2 space-y-1">
              {Object.entries(entry.changes).map(([field, change]) => (
                <div key={field} className="flex flex-wrap gap-2 text-meta">
                  <dt className="font-medium text-muted-foreground">{field}</dt>
                  <dd className="text-foreground/70">
                    <span className="line-through opacity-60">{String(change.before ?? "-")}</span>
                    <span aria-hidden="true"> &rarr; </span>
                    <span>{String(change.after ?? "-")}</span>
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
          {entry.sourceUrl ? (
            <SourceLink citation={{ url: entry.sourceUrl, title: "Source for this change" }} className="mt-2" />
          ) : null}
          {/* Contributor identity is deliberately absent -- see backend/core/audit.py. */}
        </li>
      ))}
    </ol>
  );
}

export function CardLink({ to, children, className }) {
  return (
    <Link
      to={to}
      className={cn(
        "group flex h-full flex-col rounded border border-border bg-card p-6 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40",
        className
      )}
    >
      {children}
    </Link>
  );
}
