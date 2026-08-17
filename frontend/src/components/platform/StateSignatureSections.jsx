import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { Pill, StatTile } from "@/components/platform/Primitives";
import IndiaTileMap from "@/components/platform/IndiaTileMap";
import DynamicButton from "@/components/DynamicButton";
import { cn } from "@/lib/utils";
import { ArrowRight, MapPin, Trophy, X } from "lucide-react";

/*
 * The petition, state by state.
 *
 * WHY THE PAGE IS BUILT THIS WAY. A national counter answers "how many", which is
 * the least useful thing a visitor can know about a campaign they are deciding
 * whether to join. "Forty-one people in your state have signed, and the
 * neighbouring one has six hundred" is a fact somebody can act on, and it is also
 * the truthful shape of this campaign: under Article 328 a single assembly can
 * legislate recall for its own members, so the unit that matters is the state.
 *
 * Three rules the layout follows, each of them a correctness rule rather than a
 * taste one:
 *
 * 1. EVERY state and union territory appears, including the ones on zero. A list
 *    of only the states with signatures reads as a list of the states that exist,
 *    and quietly writes the smaller ones out of a national campaign.
 * 2. The grouping is the statutory zonal councils (see core/geography.py). Any
 *    home-made grouping of Indian states carries an argument inside it; this one
 *    is a citable fact about how the Union already organises consultation.
 * 3. Percentages are of the signatures that carry a state, and the count that do
 *    not is shown next to them rather than folded away, so the numbers add up in
 *    public.
 */

function ShareBar({ share, className }) {
  return (
    <div className={cn("h-1.5 overflow-hidden rounded bg-muted", className)} aria-hidden="true">
      <div
        className="h-full rounded bg-primary transition-all"
        // Relative to the leading state rather than to the national total: at a
        // realistic spread every bar would otherwise be an invisible sliver.
        style={{ width: `${Math.min(100, share)}%` }}
      />
    </div>
  );
}

function StateRow({ row, leadCount, isSelected, onSelect }) {
  const relative = leadCount ? (row.count / leadCount) * 100 : 0;
  return (
    <div
      id={`state-signatures-${row.code}`}
      className={cn(
        "flex h-full flex-col rounded border bg-card p-4 transition-colors",
        isSelected ? "border-primary ring-1 ring-primary" : "border-border",
        row.count ? "" : "bg-card/50"
      )}
      data-testid={`state-signatures-${row.code}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => onSelect(row.code)}
            className="text-left font-heading text-body font-semibold leading-tight tracking-tight hover:text-primary"
          >
            {row.name}
          </button>
          <p className="mt-0.5 truncate text-meta text-foreground/55" lang="hi">
            {row.nameHi}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-heading text-lead font-semibold tracking-tight">
            {row.count.toLocaleString("en-IN")}
          </p>
          {row.rank ? (
            <p className="text-micro font-bold uppercase text-muted-foreground">#{row.rank}</p>
          ) : null}
        </div>
      </div>

      <ShareBar share={relative} className="mt-3" />
      <p className="mt-1.5 text-meta text-foreground/55">
        {row.count ? `${row.share}% of signatures` : "No signatures from here yet"}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Pill tone="muted">{row.campaignStageLabel}</Pill>
        {row.isPilot ? <Pill tone="secondary">Pilot</Pill> : null}
        {!row.hasLegislature ? <Pill tone="muted">No assembly</Pill> : null}
      </div>

      <Link
        to={row.url}
        className="mt-3 inline-flex items-center gap-1 text-meta text-primary underline-offset-4 hover:underline"
      >
        State page
        <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </Link>
    </div>
  );
}

export default function StateSignatureSections({
  breakdown,
  selectedCode,
  onSelectState,
  onSignForState,
  className,
}) {
  const leader = breakdown?.states?.find((row) => row.count > 0) ?? null;
  const focus = useMemo(
    () => breakdown?.states?.find((row) => row.code === selectedCode) ?? null,
    [breakdown, selectedCode]
  );
  const values = useMemo(
    () => Object.fromEntries((breakdown?.states ?? []).map((row) => [row.code, row.count])),
    [breakdown]
  );
  const mapStates = useMemo(
    () =>
      (breakdown?.states ?? []).map((row) => ({
        code: row.code,
        slug: row.slug,
        name: row.name,
        isPilot: row.isPilot,
      })),
    [breakdown]
  );

  if (!breakdown) return null;

  const leadCount = leader?.count ?? 0;
  const topStates = breakdown.states.filter((row) => row.count > 0).slice(0, 5);

  return (
    <div className={className} data-testid="state-signature-sections">
      <StaggerGroup className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StaggerItem>
          <StatTile
            label="Signatures"
            value={breakdown.totalSignatures.toLocaleString("en-IN")}
            sub={`${breakdown.recorded.toLocaleString("en-IN")} say where they are from`}
            tone="primary"
          />
        </StaggerItem>
        <StaggerItem>
          <StatTile
            label="States represented"
            value={`${breakdown.statesWithSignatures} of ${breakdown.totalStates}`}
            sub="States and union territories with at least one signature"
          />
        </StaggerItem>
        <StaggerItem>
          <StatTile
            label="Leading state"
            value={leader ? leader.name : "None yet"}
            sub={leader ? `${leader.count.toLocaleString("en-IN")} signatures` : "Be the first"}
          />
        </StaggerItem>
        <StaggerItem>
          <StatTile
            label="Not stated"
            value={breakdown.unspecified.toLocaleString("en-IN")}
            sub="Counted in the total, absent from the map"
          />
        </StaggerItem>
      </StaggerGroup>

      <div className="mt-12 grid gap-10 lg:grid-cols-[1fr_360px]">
        <Reveal>
          <IndiaTileMap
            states={mapStates}
            values={values}
            valueLabel="signatures"
            selectedCode={selectedCode}
            onSelect={onSelectState}
          />
        </Reveal>

        <div className="space-y-4">
          {/* The focused state. Set by tapping the map, by picking a state in the
              signing form, or by the state on the signed-in member's profile. */}
          {focus ? (
            <div className="rounded border border-primary/40 bg-card p-5" data-testid="focused-state">
              <div className="flex items-start justify-between gap-3">
                <p className="flex items-center gap-1.5 text-label font-bold uppercase text-secondary">
                  <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                  {focus.rank ? `Rank #${focus.rank}` : "No signatures yet"}
                </p>
                <button
                  type="button"
                  onClick={() => onSelectState(null)}
                  className="text-muted-foreground hover:text-foreground"
                  aria-label="Clear the selected state"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <p className="mt-2 font-heading text-title-3 font-semibold tracking-tight">
                {focus.name}
              </p>
              <p className="mt-1 text-meta text-foreground/60" lang="hi">
                {focus.nameHi}
              </p>
              <p className="mt-4 font-heading text-title-2 font-semibold tracking-tight text-primary">
                {focus.count.toLocaleString("en-IN")}
              </p>
              <p className="text-meta text-foreground/60">
                signatures &middot; {focus.share}% of those that state a place
              </p>
              <ShareBar share={leadCount ? (focus.count / leadCount) * 100 : 0} className="mt-3" />
              <p className="mt-4 text-meta text-foreground/70">
                Campaign stage: <strong className="font-semibold">{focus.campaignStageLabel}</strong>
                {focus.hasLegislature
                  ? `. Its assembly has ${focus.assemblySeats} seats and can legislate recall for its own members.`
                  : ". It has no legislative assembly, so this demand runs through Parliament."}
              </p>
              {onSignForState ? (
                <DynamicButton
                  className="mt-4 w-full"
                  onClick={() => onSignForState(focus.code)}
                  data-testid="sign-for-state"
                >
                  Sign for {focus.name}
                </DynamicButton>
              ) : null}
              <Link
                to={focus.url}
                className="mt-3 inline-flex items-center gap-1 text-meta text-primary underline-offset-4 hover:underline"
              >
                Everything about {focus.name}
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          ) : (
            <div className="rounded border border-dashed border-border bg-card/50 p-5">
              <p className="text-label font-bold uppercase text-muted-foreground">Your state</p>
              <p className="mt-2 text-meta leading-relaxed text-foreground/70">
                Tap any tile to see how that state stands. If you sign, your state is recorded from
                the form &mdash; that is the only reason the map asks for it.
              </p>
            </div>
          )}

          {topStates.length ? (
            <div className="rounded border border-border bg-card p-5">
              <p className="flex items-center gap-1.5 text-label font-bold uppercase text-muted-foreground">
                <Trophy className="h-3.5 w-3.5" aria-hidden="true" />
                Leading states
              </p>
              <ol className="mt-3 space-y-3">
                {topStates.map((row) => (
                  <li key={row.code}>
                    <button
                      type="button"
                      onClick={() => onSelectState(row.code)}
                      className="w-full text-left"
                    >
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="truncate text-body font-medium">
                          {row.rank}. {row.name}
                        </span>
                        <span className="shrink-0 font-heading text-body font-semibold tabular-nums">
                          {row.count.toLocaleString("en-IN")}
                        </span>
                      </span>
                      <ShareBar
                        share={leadCount ? (row.count / leadCount) * 100 : 0}
                        className="mt-1.5"
                      />
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </div>
      </div>

      {/* One section per zonal council. */}
      <div className="mt-16 space-y-14">
        {breakdown.zones.map((zone) => (
          <section key={zone.key} data-testid={`zone-${zone.key}`}>
            <Reveal>
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4">
                <div>
                  <p className="text-label font-bold uppercase text-secondary">
                    {zone.label} zone
                  </p>
                  <h3 className="mt-2 font-heading text-title-3 font-semibold tracking-tight">
                    <span lang="hi">{zone.labelHi}</span> &middot; {zone.states.length} states and
                    union territories
                  </h3>
                </div>
                <div className="text-right">
                  <p className="font-heading text-title-3 font-semibold tracking-tight">
                    {zone.count.toLocaleString("en-IN")}
                  </p>
                  <p className="text-meta text-foreground/60">{zone.share}% of signatures</p>
                </div>
              </div>
            </Reveal>

            <StaggerGroup className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {zone.states.map((row) => (
                <StaggerItem key={row.code}>
                  <StateRow
                    row={row}
                    leadCount={leadCount}
                    isSelected={selectedCode === row.code}
                    onSelect={onSelectState}
                  />
                </StaggerItem>
              ))}
            </StaggerGroup>
          </section>
        ))}
      </div>

      <p className="mt-12 max-w-3xl text-meta leading-relaxed text-foreground/60">
        {breakdown.note} States are grouped by the zonal councils constituted under the States
        Reorganisation Act 1956 and the North Eastern Council Act 1971 &mdash;{" "}
        <a
          href={breakdown.zoneSourceUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="text-primary underline-offset-4 hover:underline"
        >
          a published grouping
        </a>
        , rather than one invented for this page.
      </p>
    </div>
  );
}
