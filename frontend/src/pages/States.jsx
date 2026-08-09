import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { PageHero, Section, SectionHeading, StatTile, Pill } from "@/components/platform/Primitives";
import IndiaTileMap from "@/components/platform/IndiaTileMap";
import { getCampaignStages, getStates } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";

export default function States() {
  const { t } = useLocale();
  const [states, setStates] = useState([]);
  const [stages, setStages] = useState([]);

  useEffect(() => {
    getStates().then(setStates);
    getCampaignStages().then(setStages);
  }, []);

  const summary = useMemo(() => {
    const byStage = new Map();
    states.forEach((state) => {
      const key = state.campaign?.stage ?? "no_demand";
      byStage.set(key, (byStage.get(key) ?? 0) + 1);
    });
    return {
      total: states.length,
      moving: states.filter((s) => (s.campaign?.stageIndex ?? 0) > 0).length,
      withAssembly: states.filter((s) => s.hasLegislature).length,
      byStage,
    };
  }, [states]);

  return (
    <div data-testid="states-page">
      <PageHero
        eyebrow="Campaign dashboard"
        lines={["Where the campaign", "stands, state", "by state."]}
        lede={t("states.lede")}
      />

      <Section testId="state-map">
        <div className="grid gap-12 lg:grid-cols-[1fr_360px]">
          <div>
            <IndiaTileMap states={states} stages={stages} />
          </div>

          <div className="space-y-4">
            <StatTile
              label="States and union territories"
              value={summary.total}
              sub={`${summary.withAssembly} have a legislative assembly`}
            />
            <StatTile
              label="Past the starting line"
              value={summary.moving}
              sub="Where a demand has been raised or further"
              tone="primary"
            />
            <div className="rounded border border-border bg-card p-5">
              <p className="text-label font-bold uppercase text-muted-foreground">
                Why state by state
              </p>
              <p className="mt-2 text-meta leading-relaxed text-foreground/70">
                Under{" "}
                <Link to="/constitution/328" className="text-primary underline-offset-4 hover:underline">
                  Article 328
                </Link>
                , a state legislature can make law on elections to its own House where Parliament
                has not already done so. That means a single assembly can legislate recall for its
                own MLAs without waiting for a constitutional amendment &mdash; which is why this is
                tracked per state rather than as one national number.
              </p>
            </div>
          </div>
        </div>
      </Section>

      <Section muted testId="state-list">
        <SectionHeading
          eyebrow="Every state"
          title="Full status list"
          lede="Sorted by how far the campaign has progressed. Each state's page shows the evidence behind its stage."
        />

        <StaggerGroup className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...states]
            .sort(
              (a, b) =>
                (b.campaign?.stageIndex ?? 0) - (a.campaign?.stageIndex ?? 0) ||
                Number(b.isPilot) - Number(a.isPilot) ||
                a.name.localeCompare(b.name)
            )
            .map((state) => (
              <StaggerItem key={state.code}>
                <Link
                  to={`/states/${state.slug}`}
                  className="group flex h-full flex-col rounded border border-border bg-card p-5 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40"
                  data-testid={`state-card-${state.code}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-heading text-lead font-semibold tracking-tight group-hover:text-primary">
                        {state.name}
                      </p>
                      <p className="mt-0.5 text-meta text-foreground/60" lang="hi">
                        {state.nameHi}
                      </p>
                    </div>
                    <span className="font-heading text-meta font-bold text-muted-foreground">
                      {state.code}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {state.isPilot ? <Pill tone="secondary">{t("states.pilot")}</Pill> : null}
                    {!state.hasLegislature ? (
                      <Pill tone="muted">{t("states.noLegislature")}</Pill>
                    ) : null}
                    {state.isUnionTerritory ? <Pill tone="muted">UT</Pill> : null}
                  </div>

                  <div className="mt-auto pt-5">
                    <p className="text-label font-bold uppercase text-muted-foreground">
                      {t("states.stage")}
                    </p>
                    <p className="mt-1 text-body font-medium">{state.campaign?.stageLabel}</p>
                    {/* Progress rail: stageIndex out of totalStages, so the bar and
                        the label can never disagree. */}
                    <div className="mt-2 h-1.5 overflow-hidden rounded bg-muted" aria-hidden="true">
                      <div
                        className="h-full rounded bg-primary transition-all"
                        style={{
                          width: `${
                            (((state.campaign?.stageIndex ?? 0) + 1) /
                              (state.campaign?.totalStages ?? 8)) *
                            100
                          }%`,
                        }}
                      />
                    </div>
                    <p className="mt-1.5 text-meta text-foreground/50">
                      Stage {(state.campaign?.stageIndex ?? 0) + 1} {t("common.of")}{" "}
                      {state.campaign?.totalStages ?? 8}
                    </p>
                  </div>
                </Link>
              </StaggerItem>
            ))}
        </StaggerGroup>
      </Section>

      <Section>
        <Reveal>
          <div className="rounded border border-border bg-card p-8">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              Every stage change is dated and sourced
            </h2>
            <p className="mt-3 max-w-3xl text-body text-foreground/70">
              Moving a state along this pipeline is a factual claim about a legislature, so the
              platform will not accept one without a link to a public record &mdash; an assembly
              bulletin, a Gazette notification, a committee report. Each state page carries the full
              history of its own stage changes, with the evidence behind each one.
            </p>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
