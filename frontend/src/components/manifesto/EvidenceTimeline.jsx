import { Check, Circle } from "lucide-react";

import { cn } from "@/lib/utils";

/*
 * The documentary chain, as a timeline (§12).
 *
 * Renders every stage the API returns, INCLUDING the ones not reached. That is
 * the design decision worth defending: a timeline that listed only what happened
 * would show "RTI filed 12 Jan" and stop, and a reader would have to notice an
 * absence to understand it. Showing "Government reply — not yet received" as its
 * own greyed step makes the gap a fact on the page, which for this module is
 * frequently the most important fact there is.
 *
 * The stages are derived on the server from the records themselves, so this can
 * never show a chronology the documents underneath it contradict.
 */
export default function EvidenceTimeline({ stages = [], className }) {
  if (!stages.length) return null;

  return (
    <ol className={cn("relative", className)} data-testid="evidence-timeline">
      {stages.map((stage, index) => {
        const last = index === stages.length - 1;
        return (
          <li key={stage.key} className="relative flex gap-4 pb-6 last:pb-0">
            {/* The connecting rail, drawn behind the markers and stopped at the
                last one so the chain does not trail off into nothing. */}
            {last ? null : (
              <span
                className={cn(
                  "absolute left-[11px] top-6 h-[calc(100%-1.5rem)] w-px",
                  stage.reached ? "bg-primary/40" : "bg-border"
                )}
                aria-hidden="true"
              />
            )}

            <span
              className={cn(
                "relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
                stage.reached
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-dashed border-border bg-background text-muted-foreground"
              )}
              aria-hidden="true"
            >
              {stage.reached ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-2 w-2" />}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p
                  className={cn(
                    "font-heading text-body font-semibold tracking-tight",
                    !stage.reached && "text-foreground/50"
                  )}
                >
                  {stage.label}
                </p>
                {stage.date ? (
                  <time className="text-meta text-muted-foreground" dateTime={stage.date}>
                    {new Date(stage.date).toLocaleDateString()}
                  </time>
                ) : (
                  <span className="text-meta text-muted-foreground">
                    {stage.reached ? "date not recorded" : "not yet"}
                  </span>
                )}
              </div>
              {stage.detail ? (
                <p
                  className={cn(
                    "mt-1 text-meta leading-relaxed",
                    stage.reached ? "text-foreground/70" : "text-foreground/45"
                  )}
                >
                  {stage.detail}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
