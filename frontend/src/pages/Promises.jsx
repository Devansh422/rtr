import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHero, Section, SectionHeading, EmptyState, Pill, StatTile } from "@/components/platform/Primitives";
import { getPromises, getStates } from "@/lib/platformApi";

const ALL = "__all__";

/*
 * Promise Tracker.
 *
 * The tally is reported as a fraction of ASSESSED promises rather than of all
 * promises, matching the API. Including "cannot be assessed yet" in the denominator
 * would quietly deflate every representative's record, which is a thumb on the scale
 * dressed up as arithmetic.
 */
export default function Promises() {
  const [data, setData] = useState({ items: [], total: 0, tally: null, statuses: [] });
  const [states, setStates] = useState([]);
  const [filters, setFilters] = useState({ state: ALL, status: ALL });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStates().then(setStates);
  }, []);

  useEffect(() => {
    setLoading(true);
    getPromises({
      state: filters.state === ALL ? undefined : filters.state,
      status: filters.status === ALL ? undefined : filters.status,
      limit: 100,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  const counts = data.tally?.counts ?? {};

  return (
    <div data-testid="promises-page">
      <PageHero
        eyebrow="Promise Tracker"
        lines={["What was promised.", "What happened."]}
        lede="Every entry cites evidence that the promise was made, and separate evidence for what became of it. Marking a promise undelivered needs a primary public record, not a news report of someone else's assessment."
      />

      <Section>
        {data.tally?.total ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatTile label="Promises tracked" value={data.tally.total} />
            <StatTile label="Fulfilled" value={counts.fulfilled ?? 0} tone="primary" />
            <StatTile label="Partially" value={counts.partially_fulfilled ?? 0} />
            <StatTile label="Not delivered" value={counts.broken ?? 0} />
            <StatTile
              label="Not yet assessable"
              value={counts.not_assessable ?? 0}
              sub="Excluded from percentages"
            />
          </div>
        ) : null}

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:w-2/3">
          <Select value={filters.state} onValueChange={(v) => setFilters((p) => ({ ...p, state: v }))}>
            <SelectTrigger aria-label="Filter promises by state">
              <SelectValue placeholder="All states" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All states</SelectItem>
              {states.map((state) => (
                <SelectItem key={state.code} value={state.code}>
                  {state.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.status} onValueChange={(v) => setFilters((p) => ({ ...p, status: v }))}>
            <SelectTrigger aria-label="Filter promises by status">
              <SelectValue placeholder="Any status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Any status</SelectItem>
              {data.statuses.map((status) => (
                <SelectItem key={status.key} value={status.key}>
                  {status.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">Loading...</p>
          ) : data.items.length === 0 ? (
            <EmptyState
              title="No promises tracked for this filter yet"
              body="Promises are logged from manifestos, House assurances and public commitments, each with a source. The tracker starts with the pilot states."
            />
          ) : (
            <StaggerGroup className="grid gap-3">
              {data.items.map((promise) => (
                <StaggerItem key={promise.id}>
                  <Link
                    to={promise.url}
                    className="flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-card p-5 hover:border-primary/40"
                    data-testid={`promise-${promise.slug}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-heading text-lead font-semibold tracking-tight">
                        {promise.title}
                      </p>
                      <p className="mt-1 text-meta text-foreground/60">
                        {[
                          promise.madeContext,
                          promise.party,
                          promise.state,
                          promise.madeOn ? new Date(promise.madeOn).toLocaleDateString() : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    <Pill
                      tone={
                        promise.status === "fulfilled"
                          ? "primary"
                          : promise.status === "broken"
                            ? "default"
                            : "muted"
                      }
                    >
                      {promise.statusLabel}
                    </Pill>
                  </Link>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>

      <Section muted>
        <SectionHeading
          eyebrow="How a status is decided"
          title="Why there are seven statuses and not two"
          lede="A tracker with only 'kept' and 'broken' forces every ambiguous case into a verdict it cannot support. Most real promises are partially delivered, stalled in a department, or genuinely too early to judge — and saying so is more useful than picking a side."
        />
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.statuses.map((status) => (
            <div key={status.key} className="rounded border border-border bg-card p-4">
              <p className="font-heading text-body font-semibold tracking-tight">{status.label}</p>
              <p className="mt-1 text-meta text-foreground/60">{counts[status.key] ?? 0} tracked</p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
