import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

/*
 * The eight-stage Right to Recall pipeline, as a progress rail.
 *
 * Stage definitions come from the API (`/api/campaign-stages`) rather than being
 * hardcoded here, so the labels and the ordering have exactly one source -- adding a
 * stage later must not require editing a React component.
 */
export default function CampaignPipeline({ stages, currentIndex, compact = false }) {
  if (!stages?.length) return null;

  return (
    <ol
      className={cn("flex flex-col gap-0", compact && "gap-0")}
      data-testid="campaign-pipeline"
      aria-label="Right to Recall campaign stages"
    >
      {stages.map((stage, index) => {
        const done = index < currentIndex;
        const current = index === currentIndex;
        return (
          <li key={stage.key} className="flex gap-4">
            {/* Rail: a filled dot for reached stages, a hollow one for the rest. */}
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-meta font-bold",
                  done && "border-primary bg-primary text-primary-foreground",
                  current && "border-primary bg-primary/15 text-primary",
                  !done && !current && "border-border bg-card text-muted-foreground"
                )}
                aria-hidden="true"
              >
                {done ? <Check className="h-4 w-4" /> : index + 1}
              </span>
              {index < stages.length - 1 ? (
                <span
                  className={cn(
                    "w-0.5 flex-1",
                    compact ? "min-h-6" : "min-h-10",
                    done ? "bg-primary" : "bg-border"
                  )}
                  aria-hidden="true"
                />
              ) : null}
            </div>

            <div className={cn("pb-6", index === stages.length - 1 && "pb-0")}>
              <p
                className={cn(
                  "font-heading font-semibold tracking-tight",
                  compact ? "text-body" : "text-lead",
                  current ? "text-primary" : done ? "text-foreground" : "text-foreground/50"
                )}
              >
                {stage.label}
                {current ? (
                  <span className="ml-2 rounded border border-primary/30 bg-primary/10 px-1.5 py-px text-meta font-medium text-primary">
                    Current stage
                  </span>
                ) : null}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
