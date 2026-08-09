import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LinkButton from "@/components/LinkButton";
import { PageHero, Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { getConstituencies, getMyRepresentatives, getStates } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";

/*
 * "Who represents me".
 *
 * The page reports what is MISSING as loudly as what is present: a state page showing
 * two of forty MPs looks complete and is not. The API returns expected seat counts
 * next to published counts precisely so this can be honest.
 */
export default function MyRepresentatives() {
  const { t } = useLocale();
  const [states, setStates] = useState([]);
  const [constituencies, setConstituencies] = useState([]);
  const [stateCode, setStateCode] = useState("");
  const [constituency, setConstituency] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    getStates().then(setStates);
  }, []);

  useEffect(() => {
    if (!stateCode) return;
    setConstituency("");
    getConstituencies({ state: stateCode }).then(setConstituencies);
    getMyRepresentatives(stateCode).then(setResult).catch(() => setResult(null));
  }, [stateCode]);

  useEffect(() => {
    if (!stateCode || !constituency) return;
    getMyRepresentatives(stateCode, constituency).then(setResult).catch(() => setResult(null));
  }, [stateCode, constituency]);

  return (
    <div data-testid="my-representatives-page">
      <PageHero
        eyebrow="Who represents me"
        lines={["Find the people", "who hold your", "seats."]}
        lede="Pick your state, and your constituency if you know it. Where a profile has not been researched yet, this page says so rather than showing you a shorter list and letting you assume it is complete."
      >
        <div className="grid max-w-2xl gap-3 sm:grid-cols-2">
          <Select value={stateCode} onValueChange={setStateCode}>
            <SelectTrigger aria-label="Choose your state" data-testid="choose-state">
              <SelectValue placeholder="Choose your state" />
            </SelectTrigger>
            <SelectContent>
              {states.map((state) => (
                <SelectItem key={state.code} value={state.code}>
                  {state.name}
                  {state.isPilot ? " (pilot)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={constituency} onValueChange={setConstituency} disabled={!constituencies.length}>
            <SelectTrigger aria-label="Choose your constituency">
              <SelectValue
                placeholder={
                  constituencies.length ? "Choose your constituency" : "No constituencies recorded yet"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {constituencies.map((seat) => (
                <SelectItem key={seat.code} value={seat.code}>
                  {seat.name} ({seat.house === "lok_sabha" ? "LS" : "AC"})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </PageHero>

      <Section>
        {!result ? (
          <p className="text-body text-foreground/60">
            Choose a state above to see who holds its seats.
          </p>
        ) : (
          <div className="space-y-10">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-heading text-title-3 font-semibold tracking-tight">
                {result.state.name}
              </h2>
              {result.dataComplete ? (
                <Pill tone="primary">Pilot state — data being built end to end</Pill>
              ) : (
                <Pill tone="muted">Data still being researched</Pill>
              )}
            </div>

            {result.helpText ? (
              <p className="max-w-3xl text-body text-foreground/70">{result.helpText}</p>
            ) : null}

            {result.houses.map((house) => (
              <div key={house.key}>
                <div className="flex flex-wrap items-baseline gap-3">
                  <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                    {house.label}
                  </h3>
                  <span className="text-meta text-foreground/60">
                    {house.published} profile{house.published === 1 ? "" : "s"} published
                    {house.expected ? ` of ${house.expected} seats` : ""}
                  </span>
                </div>

                {house.items.length ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {house.items.map((rep) => (
                      <Link
                        key={rep.id}
                        to={rep.url}
                        className="rounded border border-border bg-card p-5 hover:border-primary/40"
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
                ) : (
                  <p className="mt-3 text-body text-foreground/60">
                    No profiles published for this house yet.
                  </p>
                )}
              </div>
            ))}

            <EmptyState
              title="Missing your representative?"
              body="Profiles are added one at a time, and every figure has to be found in a public record and fact-checked before it goes live. Researching one is a real volunteer task with verified hours attached."
              action={
                <div className="flex flex-wrap justify-center gap-3">
                  <LinkButton to="/volunteer" variant="outline">
                    {t("reps.helpBuild")}
                  </LinkButton>
                  <LinkButton to="/representatives" variant="ghost">
                    Browse everything published
                  </LinkButton>
                </div>
              }
            />
          </div>
        )}
      </Section>
    </div>
  );
}
