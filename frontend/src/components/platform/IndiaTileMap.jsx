import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

/*
 * India as a tile grid, coloured by campaign stage.
 *
 * WHY A TILE GRID AND NOT A GEOGRAPHIC MAP. §5 of IMPLEMENTATION_PLAN.md picks
 * Leaflet/OpenStreetMap or react-simple-maps with an India TopoJSON. Both are the
 * right long-term answer and neither is used here, for three reasons:
 *
 * 1. India's borders are politically contested, and shipping an inaccurate or
 *    incomplete boundary file is a real problem for a platform whose credibility is
 *    its entire product. A TopoJSON has to be chosen deliberately, from a source
 *    whose depiction the project is willing to stand behind -- not picked up
 *    incidentally while building a dashboard.
 * 2. A choropleth of 36 regions at wildly different sizes actively misleads: Goa
 *    and Rajasthan get equal weight in the argument and hugely unequal weight on
 *    screen. Equal tiles give every state the same visual claim, which is the
 *    correct rhetoric for "every state legislature can act on this".
 * 3. Zero dependencies, zero tiles fetched, zero API key, keyboard-navigable, and
 *    it reads correctly at 320px -- where a Leaflet canvas needs its own responsive
 *    handling.
 *
 * Tile grid maps are an established form for exactly this trade-off. The upgrade
 * path is intact: this component's only inputs are the state list and a click
 * handler, so a geographic renderer can replace it without touching a caller.
 *
 * Positions are approximate relative geography, not projections. The `title` and
 * visible label carry the real identity; the grid is orientation, not measurement.
 */

// { code: [row, column] } on an 9 x 9 grid, north-west at the top left.
const GRID = {
  JK: [1, 3], LA: [1, 4],
  CH: [2, 2], PB: [2, 3], HP: [2, 4], UT: [2, 5],
  HR: [3, 3], DL: [3, 4], UP: [3, 5], SK: [3, 7], AR: [3, 9],
  RJ: [4, 2], MP: [4, 4], BR: [4, 6], WB: [4, 7], AS: [4, 8], NL: [4, 9],
  GJ: [5, 1], DH: [5, 2], MH: [5, 3], CT: [5, 5], JH: [5, 6], ML: [5, 8], MN: [5, 9],
  GA: [6, 2], TG: [6, 4], OR: [6, 6], TR: [6, 8], MZ: [6, 9],
  KA: [7, 3], AP: [7, 5],
  KL: [8, 3], TN: [8, 4], PY: [8, 5],
  LD: [9, 1], AN: [9, 7],
};

/*
 * Stage colours. A single hue with increasing saturation rather than a red-to-green
 * scale, for two reasons: a red state would read as a judgement on that state (§1),
 * and a sequential ramp is what a reader should see for a sequential variable. The
 * ramp is also distinguishable in greyscale and for the common colour-vision
 * deficiencies, since intensity carries the signal rather than hue.
 */
const STAGE_TONES = [
  "bg-muted text-foreground/50 border-border",                    // 0 no demand
  "bg-primary/10 text-primary border-primary/20",                 // 1 awareness
  "bg-primary/20 text-primary border-primary/30",                 // 2 petition submitted
  "bg-primary/35 text-primary border-primary/40",                 // 3 bill introduced
  "bg-primary/50 text-primary-foreground border-primary/50",      // 4 committee
  "bg-primary/65 text-primary-foreground border-primary/60",      // 5 passed assembly
  "bg-primary/80 text-primary-foreground border-primary/70",      // 6 passed parliament
  "bg-primary text-primary-foreground border-primary",            // 7 act enforced
];

/*
 * Intensity mode. Given a count per state, the same primary ramp carries "how
 * many", as a proportion of the leading state rather than of an absolute scale:
 * on the day a petition opens the leader has four signatures, and a ramp pinned
 * to 100,000 would render the entire country as one flat empty grid.
 *
 * Proportional-to-leader has its own honesty problem -- it makes an early map
 * look busier than the campaign is -- so the legend states the leader's number
 * outright rather than showing an unlabelled gradient.
 */
const INTENSITY_STEPS = [
  [0.66, 7],
  [0.33, 6],
  [0.15, 5],
  [0.05, 4],
  [0, 2],
];

function intensityTone(count, max) {
  if (!count || !max) return STAGE_TONES[0];
  const ratio = count / max;
  const step = INTENSITY_STEPS.find(([threshold]) => ratio > threshold);
  return STAGE_TONES[step ? step[1] : 2];
}

export default function IndiaTileMap({
  states,
  stages = [],
  // Optional { CODE: number }. When present the tiles carry this quantity
  // instead of the campaign stage -- used by the petition's state-wise sections.
  values,
  valueLabel = "signatures",
  // Optional. When given, tiles become buttons that select a state in place
  // rather than links that navigate away from the page.
  onSelect,
  selectedCode,
  className,
}) {
  if (!states?.length) return null;

  const byCode = Object.fromEntries(states.map((s) => [s.code, s]));
  const rows = 9;
  const columns = 9;
  const showValues = Boolean(values);
  const maxValue = showValues ? Math.max(0, ...Object.values(values)) : 0;

  return (
    <div className={className} data-testid="india-tile-map">
      <div
        className="grid gap-1.5"
        style={{
          gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
          gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
        }}
        role="group"
        aria-label={
          showValues
            ? `States and union territories by ${valueLabel}`
            : "States and union territories by campaign stage"
        }
      >
        {Object.entries(GRID).map(([code, [row, column]]) => {
          const state = byCode[code];
          if (!state) return null;
          const stageIndex = state.campaign?.stageIndex ?? 0;
          const value = showValues ? (values[code] ?? 0) : null;
          const description = showValues
            ? `${value.toLocaleString("en-IN")} ${valueLabel}`
            : (state.campaign?.stageLabel ?? "No demand yet");

          const tileClassName = cn(
            "flex aspect-square flex-col items-center justify-center rounded border p-1 transition-transform",
            "hover:scale-110 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            showValues
              ? intensityTone(value, maxValue)
              : (STAGE_TONES[stageIndex] ?? STAGE_TONES[0]),
            // The pilot states are where the pattern is being proven, so they
            // are marked rather than left to be inferred from their stage.
            state.isPilot && "ring-2 ring-secondary ring-offset-1 ring-offset-background",
            selectedCode === code && "ring-2 ring-primary ring-offset-1 ring-offset-background"
          );
          const label = `${state.name}, ${description.toLowerCase()}`;
          const content = <span className="font-heading text-meta font-bold leading-none">{code}</span>;

          if (onSelect) {
            return (
              <button
                key={code}
                type="button"
                onClick={() => onSelect(code)}
                style={{ gridRow: row, gridColumn: column }}
                title={`${state.name} - ${description}`}
                aria-label={label}
                aria-pressed={selectedCode === code}
                className={tileClassName}
                data-testid={`map-tile-${code}`}
              >
                {content}
              </button>
            );
          }

          return (
            <Link
              key={code}
              to={`/states/${state.slug}`}
              style={{ gridRow: row, gridColumn: column }}
              title={`${state.name} - ${description}`}
              aria-label={label}
              className={tileClassName}
              data-testid={`map-tile-${code}`}
            >
              {content}
            </Link>
          );
        })}
      </div>

      {/* Legend. A map whose colours are unexplained is decoration. */}
      {showValues ? (
        <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-label font-bold uppercase text-muted-foreground">{valueLabel}</span>
          <span className="inline-flex items-center gap-1.5 text-meta">
            <span className={cn("h-3 w-3 rounded border", STAGE_TONES[0])} aria-hidden="true" />
            None yet
          </span>
          {[2, 4, 5, 6, 7].map((tone) => (
            <span
              key={tone}
              className={cn("h-3 w-3 rounded border", STAGE_TONES[tone])}
              aria-hidden="true"
            />
          ))}
          <span className="text-meta text-foreground/60">
            Shaded against the leading state
            {maxValue ? ` (${maxValue.toLocaleString("en-IN")} ${valueLabel})` : ""}, not against a
            national target.
          </span>
        </div>
      ) : stages.length ? (
        <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-label font-bold uppercase text-muted-foreground">Stage</span>
          {stages.map((stage, index) => (
            <span key={stage.key} className="inline-flex items-center gap-1.5 text-meta">
              <span
                className={cn("h-3 w-3 rounded border", STAGE_TONES[index] ?? STAGE_TONES[0])}
                aria-hidden="true"
              />
              {stage.label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 text-meta">
            <span
              className="h-3 w-3 rounded border border-border ring-2 ring-secondary"
              aria-hidden="true"
            />
            Pilot state
          </span>
        </div>
      ) : null}

      <p className="mt-4 text-meta text-foreground/60">
        Equal tiles, positioned approximately. Every state legislature can legislate on
        elections to its own House under Article 328, so each one gets the same weight here
        regardless of its size.
      </p>
    </div>
  );
}
