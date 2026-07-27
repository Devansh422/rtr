import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useLenis } from "lenis/react";
import { Reveal, MaskedLines, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import DynamicButton from "@/components/DynamicButton";
import Eyebrow from "@/components/Eyebrow";
import { getCampaigns } from "@/lib/api";
import { progressPercent, formatCount } from "@/lib/content";
import { cn } from "@/lib/utils";
import { MapPin, ArrowRight } from "lucide-react";

// A 3-column grid of two rows fits one viewport at these card sizes, so the
// collapsed grid shows six cards and everything beyond that hides behind the
// "View all" toggle.
const COLLAPSED_COUNT = 6;

const StatusBadge = ({ status }) => {
  const map = {
    ACTIVE: "bg-primary text-primary-foreground",
    UPCOMING: "bg-secondary text-secondary-foreground",
    VICTORY: "bg-foreground text-background",
  };
  return (
    <span
      className={`rounded px-3 py-1 text-label font-bold uppercase ${map[status] || "bg-muted"}`}
    >
      {status}
    </span>
  );
};

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [filter, setFilter] = useState("ALL");
  const [expanded, setExpanded] = useState(false);
  const gridRef = useRef(null);
  const lenis = useLenis();

  useEffect(() => {
    getCampaigns()
      .then(setCampaigns)
      .catch(() => {});
  }, []);

  // Changing the filter always drops back to the collapsed grid, otherwise a
  // narrow result set would inherit a stale "expanded" view.
  useEffect(() => {
    setExpanded(false);
  }, [filter]);

  const filters = ["ALL", "ACTIVE", "UPCOMING", "VICTORY"];
  const shown = filter === "ALL" ? campaigns : campaigns.filter((c) => c.status === filter);
  const visible = expanded ? shown : shown.slice(0, COLLAPSED_COUNT);
  const hasMore = shown.length > COLLAPSED_COUNT;

  const toggleExpanded = () => {
    if (expanded) {
      setExpanded(false);
      // Collapsing removes everything below the fold, so bring the grid back
      // into view instead of leaving the reader stranded down the page. Route
      // it through Lenis so it uses the page's smooth scrolling.
      if (lenis) lenis.scrollTo(gridRef.current, { offset: -80 });
      else gridRef.current?.scrollIntoView({ behavior: "smooth" });
    } else {
      setExpanded(true);
    }
  };

  return (
    <div data-testid="campaigns-page" className="">
      <section className="full-section-hero mx-auto w-full max-w-7xl px-6 md:px-12">
        <Eyebrow>Campaigns</Eyebrow>
        <h1 className="mt-6 font-heading text-title-1 font-semibold">
          <MaskedLines lines={["Movements in", "motion."]} />
        </h1>
        <p className="mt-8 max-w-2xl text-lead text-foreground/70">
          Real campaigns, real momentum. Pick one that speaks to you and add your voice.
        </p>

        <div className="mt-10 flex flex-wrap gap-2" data-testid="campaign-filters">
          {filters.map((f) => (
            <button
              key={f}
              data-testid={`filter-${f.toLowerCase()}`}
              onClick={() => setFilter(f)}
              className={`rounded px-5 py-2.5 text-body font-semibold transition-colors duration-200 ${
                filter === f
                  ? "bg-foreground text-background"
                  : "border border-border bg-card text-foreground/70 hover:bg-muted"
              }`}
            >
              {f === "ALL" ? "All" : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </section>

      {/*
       * `full-section` only applies while collapsed. Its min-height keeps the
       * two-row grid filling the viewport, but its vertical centring would look
       * wrong once an expanded grid grows several screens tall -- so the
       * expanded state falls back to plain vertical padding.
       */}
      <section
        ref={gridRef}
        className={cn(
          "mx-auto w-full max-w-7xl px-6 md:px-12",
          expanded ? "py-24" : "full-section"
        )}
      >
        <StaggerGroup className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {visible.map((c) => {
            // liveSupporters (baseline + real /join signups) falls back to the
            // raw admin baseline if the API hasn't computed it for some reason.
            const liveCount = c.liveSupporters ?? c.supporters;
            return (
              <StaggerItem key={c.id}>
                <Link
                  to={`/campaigns/${c.id}`}
                  className="group flex h-full flex-col overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-2"
                  data-testid={`campaign-card-${c.id}`}
                >
                  <div className="relative h-52 overflow-hidden">
                    <img
                      src={c.image}
                      alt=""
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    <div className="absolute left-4 top-4">
                      <StatusBadge status={c.status} />
                    </div>
                  </div>
                  <div className="flex flex-1 flex-col p-7">
                    <div className="flex items-center gap-1.5 text-meta font-medium text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5" /> {c.location}
                    </div>
                    <h3 className="mt-3 font-heading text-title-3 font-bold leading-snug">
                      {c.title}
                    </h3>
                    <p className="mt-3 flex-1 text-body text-foreground/70">{c.description}</p>

                    {/* Progress toward the supporter goal, when a goal is set. */}
                    {progressPercent(liveCount, c.goal) !== null && (
                      <div className="mt-5">
                        <div className="flex items-baseline justify-between text-meta">
                          <span className="font-semibold text-foreground/80">
                            {formatCount(liveCount)} supporters
                          </span>
                          <span className="font-bold text-secondary">
                            {Math.round(progressPercent(liveCount, c.goal))}%
                          </span>
                        </div>
                        <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-muted">
                          <div
                            className="h-full rounded bg-primary"
                            style={{ width: `${progressPercent(liveCount, c.goal)}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <span className="mt-6 inline-flex items-center gap-2 text-label font-bold uppercase text-foreground">
                      {c.cta} <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </Link>
              </StaggerItem>
            );
          })}
        </StaggerGroup>

        {/* The count tracks the filtered set, never the unfiltered total. */}
        {hasMore && (
          <div className="mt-12 flex justify-center">
            <DynamicButton
              data-testid="view-all-toggle"
              variant="outline"
              size="default"
              onClick={toggleExpanded}
              aria-expanded={expanded}
            >
              {expanded ? "Show less" : `View all ${shown.length} campaigns`}
            </DynamicButton>
          </div>
        )}

        {shown.length === 0 && (
          <Reveal>
            <p className="py-16 text-center text-muted-foreground">
              No campaigns in this category yet.
            </p>
          </Reveal>
        )}
      </section>
    </div>
  );
}
