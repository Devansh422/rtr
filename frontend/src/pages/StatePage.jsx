import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Reveal } from "@/components/motion/Reveal";
import LinkButton from "@/components/LinkButton";
import {
  Section,
  SectionHeading,
  StatTile,
  Pill,
  HistoryList,
  EmptyState,
  SourceLink,
} from "@/components/platform/Primitives";
import CampaignPipeline from "@/components/platform/CampaignPipeline";
import CorrectionDialog from "@/components/platform/CorrectionDialog";
import {
  getCampaignStages,
  getEvents,
  getMyRepresentatives,
  getPetitions,
  getScorecard,
  getState,
  getStateHistory,
} from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, Calendar, FileSignature, Users } from "lucide-react";

export default function StatePage() {
  const { slug } = useParams();
  const { t } = useLocale();
  const [state, setState] = useState(null);
  const [stages, setStages] = useState([]);
  const [history, setHistory] = useState([]);
  const [reps, setReps] = useState(null);
  const [petitions, setPetitions] = useState([]);
  const [events, setEvents] = useState([]);
  const [scorecard, setScorecard] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    getCampaignStages().then(setStages);
    getState(slug)
      .then(async (data) => {
        setState(data);
        setStatus("ready");
        // Everything below is per-state and independent, so it is fetched in
        // parallel and each piece renders as it arrives.
        getStateHistory(slug).then(setHistory);
        getMyRepresentatives(data.code).then(setReps).catch(() => setReps(null));
        getPetitions({ state: data.code, limit: 6 }).then((r) => setPetitions(r.items));
        getEvents({ state: data.code, limit: 4 }).then(setEvents);
        getScorecard({ state: data.code }).then(setScorecard);
      })
      .catch(() => setStatus("missing"));
  }, [slug]);

  if (status === "loading") {
    return (
      <Section>
        <p className="text-body text-foreground/60">{t("common.loading")}</p>
      </Section>
    );
  }
  if (status === "missing") {
    return (
      <Section>
        <EmptyState
          title="No such state"
          body="Check the address, or browse the campaign dashboard."
          action={<LinkButton to="/states">All states</LinkButton>}
        />
      </Section>
    );
  }

  const stageIndex = state.campaign?.stageIndex ?? 0;

  return (
    <div data-testid={`state-page-${state.code}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          <Link
            to="/states"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.states")}
          </Link>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            {state.isPilot ? <Pill tone="secondary">{t("states.pilot")}</Pill> : null}
            {state.isUnionTerritory ? <Pill tone="muted">Union territory</Pill> : null}
            {!state.hasLegislature ? <Pill tone="muted">{t("states.noLegislature")}</Pill> : null}
          </div>

          <h1 className="mt-5 font-heading text-title-1 font-semibold leading-[1] tracking-tighter">
            {state.name}
          </h1>
          <p className="mt-2 text-lead text-foreground/60" lang="hi">
            {state.nameHi}
          </p>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Lok Sabha seats" value={state.seats?.lokSabha ?? 0} />
            <StatTile label="Rajya Sabha seats" value={state.seats?.rajyaSabha ?? 0} />
            <StatTile
              label="Assembly seats"
              value={state.hasLegislature ? state.seats?.assembly ?? 0 : "-"}
              sub={state.hasLegislature ? undefined : "No assembly"}
            />
            <StatTile
              label={t("states.stage")}
              value={`${stageIndex + 1}/${state.campaign?.totalStages ?? 8}`}
              sub={state.campaign?.stageLabel}
              tone="primary"
            />
          </div>

          {/* Seat counts are seeded scaffolding, not verified claims -- said here
              rather than buried, because the numbers are above this line. */}
          <p className="mt-4 max-w-2xl text-meta text-foreground/60">
            Seat counts are seeded reference figures pending fact-check against the Election
            Commission, and the delimitation exercise will change them.
          </p>
        </div>
      </section>

      {/* Campaign status, with its evidence. */}
      <Section muted testId="state-campaign">
        <div className="grid gap-12 lg:grid-cols-[380px_1fr]">
          <div>
            <SectionHeading eyebrow="Progress" title="The eight stages" />
            <div className="mt-8">
              <CampaignPipeline stages={stages} currentIndex={stageIndex} />
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded border border-border bg-card p-7">
              <p className="text-label font-bold uppercase text-secondary">Current status</p>
              <p className="mt-2 font-heading text-title-3 font-semibold tracking-tight">
                {state.campaign?.stageLabel}
              </p>
              {state.campaign?.note ? (
                <p className="mt-3 text-body leading-relaxed text-foreground/80">
                  {state.campaign.note}
                </p>
              ) : (
                <p className="mt-3 text-body text-foreground/60">
                  No demand has been formally raised in {state.name} yet. That is a starting point,
                  not a verdict &mdash; most states are here.
                </p>
              )}
              {state.campaign?.sourceUrl ? (
                <SourceLink
                  citation={{
                    url: state.campaign.sourceUrl,
                    title: "Evidence for this status",
                    sourceDate: state.campaign.updatedAt?.slice(0, 10),
                  }}
                  className="mt-4"
                />
              ) : null}
              <div className="mt-5">
                <CorrectionDialog entityType="state" entityId={state.code} fieldLabel="Campaign status" />
              </div>
            </div>

            {!state.hasLegislature ? (
              <div className="rounded border border-border bg-muted/40 p-6">
                <p className="font-heading text-lead font-semibold tracking-tight">
                  {state.name} has no legislative assembly
                </p>
                <p className="mt-2 text-body text-foreground/70">
                  So there is no House through which a state Right to Recall Bill could pass, and no
                  MLAs to profile. The case here runs through Parliament under{" "}
                  <Link to="/constitution/327" className="text-primary underline-offset-4 hover:underline">
                    Article 327
                  </Link>{" "}
                  instead.
                </p>
              </div>
            ) : null}

            <div className="rounded border border-border bg-card p-6">
              <p className="text-label font-bold uppercase text-muted-foreground">
                {t("common.history")}
              </p>
              <div className="mt-4">
                <HistoryList
                  entries={history}
                  emptyText="This state's status has not changed since the platform launched."
                />
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* Representatives, with an honest completeness signal. */}
      <Section testId="state-representatives">
        <SectionHeading
          eyebrow="Accountability"
          title="Who represents this state"
          action={<LinkButton to={`/representatives?state=${state.code}`} variant="outline" size="sm">
            {t("common.viewAll")}
          </LinkButton>}
        />
        {reps?.houses?.some((house) => house.items.length) ? (
          <div className="mt-8 space-y-8">
            {reps.houses
              .filter((house) => house.items.length)
              .map((house) => (
                <div key={house.key}>
                  <div className="flex flex-wrap items-baseline gap-3">
                    <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                      {house.label}
                    </h3>
                    <span className="text-meta text-foreground/60">
                      {house.published} published
                      {house.expected ? ` of ${house.expected} seats` : ""}
                    </span>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {house.items.map((rep) => (
                      <Link
                        key={rep.id}
                        to={rep.url}
                        className="rounded border border-border bg-card p-4 transition-colors hover:border-primary/40"
                      >
                        <p className="font-heading text-body font-semibold tracking-tight">
                          {rep.name}
                        </p>
                        <p className="mt-1 text-meta text-foreground/60">
                          {rep.constituency?.name ?? rep.houseLabel}
                          {rep.party ? ` · ${rep.party.code}` : ""}
                        </p>
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        ) : (
          <div className="mt-8">
            <EmptyState
              title={`No profiles published for ${state.name} yet`}
              body={
                reps?.helpText ??
                "Profiles are added constituency by constituency, each one sourced from public records before it is published."
              }
              action={
                <LinkButton to="/volunteer" variant="outline">
                  <Users className="h-4 w-4" aria-hidden="true" />
                  {t("reps.helpBuild")}
                </LinkButton>
              }
            />
          </div>
        )}
      </Section>

      {/* Local activity. */}
      <Section muted>
        <div className="grid gap-10 lg:grid-cols-3">
          <div>
            <h3 className="flex items-center gap-2 font-heading text-title-4 font-semibold tracking-tight">
              <FileSignature className="h-5 w-5 text-secondary" aria-hidden="true" />
              Petitions
            </h3>
            <div className="mt-4 space-y-3">
              {petitions.length ? (
                petitions.map((petition) => (
                  <Link
                    key={petition.id}
                    to={petition.url}
                    className="block rounded border border-border bg-card p-4 hover:border-primary/40"
                  >
                    <p className="font-heading text-body font-semibold tracking-tight">
                      {petition.title}
                    </p>
                    <p className="mt-1 text-meta text-foreground/60">
                      {petition.signatureCount} {t("petitions.signatures")}
                    </p>
                  </Link>
                ))
              ) : (
                <p className="text-body text-foreground/60">
                  No petitions for {state.name} yet.{" "}
                  <Link to="/petitions" className="text-primary underline-offset-4 hover:underline">
                    Start one
                  </Link>
                  .
                </p>
              )}
            </div>
          </div>

          <div>
            <h3 className="flex items-center gap-2 font-heading text-title-4 font-semibold tracking-tight">
              <Calendar className="h-5 w-5 text-secondary" aria-hidden="true" />
              {t("events.title")}
            </h3>
            <div className="mt-4 space-y-3">
              {events.length ? (
                events.map((event) => (
                  <Link
                    key={event.id}
                    to={event.url}
                    className="block rounded border border-border bg-card p-4 hover:border-primary/40"
                  >
                    <p className="font-heading text-body font-semibold tracking-tight">
                      {event.title}
                    </p>
                    <p className="mt-1 text-meta text-foreground/60">
                      {new Date(event.startsAt).toLocaleDateString()} &middot;{" "}
                      {event.isOnline ? "Online" : event.venue}
                    </p>
                  </Link>
                ))
              ) : (
                <p className="text-body text-foreground/60">Nothing scheduled here yet.</p>
              )}
            </div>
          </div>

          <div>
            <h3 className="font-heading text-title-4 font-semibold tracking-tight">
              {t("reports.scorecard")}
            </h3>
            <div className="mt-4">
              {scorecard?.services?.length ? (
                <div className="space-y-2">
                  {scorecard.services.slice(0, 6).map((service) => (
                    <div
                      key={service.service}
                      className="flex items-center justify-between rounded border border-border bg-card px-4 py-2.5"
                    >
                      <span className="text-body">{service.label}</span>
                      <span className="text-meta text-foreground/60">
                        {service.averageRating != null
                          ? `${service.averageRating}/5`
                          : `${service.reportCount} report${service.reportCount === 1 ? "" : "s"}`}
                      </span>
                    </div>
                  ))}
                  <p className="pt-1 text-meta text-foreground/60">{scorecard.note}</p>
                </div>
              ) : (
                <p className="text-body text-foreground/60">
                  No citizen reports for {state.name} yet.{" "}
                  <Link to="/reports" className="text-primary underline-offset-4 hover:underline">
                    File the first one
                  </Link>
                  .
                </p>
              )}
            </div>
          </div>
        </div>
      </Section>

      <Section>
        <Reveal>
          <div className="rounded border border-primary/30 bg-primary/5 p-8 text-center">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              Write to your representative in {state.name}
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-body text-foreground/70">
              A written representation on the record is treated differently from a phone call. The
              generator produces a letter asking them to state their position on recall &mdash; the
              same letter, to every party.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <LinkButton to="/tools/recall-demand">Generate the letter</LinkButton>
              <LinkButton to="/tools" variant="outline">
                All civic tools
              </LinkButton>
            </div>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
