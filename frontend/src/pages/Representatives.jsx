import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem, Reveal } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import {
  PageHero,
  Section,
  SectionHeading,
  EmptyState,
  Pill,
  Disclaimer,
} from "@/components/platform/Primitives";
import { getClaimFields, getHouses, getParties, getRepresentatives, getStates } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { Search, Users } from "lucide-react";

const ALL = "__all__";

export default function Representatives() {
  const { t } = useLocale();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [states, setStates] = useState([]);
  const [houses, setHouses] = useState([]);
  const [parties, setParties] = useState([]);
  const [meta, setMeta] = useState({ fields: [], disclaimer: "" });
  const [loading, setLoading] = useState(true);

  const [filters, setFilters] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      q: "",
      state: params.get("state") ?? ALL,
      house: params.get("house") ?? ALL,
      party: ALL,
    };
  });

  useEffect(() => {
    getStates().then(setStates);
    getHouses().then(setHouses);
    getParties().then(setParties);
    getClaimFields().then(setMeta);
  }, []);

  useEffect(() => {
    setLoading(true);
    getRepresentatives({
      q: filters.q || undefined,
      state: filters.state === ALL ? undefined : filters.state,
      house: filters.house === ALL ? undefined : filters.house,
      party: filters.party === ALL ? undefined : filters.party,
      limit: 120,
    })
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
  }, [filters]);

  const set = (key) => (value) => setFilters((prev) => ({ ...prev, [key]: value }));

  return (
    <div data-testid="representatives-page">
      <PageHero
        eyebrow="Representative Database"
        lines={["Who represents you,", "and what they", "have done."]}
        lede={t("reps.lede")}
      >
        <LinkButton to="/my-representatives" size="lg">
          <Users className="h-5 w-5" aria-hidden="true" />
          {t("reps.findMine")}
        </LinkButton>
      </PageHero>

      <Section testId="representatives-filters">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={filters.q}
              onChange={(event) => set("q")(event.target.value)}
              placeholder="Search by name"
              className="pl-9"
              aria-label="Search representatives by name"
              data-testid="rep-search"
            />
          </div>

          <Select value={filters.state} onValueChange={set("state")}>
            <SelectTrigger aria-label="Filter by state" data-testid="rep-filter-state">
              <SelectValue placeholder="All states" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All states</SelectItem>
              {states.map((state) => (
                <SelectItem key={state.code} value={state.code}>
                  {state.name}
                  {state.isPilot ? " (pilot)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.house} onValueChange={set("house")}>
            <SelectTrigger aria-label="Filter by house" data-testid="rep-filter-house">
              <SelectValue placeholder="All houses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All houses</SelectItem>
              {houses.map((house) => (
                <SelectItem key={house.key} value={house.key}>
                  {house.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.party} onValueChange={set("party")}>
            <SelectTrigger aria-label="Filter by party" data-testid="rep-filter-party">
              <SelectValue placeholder="All parties" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All parties</SelectItem>
              {parties.map((party) => (
                <SelectItem key={party.code} value={party.code}>
                  {party.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">{t("common.loading")}</p>
          ) : items.length === 0 ? (
            <EmptyState
              title={t("reps.noProfiles")}
              body="The database is built constituency by constituency: every figure has to be found in a public record, entered with its citation, and fact-checked before the profile goes live. Delhi and Maharashtra are being built first."
              action={
                <div className="flex flex-wrap justify-center gap-3">
                  <LinkButton to="/volunteer" variant="outline">
                    {t("reps.helpBuild")}
                  </LinkButton>
                  <DynamicButton
                    variant="ghost"
                    onClick={() => setFilters({ q: "", state: ALL, house: ALL, party: ALL })}
                  >
                    {t("common.clearFilters")}
                  </DynamicButton>
                </div>
              }
            />
          ) : (
            <>
              <p className="text-meta text-foreground/60">
                {total} profile{total === 1 ? "" : "s"} published
              </p>
              <StaggerGroup className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {items.map((rep) => (
                  <StaggerItem key={rep.id}>
                    <Link
                      to={rep.url}
                      className="group flex h-full flex-col rounded border border-border bg-card p-5 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40"
                      data-testid={`rep-card-${rep.slug}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-heading text-lead font-semibold tracking-tight group-hover:text-primary">
                            {rep.name}
                          </p>
                          {rep.nameHi ? (
                            <p className="mt-0.5 text-meta text-foreground/60" lang="hi">
                              {rep.nameHi}
                            </p>
                          ) : null}
                        </div>
                        {rep.party ? <Pill tone="muted">{rep.party.code}</Pill> : null}
                      </div>

                      <p className="mt-3 text-body text-foreground/70">
                        {rep.houseLabel}
                        {rep.constituency ? ` — ${rep.constituency.name}` : ""}
                      </p>
                      {rep.office ? (
                        <p className="mt-1 text-meta font-medium text-secondary">{rep.office}</p>
                      ) : null}

                      <div className="mt-auto flex flex-wrap gap-1.5 pt-4">
                        <Pill tone={rep.isDirectlyElected ? "primary" : "muted"}>
                          {rep.isDirectlyElected
                            ? t("reps.directlyElected")
                            : t("reps.notDirectlyElected")}
                        </Pill>
                        {!rep.isSitting ? <Pill tone="muted">Former member</Pill> : null}
                      </div>
                    </Link>
                  </StaggerItem>
                ))}
              </StaggerGroup>
            </>
          )}
        </div>
      </Section>

      {/* What is tracked, and what each number does not mean. Public on purpose --
          a reader should be able to check our definitions without taking our word. */}
      <Section muted testId="tracked-fields">
        <SectionHeading
          eyebrow="Method"
          title="What we track, and what each figure does not mean"
          lede="Every one of these is entered with a link to the public record it came from, and the high-risk ones will not publish until a fact-checker has confirmed them against that record."
        />
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {meta.fields.map((field) => (
            <div key={field.key} className="rounded border border-border bg-card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-heading text-body font-semibold tracking-tight">{field.label}</p>
                {field.requiresPrimarySource ? (
                  <Pill tone="secondary">Primary source required</Pill>
                ) : null}
              </div>
              <p className="mt-2 text-meta leading-relaxed text-foreground/70">
                {field.explanation}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-8">
          <Disclaimer text={meta.disclaimer} />
        </div>
      </Section>

      <Section>
        <Reveal>
          <div className="rounded border border-border bg-card p-8">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              The same standard for every party
            </h2>
            <p className="mt-3 max-w-3xl text-body text-foreground/70">
              Party affiliation appears here the way a date of birth does: as a neutral fact. There
              is no rating, no score and no editorial description of any party anywhere in this
              database &mdash; the schema has nowhere to put one. The same fields, the same sourcing
              rule and the same fact-check gate apply to every representative regardless of who they
              belong to.
            </p>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
