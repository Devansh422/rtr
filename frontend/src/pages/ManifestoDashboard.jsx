import { useEffect, useState } from "react";

import { Reveal } from "@/components/motion/Reveal";
import { PageHero, Section, SectionHeading, Disclaimer } from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import { PromiseStatusBadge } from "@/components/manifesto/StatusBadge";
import LinkButton from "@/components/LinkButton";
import {
  getManifestoDashboard,
  getManifestoRtiSummary,
  getManifestoVocabulary,
} from "@/lib/platformApi";

/*
 * The accountability dashboard.
 *
 * EVERY NUMBER IS A COUNT OF PUBLISHED ROWS, taken when the page loaded. There is
 * no constant in this file a figure could come from, and no cached total the
 * research desk updates by hand -- on a site whose entire argument is "check the
 * records", a headline number nobody can reproduce from the records would be the
 * one unsourced claim on it.
 *
 * PROPORTIONS ARE SHOWN AGAINST ASSESSED PROMISES, NOT ALL PROMISES. A promise
 * nobody has researched yet is not evidence of anything, and counting it in the
 * denominator would silently move every percentage toward whichever conclusion
 * the unexamined pile happens to sit under. The unassessed count is shown
 * separately and prominently instead.
 *
 * THE STATUS LEGEND IS PART OF THE PAGE, not a footnote. Six statuses with
 * carefully limited meanings are only useful if the meanings travel with them,
 * and this is the one screen a reader is likely to look at before reading any
 * individual promise.
 */

function Figure({ label, value, sub, tone = "default" }) {
  return (
    <div className="rounded border border-border bg-card p-5">
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

/** A proportion bar. Renders nothing at all when there is nothing to divide by. */
function StatusBar({ byStatus, assessed }) {
  if (!assessed) return null;
  const tones = {
    fulfilled: "bg-emerald-600",
    partially_fulfilled: "bg-amber-500",
    under_implementation: "bg-sky-600",
    information_insufficient: "bg-orange-600",
    rti_reply_awaited: "bg-violet-600",
    not_established: "bg-muted-foreground/50",
  };

  return (
    <div className="mt-6">
      <div className="flex h-3 w-full overflow-hidden rounded border border-border">
        {byStatus
          .filter((status) => status.count > 0)
          .map((status) => (
            <span
              key={status.key}
              className={tones[status.key] ?? tones.not_established}
              style={{ width: `${(status.count / assessed) * 100}%` }}
              title={`${status.label}: ${status.count}`}
            />
          ))}
      </div>
      <p className="mt-2 text-meta text-muted-foreground">
        Proportions are of the {assessed} promise(s) with a published assessment.
      </p>
    </div>
  );
}

export default function ManifestoDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [rti, setRti] = useState({ summary: {} });
  const [vocabulary, setVocabulary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getManifestoDashboard(), getManifestoRtiSummary(), getManifestoVocabulary()])
      .then(([dash, register, vocab]) => {
        setDashboard(dash);
        setRti(register ?? { summary: {} });
        setVocabulary(vocab);
      })
      .finally(() => setLoading(false));
  }, []);

  const byStatus = dashboard?.byStatus ?? [];
  const totalCounted = byStatus.reduce((sum, status) => sum + (status.count ?? 0), 0);

  return (
    <div data-testid="manifesto-dashboard-page">
      <PageHero
        eyebrow="Accountability dashboard"
        lines={["The record,", "counted."]}
        lede="Where the Uttarakhand 2022 manifesto stands against the state government's own documents. Every figure below is counted from published records at the moment you loaded this page."
      />

      <ModuleNav />

      {loading ? (
        <Section>
          <p className="text-body text-foreground/60">Loading…</p>
        </Section>
      ) : (
        <>
          <Section>
            <SectionHeading eyebrow="Promises" title="What has been researched" />
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Figure label="Total promises" value={dashboard?.totalPromises} tone="primary" />
              <Figure
                label="Promises assessed"
                value={dashboard?.promisesAssessed}
                sub="An assessment is published"
              />
              <Figure
                label="Not yet assessed"
                value={dashboard?.promisesNotYetAssessed}
                sub="Research still open"
              />
              <Figure
                label="Evidence statements"
                value={dashboard?.evidenceItems}
                sub="Drawn from the records"
              />
            </div>

            <StatusBar byStatus={byStatus} assessed={totalCounted} />

            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {byStatus.map((status) => (
                <div
                  key={status.key}
                  className="rounded border border-border bg-card p-5"
                  data-testid={`dashboard-status-${status.key}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <PromiseStatusBadge status={status} />
                    <span className="font-heading text-title-3 font-semibold tracking-tight">
                      {status.count}
                    </span>
                  </div>
                  <p className="mt-3 text-meta leading-relaxed text-foreground/65">
                    {status.meaning}
                  </p>
                </div>
              ))}
            </div>
          </Section>

          <Section muted>
            <SectionHeading
              eyebrow="Right to Information"
              title="How the state has responded"
              lede="Filed, answered, and how completely. 'Information insufficient' counts replies that arrived without answering what was asked — it is a statement about the reply, not about the promise."
              action={
                <LinkButton to="/manifesto/rti" variant="ghost">
                  Open the RTI register
                </LinkButton>
              }
            />
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Figure label="RTIs filed" value={dashboard?.rtisFiled} tone="primary" />
              <Figure label="Replies received" value={dashboard?.repliesReceived} />
              <Figure
                label="Replies awaited"
                value={dashboard?.repliesAwaited}
                sub="Filed, nothing back yet"
              />
              <Figure label="Documents published" value={dashboard?.documentsPublished} />
              <Figure
                label="Information fully provided"
                value={rti.summary?.informationProvided}
                sub="Every question answered"
              />
              <Figure
                label="Partially provided"
                value={rti.summary?.partiallyProvided}
                sub="Some questions answered"
              />
              <Figure
                label="Information insufficient"
                value={rti.summary?.informationInsufficient}
                sub="Reply received, questions unanswered"
              />
              <Figure
                label="Total applications"
                value={rti.summary?.totalRtis}
                sub="Including those not yet filed"
              />
            </div>
          </Section>

          <Section>
            <SectionHeading
              eyebrow="Reading the statuses"
              title="What each status does and does not claim"
              lede="Every status describes the state of the record, not the character of anyone's conduct."
            />
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {(vocabulary?.promiseStatuses ?? []).map((status) => (
                <div key={status.key} className="rounded border border-border bg-card p-5">
                  <PromiseStatusBadge status={status} />
                  <p className="mt-3 text-body leading-relaxed text-foreground/75">
                    {status.meaning}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-8 grid gap-4 lg:grid-cols-2">
              <Reveal>
                <Disclaimer
                  title="How these figures are produced"
                  text={
                    dashboard?.note ||
                    "Every figure here is counted from published records at the moment you loaded this page."
                  }
                />
              </Reveal>
              <Reveal>
                <Disclaimer title="How to read a status" text={vocabulary?.editorialNote} />
              </Reveal>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
