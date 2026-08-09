import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Reveal } from "@/components/motion/Reveal";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import LinkButton from "@/components/LinkButton";
import {
  Section,
  SectionHeading,
  ClaimValue,
  Disclaimer,
  EmptyState,
  HistoryList,
  Pill,
  SourceLink,
  StatTile,
  VerificationBadge,
} from "@/components/platform/Primitives";
import CorrectionDialog from "@/components/platform/CorrectionDialog";
import {
  getCorrections,
  getRepresentative,
  getRepresentativeHistory,
} from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, ExternalLink, Mail, MapPin } from "lucide-react";

export default function RepresentativeProfile() {
  const { slug } = useParams();
  const { t } = useLocale();
  const [rep, setRep] = useState(null);
  const [history, setHistory] = useState([]);
  const [corrections, setCorrections] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    setStatus("loading");
    getRepresentative(slug)
      .then((data) => {
        setRep(data);
        setStatus("ready");
      })
      .catch(() => setStatus("missing"));
    getRepresentativeHistory(slug).then(setHistory);
    getCorrections("representative", slug).then(setCorrections);
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
          title="This profile is not published"
          body="Either it does not exist yet, or it is still a draft awaiting fact-check. Profiles do not go live until their high-risk claims have been confirmed against a public record."
          action={<LinkButton to="/representatives">Browse the database</LinkButton>}
        />
      </Section>
    );
  }

  return (
    <div data-testid={`rep-profile-${rep.slug}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-5xl">
          <Link
            to="/representatives"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.representatives")}
          </Link>

          <div className="mt-6 flex flex-wrap items-start gap-6">
            {rep.photoUrl ? (
              <img
                src={rep.photoUrl}
                alt=""
                className="h-24 w-24 rounded border border-border object-cover"
              />
            ) : null}
            <div className="min-w-0 flex-1">
              <h1 className="font-heading text-title-1 font-semibold leading-[1.05] tracking-tighter">
                {rep.name}
              </h1>
              {rep.nameHi ? (
                <p className="mt-2 text-lead text-foreground/60" lang="hi">
                  {rep.nameHi}
                </p>
              ) : null}
              <p className="mt-4 text-lead text-foreground/80">
                {rep.houseLabel}
                {rep.constituency ? ` — ${rep.constituency.name}` : ""}
              </p>
              {rep.office ? (
                <p className="mt-1 text-body font-medium text-secondary">{rep.office}</p>
              ) : null}

              <div className="mt-5 flex flex-wrap gap-2">
                {/* Party as a neutral fact, per §1 -- a label, never framing. */}
                {rep.party ? (
                  <Pill tone="muted">
                    {rep.party.name} ({rep.party.code})
                  </Pill>
                ) : null}
                <Pill tone={rep.isDirectlyElected ? "primary" : "muted"}>
                  {rep.isDirectlyElected ? t("reps.directlyElected") : t("reps.notDirectlyElected")}
                </Pill>
                {rep.constituency?.reservedFor ? (
                  <Pill tone="muted">Reserved ({rep.constituency.reservedFor})</Pill>
                ) : null}
                {rep.termStart ? (
                  <Pill tone="muted">
                    Term from {new Date(rep.termStart).toLocaleDateString()}
                  </Pill>
                ) : null}
                {!rep.isSitting ? <Pill tone="muted">Former member</Pill> : null}
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <CorrectionDialog entityType="representative" entityId={rep.slug} fieldLabel={rep.name} />
            <LinkButton to="/tools/representation-to-representative" variant="outline" size="sm">
              <Mail className="h-4 w-4" aria-hidden="true" />
              Write to this office
            </LinkButton>
          </div>

          <div className="mt-8">
            <SourceLink citation={{ ...rep.source, isPrimary: true }} />
          </div>
        </div>
      </section>

      {/* Verification summary, before any figure. A reader should know how much of
          this page has been checked before they read the numbers. */}
      <Section testId="rep-claim-summary">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label={t("reps.claimsFactChecked")}
            value={rep.claimSummary.factChecked}
            sub={`of ${rep.claimSummary.total} published figures`}
            tone="primary"
          />
          <StatTile
            label={t("reps.claimsUnverified")}
            value={rep.claimSummary.unverified}
            sub="Entered with a source, not yet confirmed"
          />
          <StatTile label="Disputed" value={rep.claimSummary.disputed} sub="A correction is open" />
          <StatTile
            label={t("reps.promises")}
            value={rep.promiseTally?.total ?? 0}
            sub={`${rep.promiseTally?.assessed ?? 0} assessed`}
          />
        </div>

        <div className="mt-8">
          <Disclaimer text={rep.disclaimer} />
        </div>
      </Section>

      {/* The claims themselves, grouped, each with its own citation and status. */}
      <Section muted testId="rep-claims">
        {rep.claims?.length ? (
          <div className="space-y-12">
            {rep.claims.map((group) => (
              <div key={group.category}>
                <SectionHeading title={group.category} />
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  {group.items.map((claim) => (
                    <div key={claim.id}>
                      <ClaimValue claim={claim} />
                      <div className="mt-2">
                        <CorrectionDialog
                          entityType="representative"
                          entityId={rep.slug}
                          fieldKey={claim.fieldKey}
                          fieldLabel={claim.label}
                          triggerVariant="ghost"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No figures published for this representative yet"
            body="The profile exists, but the attendance, questions, declared assets and case data have not been researched and fact-checked yet. Nothing appears here until it has been."
            action={
              <LinkButton to="/volunteer" variant="outline">
                Help research this
              </LinkButton>
            }
          />
        )}
      </Section>

      {/* Promises. */}
      {rep.promises?.length ? (
        <Section testId="rep-promises">
          <SectionHeading
            eyebrow="Promise tracker"
            title="What was promised, and what happened"
            lede="Each entry cites evidence that the promise was made, and separate evidence for what became of it."
          />
          <div className="mt-8 grid gap-3">
            {rep.promises.map((promise) => (
              <Link
                key={promise.id}
                to={promise.url}
                className="flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-card p-5 hover:border-primary/40"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-heading text-body font-semibold tracking-tight">
                    {promise.title}
                  </p>
                  <p className="mt-1 text-meta text-foreground/60">
                    {promise.madeContext || promise.category}
                    {promise.madeOn ? ` · ${new Date(promise.madeOn).toLocaleDateString()}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
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
                  <VerificationBadge
                    status={promise.verificationStatus}
                    label={promise.verificationStatus === "fact_checked" ? "checked" : "unverified"}
                  />
                </div>
              </Link>
            ))}
          </div>
        </Section>
      ) : null}

      {/* Contact, history, corrections. */}
      <Section muted>
        <div className="grid gap-8 lg:grid-cols-[320px_1fr]">
          <div className="rounded border border-border bg-card p-6">
            <h3 className="font-heading text-title-4 font-semibold tracking-tight">
              Official contact
            </h3>
            <p className="mt-2 text-meta text-foreground/60">
              Published by the House so that citizens can write to the office. Personal numbers are
              never recorded here.
            </p>
            <div className="mt-4 space-y-3 text-body">
              {rep.contact?.officeAddress ? (
                <p className="flex gap-2">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="whitespace-pre-line">{rep.contact.officeAddress}</span>
                </p>
              ) : null}
              {rep.contact?.email ? (
                <p className="flex gap-2">
                  <Mail className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <a
                    href={`mailto:${rep.contact.email}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {rep.contact.email}
                  </a>
                </p>
              ) : null}
              {rep.contact?.officialPage ? (
                <p className="flex gap-2">
                  <ExternalLink
                    className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <a
                    href={rep.contact.officialPage}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Official page
                  </a>
                </p>
              ) : null}
              {!rep.contact?.officeAddress && !rep.contact?.email && !rep.contact?.officialPage ? (
                <p className="text-foreground/60">Not recorded yet.</p>
              ) : null}
            </div>
          </div>

          <Tabs defaultValue="history" className="rounded border border-border bg-card p-6">
            <TabsList>
              <TabsTrigger value="history">
                {t("common.history")} ({history.length})
              </TabsTrigger>
              <TabsTrigger value="corrections">
                Corrections ({corrections?.total ?? 0})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="history" className="mt-5">
              <p className="mb-4 text-meta text-foreground/60">
                Every change to this profile, with the source behind it. This is the record that
                makes the data checkable rather than merely visible &mdash; and it cannot be edited,
                including by us.
              </p>
              <HistoryList entries={history} />
            </TabsContent>

            <TabsContent value="corrections" className="mt-5">
              {corrections?.items?.length ? (
                <ul className="space-y-3">
                  {corrections.items.map((item) => (
                    <li key={item.id} className="rounded border border-border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Pill tone={item.status === "accepted" ? "primary" : "muted"}>
                          {item.statusLabel}
                        </Pill>
                        <span className="text-meta text-muted-foreground">{item.filedOn}</span>
                      </div>
                      <p className="mt-2 text-body text-foreground/80">{item.summary}</p>
                      {item.resolutionNote ? (
                        <p className="mt-2 text-meta text-foreground/70">
                          <strong className="font-semibold">Reviewer: </strong>
                          {item.resolutionNote}
                        </p>
                      ) : null}
                      {item.source ? <SourceLink citation={item.source} className="mt-2" /> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-body text-foreground/60">
                  Nothing on this profile has been contested. If a figure here is wrong, filing a
                  correction with a link to the public record is the fastest way to get it fixed.
                </p>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </Section>

      <Section>
        <Reveal>
          <div className="rounded border border-border bg-muted/40 p-8">
            <h2 className="font-heading text-title-4 font-semibold tracking-tight">
              A note on criminal cases
            </h2>
            <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/70">
              Where this page records pending criminal cases, those figures come from the
              representative&rsquo;s own affidavit to the Election Commission. A pending case is an
              allegation that a court has not decided. Article 20 and the presumption of innocence
              apply in full. This platform does not investigate allegations, does not assess their
              merit, and takes no position on the guilt of any individual. Publishing the number is
              not an accusation &mdash; it is the disclosure the Supreme Court held voters are
              entitled to in{" "}
              <em>Union of India v. Association for Democratic Reforms</em> (2002).
            </p>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
