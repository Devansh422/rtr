import { useEffect, useState } from "react";
import { ArrowRight, FileSearch, FileText, Landmark, Scale, ScrollText } from "lucide-react";

import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import {
  PageHero,
  Section,
  SectionHeading,
  EmptyState,
  Disclaimer,
} from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import { PromiseStatusBadge, RtiStatusPill } from "@/components/manifesto/StatusBadge";
import LinkButton from "@/components/LinkButton";
import {
  getManifestoDashboard,
  getManifestoElections,
  getManifestoPromises,
  getManifestoVocabulary,
} from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";

/*
 * Uttarakhand Manifesto Accountability -- the module's front door.
 *
 * WHAT THIS PAGE IS FOR. Not to summarise findings. To make the CHAIN legible in
 * one screen -- promise, RTI, reply, document, assessment -- so that a visitor
 * understands, before they read a single status, that every conclusion further in
 * is attached to a record they can open. A landing page that led with "3 of 12
 * promises unfulfilled" would be inviting exactly the trust this module refuses
 * to ask for.
 *
 * EVERY FIGURE IS COUNTED, NOT TYPED. The dashboard block renders whatever
 * `/manifesto/dashboard` returns, which is a set of SELECT count(*) over
 * published rows. There is no constant in this file that a number could come
 * from, and that is deliberate: a hard-coded "100 RTIs filed" on an
 * accountability site is the same category of failure as an unsourced claim.
 *
 * ONE ELECTION, SAID PLAINLY. The selector below lists what the API publishes,
 * which today is Uttarakhand 2022 alone. The schema behind it is state ->
 * election -> party -> manifesto -> promise, so a second state is data entry --
 * but until there is one, the page says "one election" rather than implying a
 * national database that does not exist (§5, §25).
 */

const CHAIN = [
  {
    icon: ScrollText,
    label: "Manifesto promise",
    detail: "Quoted from the published document, with its page number.",
  },
  {
    icon: FileText,
    label: "RTI application",
    detail: "Filed with the public authority that owns the subject.",
  },
  {
    icon: Landmark,
    label: "Government reply",
    detail: "Reproduced as received, with its reference number.",
  },
  {
    icon: FileSearch,
    label: "Official documents",
    detail: "Orders, sanctions and reports the reply relied on.",
  },
  {
    icon: Scale,
    label: "Evidence-based assessment",
    detail: "This platform's reading, labelled as such.",
  },
];

function StatCard({ label, value, sub, tone = "default" }) {
  return (
    <div className="rounded border border-border bg-card p-5" data-testid={`stat-${label}`}>
      <p className="text-label font-bold uppercase text-muted-foreground">{label}</p>
      <p
        className={`mt-1 font-heading text-title-2 font-semibold tracking-tight ${
          tone === "primary" ? "text-primary" : ""
        }`}
      >
        {value ?? "—"}
      </p>
      {sub ? <p className="mt-1 text-meta text-foreground/60">{sub}</p> : null}
    </div>
  );
}

export default function ManifestoAccountability() {
  const { locale } = useLocale();
  const [dashboard, setDashboard] = useState(null);
  const [elections, setElections] = useState([]);
  const [vocabulary, setVocabulary] = useState(null);
  const [recent, setRecent] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getManifestoDashboard(),
      getManifestoElections(),
      getManifestoVocabulary(),
      getManifestoPromises({ limit: 6, sort: "updated" }),
    ])
      .then(([dash, list, vocab, promises]) => {
        setDashboard(dash);
        setElections(list ?? []);
        setVocabulary(vocab);
        setRecent(promises ?? { items: [], total: 0 });
      })
      .finally(() => setLoading(false));
  }, []);

  const hi = locale === "hi";

  return (
    <div data-testid="manifesto-page">
      <PageHero
        eyebrow="Uttarakhand Manifesto Accountability"
        lines={["What was promised.", "What the record shows."]}
        lede="Manifesto promise → RTI → government reply → evidence → public record. Every promise made in the Uttarakhand Assembly Election is tracked against the state government's own documents, obtained under the Right to Information Act and published here in full."
      >
        <div className="flex flex-wrap gap-3">
          <LinkButton to="/manifesto/promises" variant="default">
            Explore promises
            <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
          </LinkButton>
          <LinkButton to="/manifesto/rti" variant="outline">
            View RTI records
          </LinkButton>
        </div>
      </PageHero>

      <ModuleNav />

      {/* ---- Transparency dashboard (§4). Counted live, never entered. ---- */}
      <Section testId="manifesto-dashboard">
        <SectionHeading
          eyebrow="Transparency dashboard"
          title="The state of the record, right now"
          lede="Every figure here is counted from published records at the moment you loaded this page."
          action={
            <LinkButton to="/manifesto/dashboard" variant="ghost">
              Full dashboard
            </LinkButton>
          }
        />

        {loading ? (
          <p className="mt-8 text-body text-foreground/60">Loading…</p>
        ) : (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Total promises" value={dashboard?.totalPromises} tone="primary" />
              <StatCard label="RTIs filed" value={dashboard?.rtisFiled} />
              <StatCard label="Replies received" value={dashboard?.repliesReceived} />
              <StatCard
                label="Replies awaited"
                value={dashboard?.repliesAwaited}
                sub="Filed, no reply on file yet"
              />
              <StatCard label="Documents published" value={dashboard?.documentsPublished} />
              <StatCard label="Evidence statements" value={dashboard?.evidenceItems} />
              <StatCard label="Promises assessed" value={dashboard?.promisesAssessed} />
              <StatCard
                label="Not yet assessed"
                value={dashboard?.promisesNotYetAssessed}
                sub="Research still open"
              />
            </div>

            {dashboard?.byStatus?.length ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {dashboard.byStatus.map((status) => (
                  <div
                    key={status.key}
                    className="flex items-center justify-between gap-3 rounded border border-border bg-card p-4"
                  >
                    <PromiseStatusBadge status={status} />
                    <span className="font-heading text-lead font-semibold tracking-tight">
                      {status.count}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}

            {dashboard?.note ? (
              <p className="mt-4 text-meta text-muted-foreground">{dashboard.note}</p>
            ) : null}
          </>
        )}
      </Section>

      {/* ---- The chain (§16). Shown before any finding. ---- */}
      <Section muted>
        <SectionHeading
          eyebrow="How this works"
          title="Nothing here asks to be taken on trust"
          lede="Each promise carries the whole documentary chain behind it. You can open every record at each step and reach your own conclusion."
        />
        <StaggerGroup className="mt-8 grid gap-4 md:grid-cols-3 lg:grid-cols-5">
          {CHAIN.map((step, index) => (
            <StaggerItem key={step.label}>
              <div className="flex h-full flex-col rounded border border-border bg-card p-5">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded border border-border text-secondary">
                    <step.icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="text-label font-bold uppercase text-muted-foreground">
                    Step {index + 1}
                  </span>
                </div>
                <p className="mt-3 font-heading text-body font-semibold tracking-tight">
                  {step.label}
                </p>
                <p className="mt-1 text-meta leading-relaxed text-foreground/70">{step.detail}</p>
              </div>
            </StaggerItem>
          ))}
        </StaggerGroup>
      </Section>

      {/* ---- Election selector (§5). One, and it says so. ---- */}
      <Section>
        <SectionHeading
          eyebrow="Election"
          title="Uttarakhand Assembly Election 2022"
          lede="This module covers one election. The database behind it is built as state → election → party → manifesto → promise, so more can be added without changing the schema — but only what has been researched is shown."
        />
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {elections.length === 0 ? (
            <EmptyState
              title="No election published yet"
              body="The Uttarakhand 2022 record opens as soon as the first promises are published."
            />
          ) : (
            elections.map((election) => (
              <div key={election.slug} className="rounded border border-border bg-card p-6">
                <p className="text-label font-bold uppercase text-secondary">
                  {election.house === "assembly" ? "Assembly election" : election.house}
                </p>
                <p className="mt-2 font-heading text-title-3 font-semibold tracking-tight">
                  {hi && election.nameHi ? election.nameHi : election.name}
                </p>
                <dl className="mt-4 space-y-1 text-meta text-foreground/70">
                  {election.electionDate ? (
                    <div className="flex gap-2">
                      <dt className="font-medium text-muted-foreground">Polling</dt>
                      <dd>{new Date(election.electionDate).toLocaleDateString()}</dd>
                    </div>
                  ) : null}
                  {election.resultDate ? (
                    <div className="flex gap-2">
                      <dt className="font-medium text-muted-foreground">Result</dt>
                      <dd>{new Date(election.resultDate).toLocaleDateString()}</dd>
                    </div>
                  ) : null}
                </dl>
                <div className="mt-5 flex flex-wrap gap-3">
                  <LinkButton to="/manifesto/promises" variant="default" size="sm">
                    Promises
                  </LinkButton>
                  {election.sourceUrl ? (
                    <LinkButton href={election.sourceUrl} external variant="ghost" size="sm">
                      Election Commission record
                    </LinkButton>
                  ) : null}
                </div>
              </div>
            ))
          )}
        </div>
      </Section>

      {/* ---- Recently updated promises ---- */}
      <Section muted>
        <SectionHeading
          eyebrow="Latest"
          title="Recently updated promises"
          action={
            <LinkButton to="/manifesto/promises" variant="ghost">
              All promises
            </LinkButton>
          }
        />
        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">Loading…</p>
          ) : recent.items.length === 0 ? (
            <EmptyState
              title="No promises published yet"
              body="Promises are entered from the published manifesto PDF one at a time, each with its page number, and appear here once the RTI trail behind them is on file. Nothing is added to make this page look fuller than the research is."
            />
          ) : (
            <StaggerGroup className="grid gap-3">
              {recent.items.map((promise) => (
                <StaggerItem key={promise.code}>
                  <a
                    href={promise.url}
                    className="flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-card p-5 transition-colors hover:border-primary/40"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-meta font-medium text-muted-foreground">{promise.code}</p>
                      <p className="mt-1 font-heading text-lead font-semibold tracking-tight">
                        {hi && promise.titleHi ? promise.titleHi : promise.title}
                      </p>
                      <p className="mt-1 text-meta text-foreground/60">
                        {[promise.department, promise.category].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <RtiStatusPill
                        status={promise.rti?.status}
                        label={promise.rti?.statusLabel}
                      />
                      <PromiseStatusBadge status={promise.status} />
                    </div>
                  </a>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>

      <Section>
        <Reveal>
          <Disclaimer
            title="How to read this module"
            text={
              vocabulary?.editorialNote ||
              "Statuses describe what the available official records establish. They are not findings about anyone's conduct."
            }
          />
        </Reveal>
      </Section>
    </div>
  );
}
