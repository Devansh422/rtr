import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  ExternalLink,
  FileText,
  Landmark,
  Scale,
  ScrollText,
} from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import {
  Section,
  Pill,
  Disclaimer,
  HistoryList,
  EmptyState,
} from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import EvidenceTimeline from "@/components/manifesto/EvidenceTimeline";
import { AttachmentButton, DocumentCard } from "@/components/manifesto/DocumentPreview";
import {
  PromiseStatusBadge,
  RtiStatusPill,
  WhyThisStatus,
} from "@/components/manifesto/StatusBadge";
import LinkButton from "@/components/LinkButton";
import { getManifestoPromise, getManifestoPromiseHistory } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";

/*
 * One promise, and everything on the record about it.
 *
 * THE PAGE IS BUILT AROUND ONE RULE (§14). Three blocks, in this order, never
 * merged and never interleaved:
 *
 *   1. Manifesto says          -- the party's words, quoted.
 *   2. Government records say  -- the authority's words and its documents.
 *   3. Evidence-based assessment -- this platform's reading, labelled as ours.
 *
 * They arrive from the API as three separate objects (`manifestoSays`,
 * `recordsSay`, `assessment`) precisely so that this file cannot quietly blend
 * them. Anything that reads as a conclusion lives in block 3 or in the "Why this
 * status?" panel, and every conclusion sits within one screen of the records it
 * is drawn from (§24).
 *
 * THE STATUS APPEARS TWICE, DELIBERATELY. Once at the top, where a reader
 * scanning on a phone will see it, and once at the bottom of the assessment with
 * its reasoning. What the top badge never does is stand alone: "Why this status?"
 * is directly beneath it and opens the reasoning and the records in place.
 *
 * MOBILE (§22). The jump bar below is the whole navigation of this page --
 * promise, RTI, reply, evidence -- so the four things a citizen came for are one
 * tap apart on a phone rather than a scroll through everything above them.
 */

const JUMPS = [
  { id: "manifesto-says", label: "Promise" },
  { id: "rti", label: "RTI" },
  { id: "reply", label: "Reply" },
  { id: "evidence", label: "Evidence" },
  { id: "assessment", label: "Assessment" },
];

function LayerHeading({ index, title, lede, icon: Icon }) {
  return (
    <div className="border-b border-border pb-5">
      <p className="flex items-center gap-2 text-label font-bold uppercase text-secondary">
        <Icon className="h-4 w-4" aria-hidden="true" />
        Section {index}
      </p>
      <h2 className="mt-2 font-heading text-title-2 font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 max-w-3xl text-body text-foreground/70">{lede}</p>
    </div>
  );
}

function Field({ label, children }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-label font-bold uppercase text-muted-foreground">{label}</dt>
      <dd className="text-body text-foreground/80">{children}</dd>
    </div>
  );
}

const formatDate = (value) => (value ? new Date(value).toLocaleDateString() : null);

export default function ManifestoPromise() {
  const { code } = useParams();
  const { locale } = useLocale();
  const hi = locale === "hi";

  const [promise, setPromise] = useState(null);
  const [history, setHistory] = useState([]);
  const [state, setState] = useState("loading"); // loading | ready | missing

  useEffect(() => {
    if (!code) return;
    setState("loading");
    getManifestoPromise(code)
      .then((data) => {
        setPromise(data);
        setState("ready");
        getManifestoPromiseHistory(code).then(setHistory);
      })
      .catch(() => setState("missing"));
  }, [code]);

  if (state === "loading") {
    return (
      <Section testId="manifesto-promise-loading">
        <p className="text-body text-foreground/60">Loading the record…</p>
      </Section>
    );
  }

  if (state === "missing") {
    return (
      <Section testId="manifesto-promise-missing">
        <EmptyState
          title="No published record for this promise"
          body={`Nothing is published under ${code}. It may not have been researched yet, or the identifier may be mistyped.`}
          action={
            <LinkButton to="/manifesto/promises" variant="outline">
              Browse all promises
            </LinkButton>
          }
        />
      </Section>
    );
  }

  const { manifestoSays, recordsSay, assessment, counts, timeline } = promise;
  const manifesto = manifestoSays?.manifesto;
  const applications = recordsSay?.rtiApplications ?? [];
  const documents = recordsSay?.documents ?? [];
  const evidence = recordsSay?.evidence ?? [];

  return (
    <div data-testid="manifesto-promise-page">
      <ModuleNav />

      {/* ---- Identity and current status ---- */}
      <Section testId="promise-header">
        <Link
          to="/manifesto/promises"
          className="inline-flex items-center gap-2 text-meta text-foreground/60 hover:text-primary"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          All promises
        </Link>

        <div className="mt-6 flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 max-w-3xl">
            <span className="rounded border border-border bg-muted/50 px-2 py-0.5 font-mono text-meta font-medium text-foreground/70">
              {promise.code}
            </span>
            <h1 className="mt-3 font-heading text-title-1 font-semibold leading-tight tracking-tighter">
              {hi && promise.titleHi ? promise.titleHi : promise.title}
            </h1>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Pill>{promise.department}</Pill>
              <Pill tone="muted">{promise.category}</Pill>
              {promise.election ? <Pill tone="muted">{promise.election.name}</Pill> : null}
            </div>
          </div>
          <PromiseStatusBadge status={promise.status} size="large" />
        </div>

        {/* §24: never the conclusion on its own. */}
        <div className="mt-6 max-w-3xl">
          <WhyThisStatus status={promise.status} assessment={assessment}>
            {assessment?.sources?.length ? (
              <div className="mt-5">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  Drawn from these records
                </p>
                <ul className="mt-2 space-y-1">
                  {assessment.sources.map((source) => (
                    <li
                      key={`${source.kind}-${source.id}`}
                      className="text-meta text-foreground/70"
                    >
                      · {source.label || `${source.kind} ${source.id}`}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <p className="mt-5 text-meta text-muted-foreground">
              Every record named here is published in full further down this page.
            </p>
          </WhyThisStatus>
        </div>

        {/* Mobile-first jump bar (§22). */}
        <nav aria-label="Sections of this record" className="mt-6 flex gap-2 overflow-x-auto pb-1">
          {JUMPS.map((jump) => (
            <a
              key={jump.id}
              href={`#${jump.id}`}
              className="shrink-0 rounded border border-border bg-card px-3 py-1.5 text-meta font-medium text-foreground/75 hover:border-primary/40 hover:text-primary"
            >
              {jump.label}
            </a>
          ))}
        </nav>

        <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["RTI applications", counts?.rtiApplications],
            ["Questions asked", counts?.questions],
            ["Questions answered", counts?.answers],
            ["Replies received", counts?.responses],
            ["Documents", counts?.documents],
            ["Evidence statements", counts?.evidence],
          ].map(([label, value]) => (
            <div key={label} className="rounded border border-border bg-card p-3">
              <p className="text-label font-bold uppercase text-muted-foreground">{label}</p>
              <p className="mt-0.5 font-heading text-lead font-semibold">{value ?? 0}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ================= 1. MANIFESTO SAYS (§8A) ================= */}
      <Section muted testId="manifesto-says">
        <div id="manifesto-says" className="scroll-mt-24">
          <LayerHeading
            index={1}
            icon={ScrollText}
            title="What the manifesto says"
            lede="The promise exactly as printed in the party's published manifesto. Reproduced, not paraphrased."
          />

          <blockquote className="mt-8 border-l-4 border-secondary bg-card p-6 text-lead leading-relaxed text-foreground/90">
            {hi && manifestoSays?.promiseTextHi
              ? manifestoSays.promiseTextHi
              : manifestoSays?.promiseText}
          </blockquote>

          {/* Both languages where both exist: the manifesto was published in
              Hindi, and an English reader should still be able to see the words
              that were actually printed. */}
          {manifestoSays?.promiseTextHi &&
          manifestoSays.promiseTextHi !== manifestoSays.promiseText ? (
            <details className="mt-3">
              <summary className="cursor-pointer text-meta text-foreground/60 hover:text-primary">
                {hi ? "Show the English text" : "मूल हिंदी पाठ देखें (show the Hindi text)"}
              </summary>
              <p
                lang={hi ? "en" : "hi"}
                className="mt-3 border-l-2 border-border pl-4 text-body leading-relaxed text-foreground/75"
              >
                {hi ? manifestoSays.promiseText : manifestoSays.promiseTextHi}
              </p>
            </details>
          ) : null}

          <dl className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Promise ID">{promise.code}</Field>
            <Field label="Manifesto">{manifesto?.title}</Field>
            <Field label="Political party">{manifesto?.party}</Field>
            <Field label="Election">{promise.election?.name}</Field>
            <Field label="Election year">{promise.election?.year}</Field>
            <Field label="Manifesto page">{manifestoSays?.page}</Field>
            <Field label="Manifesto published">{formatDate(manifesto?.publishedOn)}</Field>
            <Field label="Total pages">{manifesto?.totalPages}</Field>
          </dl>

          {manifesto?.sourceNote ? (
            <p className="mt-6 text-meta leading-relaxed text-foreground/60">
              <span className="font-semibold text-foreground/80">Where this copy came from: </span>
              {manifesto.sourceNote}
            </p>
          ) : null}

          <div className="mt-6 flex flex-wrap gap-3">
            {manifesto?.sourceUrl ? (
              <AttachmentButton
                url={manifesto.sourceUrl}
                title={manifesto.title}
                sourceNote={manifesto.sourceNote}
                label="View the original manifesto"
                className="px-3 py-2"
              />
            ) : null}
            {manifestoSays?.pageUrl ? (
              <AttachmentButton
                url={manifestoSays.pageUrl}
                title={`${manifesto?.title ?? "Manifesto"} — page ${manifestoSays.page}`}
                label={`View page ${manifestoSays.page}`}
                className="px-3 py-2"
              />
            ) : null}
            {!manifesto?.sourceUrl && !manifestoSays?.pageUrl ? (
              <p className="flex items-center gap-2 text-meta text-foreground/60">
                <AlertCircle className="h-4 w-4" aria-hidden="true" />
                No scan of the manifesto is published against this promise yet.
              </p>
            ) : null}
          </div>
        </div>
      </Section>

      {/* ================= 2. GOVERNMENT RECORDS SAY (§8B–§11) ================= */}
      <Section testId="records-say">
        <div id="rti" className="scroll-mt-24">
          <LayerHeading
            index={2}
            icon={Landmark}
            title="What the government's own records say"
            lede="The RTI applications filed against this promise, the questions asked, the answers received in the authority's own words, and the official documents supplied."
          />
        </div>

        {applications.length === 0 ? (
          <div className="mt-8">
            <EmptyState
              title="No RTI application published against this promise yet"
              body="An application has either not been filed, or has been filed and not yet published here. Nothing is inferred from its absence."
            />
          </div>
        ) : (
          applications.map((application) => (
            <article key={application.id} className="mt-8 rounded border border-border bg-card">
              {/* ---- The application (§8B) ---- */}
              <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border p-6">
                <div>
                  <span className="font-mono text-meta font-medium text-muted-foreground">
                    {application.code}
                  </span>
                  <h3 className="mt-1 font-heading text-lead font-semibold tracking-tight">
                    {application.subject || "RTI application"}
                  </h3>
                </div>
                <RtiStatusPill status={application.status} label={application.statusLabel} />
              </header>

              <div className="p-6">
                <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Public authority">{application.publicAuthority}</Field>
                  <Field label="Department">{application.department}</Field>
                  <Field label="Public Information Officer">{application.pioDesignation}</Field>
                  <Field label="Application number">{application.applicationNumber}</Field>
                  <Field label="Filed on">{formatDate(application.filedOn)}</Field>
                  <Field label="Reply due">{formatDate(application.replyDueOn)}</Field>
                </dl>

                {application.notes ? (
                  <p className="mt-5 text-meta leading-relaxed text-foreground/60">
                    {application.notes}
                  </p>
                ) : null}

                <div className="mt-5 flex flex-wrap gap-2">
                  {application.applicationUrl ? (
                    <AttachmentButton
                      url={application.applicationUrl}
                      title={`RTI application ${application.code}`}
                      label="View the RTI application"
                      className="px-3 py-2"
                    />
                  ) : null}
                  {application.filingProofUrl ? (
                    <AttachmentButton
                      url={application.filingProofUrl}
                      title={`Filing proof — ${application.code}`}
                      label="View filing proof"
                      className="px-3 py-2"
                    />
                  ) : null}
                </div>

                {/* ---- Questions and answers (§9) ---- */}
                <div className="mt-8 border-t border-border pt-6">
                  <h4 className="font-heading text-body font-semibold tracking-tight">
                    Questions asked, and the answers received
                  </h4>
                  <p className="mt-1 text-meta text-foreground/60">
                    Each answer is reproduced as the public authority gave it.
                  </p>

                  {application.questions?.length ? (
                    <ol className="mt-5 space-y-5">
                      {application.questions.map((question) => (
                        <li
                          key={question.id}
                          className="rounded border border-border bg-background p-5"
                          data-testid={`rti-question-${question.number}`}
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <p className="text-label font-bold uppercase text-secondary">
                              Question {String(question.number).padStart(2, "0")}
                            </p>
                            <Pill tone="muted">{question.answerStatusLabel}</Pill>
                          </div>

                          <p className="mt-3 text-body font-medium leading-relaxed text-foreground/90">
                            {hi && question.questionHi ? question.questionHi : question.question}
                          </p>

                          <div className="mt-4 rounded border border-border bg-muted/30 p-4">
                            <p className="text-label font-bold uppercase text-muted-foreground">
                              Government response
                            </p>
                            {question.answer ? (
                              <p className="mt-2 whitespace-pre-line text-body leading-relaxed text-foreground/85">
                                {question.answer}
                              </p>
                            ) : (
                              <p className="mt-2 text-body text-foreground/60">
                                No answer has been received to this question.
                              </p>
                            )}
                          </div>

                          {question.supportingDocument ? (
                            <div className="mt-4">
                              <p className="text-label font-bold uppercase text-muted-foreground">
                                Supporting record
                              </p>
                              <div className="mt-2">
                                <AttachmentButton document={question.supportingDocument} />
                              </div>
                            </div>
                          ) : null}
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-4 text-body text-foreground/60">
                      The questions from this application have not been published yet.
                    </p>
                  )}
                </div>

                {/* ---- The reply itself (§10) ---- */}
                <div id="reply" className="mt-8 scroll-mt-24 border-t border-border pt-6">
                  <h4 className="font-heading text-body font-semibold tracking-tight">
                    Government reply
                  </h4>

                  {application.responses?.length ? (
                    <div className="mt-4 space-y-4">
                      {application.responses.map((response) => (
                        <div
                          key={response.id}
                          className="rounded border border-border bg-background p-5"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <p className="font-heading text-body font-semibold tracking-tight">
                              {response.replyingAuthority}
                            </p>
                            {response.isAppealReply ? (
                              <Pill tone="secondary">Appeal reply</Pill>
                            ) : null}
                          </div>

                          <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <Field label="Reply dated">{formatDate(response.replyDated)}</Field>
                            <Field label="Received on">{formatDate(response.receivedOn)}</Field>
                            <Field label="Reference number">{response.referenceNumber}</Field>
                            <Field label="Department">{response.department}</Field>
                          </dl>

                          {response.summary ? (
                            <p className="mt-4 rounded border border-border bg-muted/30 p-4 text-meta leading-relaxed text-foreground/70">
                              <span className="font-semibold text-foreground/85">
                                Note on this reply:{" "}
                              </span>
                              {response.summary}
                            </p>
                          ) : null}

                          {response.documentUrl ? (
                            <div className="mt-4 flex flex-wrap gap-2">
                              <AttachmentButton
                                url={response.documentUrl}
                                title={`Government reply — ${response.replyingAuthority}`}
                                label="View the original reply"
                                className="px-3 py-2"
                              />
                              <a
                                href={response.documentUrl}
                                download
                                className="inline-flex items-center gap-1.5 rounded border border-border bg-card px-3 py-2 text-meta font-medium text-foreground/80 hover:border-primary/40 hover:text-primary"
                              >
                                <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                                Download the original reply
                              </a>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-body text-foreground/60">
                      No reply has been received against this application yet.
                      {application.replyDueOn
                        ? ` The statutory reply period ended ${formatDate(application.replyDueOn)}.`
                        : ""}
                    </p>
                  )}
                </div>
              </div>
            </article>
          ))
        )}

        {/* ---- Official documents (§11) ---- */}
        <div id="evidence" className="mt-12 scroll-mt-24">
          <h3 className="font-heading text-title-3 font-semibold tracking-tight">
            Official documents on record
          </h3>
          <p className="mt-2 max-w-3xl text-body text-foreground/70">
            Government orders, notifications, sanction orders and reports relating to this promise.
            Each is stored as issued, with the note saying where the copy came from.
          </p>

          {documents.length ? (
            <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {documents.map((document) => (
                <DocumentCard key={document.id} document={document} showPromise={false} />
              ))}
            </div>
          ) : (
            <p className="mt-4 text-body text-foreground/60">
              No official documents have been published against this promise yet.
            </p>
          )}
        </div>

        {/* ---- Evidence statements ---- */}
        {evidence.length ? (
          <div className="mt-12">
            <h3 className="font-heading text-title-3 font-semibold tracking-tight">
              What those records state
            </h3>
            <p className="mt-2 max-w-3xl text-body text-foreground/70">
              Each line below describes what a specific record says, and points at the record. These
              are descriptions of documents, not conclusions about the promise.
            </p>
            <ul className="mt-6 space-y-4">
              {evidence.map((item) => (
                <li key={item.id} className="rounded border border-border bg-card p-5">
                  <p className="text-body leading-relaxed text-foreground/85">
                    {hi && item.statementHi ? item.statementHi : item.statement}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    {item.locator ? <Pill tone="muted">{item.locator}</Pill> : null}
                    {item.recordedOn ? (
                      <span className="text-meta text-muted-foreground">
                        Recorded {formatDate(item.recordedOn)}
                      </span>
                    ) : null}
                    {item.document ? <AttachmentButton document={item.document} /> : null}
                    {item.rtiQuestion ? (
                      <span className="text-meta text-muted-foreground">
                        From RTI question {item.rtiQuestion.number}
                      </span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Section>

      {/* ================= 3. ASSESSMENT (§14.3) ================= */}
      <Section muted testId="assessment">
        <div id="assessment" className="scroll-mt-24">
          <LayerHeading
            index={3}
            icon={Scale}
            title="Evidence-based assessment"
            lede="This section is this platform's reading of the records above. It is not a government statement, and it is kept separate from one on purpose."
          />

          {assessment ? (
            <div className="mt-8 max-w-3xl">
              <div className="flex flex-wrap items-center gap-4">
                <PromiseStatusBadge status={assessment.status} size="large" />
                {assessment.assessedOn ? (
                  <span className="text-meta text-muted-foreground">
                    Assessed {formatDate(assessment.assessedOn)}
                    {assessment.version > 1 ? ` · version ${assessment.version}` : ""}
                  </span>
                ) : null}
              </div>

              <p className="mt-3 text-body leading-relaxed text-foreground/70">
                {assessment.status?.meaning}
              </p>

              {assessment.rationale ? (
                <div className="mt-6 rounded border border-border bg-card p-6">
                  <p className="text-label font-bold uppercase text-muted-foreground">Reasoning</p>
                  <p className="mt-2 whitespace-pre-line text-body leading-relaxed text-foreground/85">
                    {assessment.rationale}
                  </p>
                </div>
              ) : null}

              {assessment.methodNote ? (
                <div className="mt-4 rounded border border-border bg-card p-6">
                  <p className="text-label font-bold uppercase text-muted-foreground">
                    How this was checked
                  </p>
                  <p className="mt-2 whitespace-pre-line text-body leading-relaxed text-foreground/75">
                    {assessment.methodNote}
                  </p>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState
                title="No assessment has been published for this promise"
                body="The records above are published as they stand. An assessment is only written once there is enough on file to say something defensible about what they establish."
              />
            </div>
          )}
        </div>
      </Section>

      {/* ---- Timeline (§12) and record history (§17) ---- */}
      <Section>
        <div className="grid gap-12 lg:grid-cols-2">
          <div>
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              Evidence timeline
            </h2>
            <p className="mt-2 text-body text-foreground/70">
              Every stage of this promise's chain, with the date each record carries. Stages not yet
              reached are shown too.
            </p>
            <EvidenceTimeline stages={timeline ?? []} className="mt-6" />
          </div>

          <div>
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              Record history
            </h2>
            <p className="mt-2 text-body text-foreground/70">
              Every change made to this record since it was created. Contributor names are not
              shown.
            </p>
            <div className="mt-6">
              <HistoryList
                entries={history}
                emptyText="No changes have been recorded against this promise yet."
              />
            </div>
          </div>
        </div>
      </Section>

      <Section muted>
        <Reveal>
          <div className="grid gap-4 lg:grid-cols-2">
            <Disclaimer title="How to read this page" text={promise.disclaimer} />
            <div className="rounded border border-border bg-card p-5">
              <p className="text-label font-bold uppercase text-muted-foreground">
                Check it yourself
              </p>
              <p className="mt-2 text-meta leading-relaxed text-foreground/70">
                Every document on this page can be opened and downloaded. If you believe a record
                has been read wrongly here, the evidence is published precisely so that you can say
                so.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <LinkButton to="/manifesto/rti" variant="outline" size="sm">
                  The full RTI register
                </LinkButton>
                <LinkButton to="/tools/rti-general" variant="ghost" size="sm">
                  File an RTI yourself
                  <ExternalLink className="ml-2 h-4 w-4" aria-hidden="true" />
                </LinkButton>
              </div>
            </div>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
