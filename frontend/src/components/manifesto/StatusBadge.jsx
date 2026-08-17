import { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";

/*
 * The three status vocabularies of the accountability module, and the rule that
 * they are never mixed.
 *
 * - PromiseStatusBadge  : what the records establish about implementation.
 * - RtiStatusPill       : where an RTI application has got to.
 * - ResponseStatusBadge : how much of what was asked actually came back.
 *
 * A reader who sees "Information provided" next to "Status not established" is
 * looking at the module working correctly: the authority answered in full, and
 * what it sent does not show the promise implemented. One badge for both would
 * have to pick one of those to report and would be wrong either way.
 *
 * Colours come with a text label in every case. Colour alone would put the whole
 * finding out of reach of a colour-blind reader, and these badges carry the
 * conclusion of the page.
 */

const PROMISE_TONES = {
  fulfilled: "border-emerald-600/30 bg-emerald-600/10 text-emerald-800 dark:text-emerald-300",
  partially_fulfilled: "border-amber-600/30 bg-amber-600/10 text-amber-800 dark:text-amber-300",
  under_implementation: "border-sky-600/30 bg-sky-600/10 text-sky-800 dark:text-sky-300",
  information_insufficient:
    "border-orange-700/30 bg-orange-700/10 text-orange-900 dark:text-orange-300",
  rti_reply_awaited: "border-violet-600/30 bg-violet-600/10 text-violet-800 dark:text-violet-300",
  not_established: "border-border bg-muted text-foreground/70",
};

const PROMISE_DOTS = {
  fulfilled: "bg-emerald-600",
  partially_fulfilled: "bg-amber-500",
  under_implementation: "bg-sky-600",
  information_insufficient: "bg-orange-600",
  rti_reply_awaited: "bg-violet-600",
  not_established: "bg-muted-foreground/60",
};

const RESPONSE_TONES = {
  information_provided:
    "border-emerald-600/30 bg-emerald-600/10 text-emerald-800 dark:text-emerald-300",
  partially_provided: "border-amber-600/30 bg-amber-600/10 text-amber-800 dark:text-amber-300",
  information_insufficient:
    "border-orange-700/30 bg-orange-700/10 text-orange-900 dark:text-orange-300",
  awaited: "border-violet-600/30 bg-violet-600/10 text-violet-800 dark:text-violet-300",
  denied: "border-destructive/30 bg-destructive/10 text-destructive",
  transferred: "border-sky-600/30 bg-sky-600/10 text-sky-800 dark:text-sky-300",
};

/**
 * The promise status.
 *
 * `status` is the API's envelope -- `{key, label, meaning}` -- and never a bare
 * string, so there is no way to render the badge without the sentence that says
 * what it is claiming. The same reasoning as ClaimValue in the platform
 * primitives.
 */
export function PromiseStatusBadge({ status, size = "default", className }) {
  if (!status?.key) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded border font-medium",
        size === "large" ? "px-3 py-1.5 text-body" : "px-2 py-0.5 text-meta",
        PROMISE_TONES[status.key] ?? PROMISE_TONES.not_established,
        className
      )}
      data-testid={`promise-status-${status.key}`}
      title={status.meaning || undefined}
    >
      <span
        className={cn(
          "h-2 w-2 shrink-0 rounded-full",
          PROMISE_DOTS[status.key] ?? PROMISE_DOTS.not_established
        )}
        aria-hidden="true"
      />
      {status.label}
    </span>
  );
}

export function ResponseStatusBadge({ status, className }) {
  if (!status?.key) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-meta font-medium",
        RESPONSE_TONES[status.key] ?? RESPONSE_TONES.awaited,
        className
      )}
      title={status.detail || undefined}
      data-testid={`response-status-${status.key}`}
    >
      {status.label}
    </span>
  );
}

export function RtiStatusPill({ status, label, className }) {
  const answered = status === "reply_received" || status === "partial_reply";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 text-meta font-medium",
        answered
          ? "border-emerald-600/30 bg-emerald-600/10 text-emerald-800 dark:text-emerald-300"
          : "border-border bg-muted/50 text-foreground/70",
        className
      )}
    >
      {label || "Not filed yet"}
    </span>
  );
}

/**
 * "Why this status?" (§13, §24).
 *
 * The requirement this implements is that a reader is never shown a conclusion on
 * its own. It is collapsed by default because the badge is what a scanning reader
 * needs, but the reasoning and the records behind it are one control away and on
 * the same page -- not on a methodology page nobody opens.
 */
export function WhyThisStatus({ status, assessment, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!status?.key) return null;

  return (
    <div className="rounded border border-border bg-card" data-testid="why-this-status">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-4 p-4 text-left"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
          Why this status?
        </span>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 transition-transform", open && "rotate-180")}
          aria-hidden="true"
        />
      </button>

      {open ? (
        <div className="border-t border-border p-5">
          <p className="text-body leading-relaxed text-foreground/80">{status.meaning}</p>

          {assessment?.rationale ? (
            <div className="mt-5">
              <p className="text-label font-bold uppercase text-muted-foreground">
                This platform&apos;s reasoning
              </p>
              <p className="mt-2 whitespace-pre-line text-body leading-relaxed text-foreground/80">
                {assessment.rationale}
              </p>
            </div>
          ) : null}

          {assessment?.methodNote ? (
            <div className="mt-5">
              <p className="text-label font-bold uppercase text-muted-foreground">
                How this was checked
              </p>
              <p className="mt-2 whitespace-pre-line text-meta leading-relaxed text-foreground/70">
                {assessment.methodNote}
              </p>
            </div>
          ) : null}

          {children}

          {assessment?.assessedOn ? (
            <p className="mt-5 text-meta text-muted-foreground">
              Assessed {new Date(assessment.assessedOn).toLocaleDateString()}
              {assessment.version > 1 ? ` · version ${assessment.version}` : ""}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
