import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHero, Section, EmptyState, Pill, Disclaimer } from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import { AttachmentButton } from "@/components/manifesto/DocumentPreview";
import {
  PromiseStatusBadge,
  ResponseStatusBadge,
  RtiStatusPill,
} from "@/components/manifesto/StatusBadge";
import LinkButton from "@/components/LinkButton";
import { getManifestoRtiSummary, getManifestoVocabulary } from "@/lib/platformApi";
import { cn } from "@/lib/utils";

/*
 * The RTI register: every application, what was asked, and what came back.
 *
 * THE COLUMN DISTINCTION THAT MATTERS MOST. "Government reply" and "Promise
 * status" are adjacent columns and are never the same value. The first is what
 * the public authority stated; the second is what this platform concludes the
 * records establish. A reader must be able to see an authority reply "the scheme
 * is under implementation" next to an assessment of "status not established" and
 * understand that both are being reported faithfully -- which is only possible if
 * the table never merges them (§14, and the note the API returns alongside these
 * rows).
 *
 * TWO VIEWS OF THE SAME ROWS. "Promise summary" answers "what is the state of
 * each promise's RTI trail"; "Response summary" answers "how completely does this
 * government actually answer". The second is the one that shows a pattern across
 * applications, which no single promise page can.
 *
 * TABLE ON DESKTOP, CARDS ON A PHONE. Not a horizontally scrolling table with
 * nine columns -- most readers arrive on a phone (§22), and a register they
 * cannot read is not a register. Both render from the same row objects.
 */

const ALL = "__all__";

function SummaryCards({ summary }) {
  const cards = [
    ["Total RTIs", summary.totalRtis, null],
    ["Replies received", summary.repliesReceived, null],
    ["Replies awaited", summary.repliesAwaited, "Filed, nothing back yet"],
    ["Information fully provided", summary.informationProvided, "Every question answered"],
    ["Partially provided", summary.partiallyProvided, "Some questions answered"],
    [
      "Information insufficient",
      summary.informationInsufficient,
      "Reply received, questions unanswered",
    ],
    ["Documents provided", summary.documentsProvided, "Records supplied with replies"],
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map(([label, value, sub]) => (
        <div key={label} className="rounded border border-border bg-card p-5">
          <p className="text-label font-bold uppercase text-muted-foreground">{label}</p>
          <p className="mt-1 font-heading text-title-2 font-semibold tracking-tight">
            {value ?? 0}
          </p>
          {sub ? <p className="mt-1 text-meta text-foreground/60">{sub}</p> : null}
        </div>
      ))}
    </div>
  );
}

/** The questions, answers and attachments behind one row. */
function ExpandedRow({ item }) {
  return (
    <div className="space-y-5 border-t border-border bg-muted/20 p-5">
      {item.questions?.length ? (
        <ol className="space-y-4">
          {item.questions.map((question) => (
            <li key={question.id} className="rounded border border-border bg-background p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-label font-bold uppercase text-secondary">
                  Question {String(question.number).padStart(2, "0")}
                </p>
                <Pill tone="muted">{question.answerStatusLabel}</Pill>
              </div>
              <p className="mt-2 text-body font-medium leading-relaxed text-foreground/90">
                {question.question}
              </p>
              <div className="mt-3 rounded border border-border bg-muted/30 p-3">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  Government answer
                </p>
                <p className="mt-1 whitespace-pre-line text-meta leading-relaxed text-foreground/85">
                  {question.answer || "No answer received to this question."}
                </p>
              </div>
              {question.supportingDocument ? (
                <div className="mt-3">
                  <AttachmentButton document={question.supportingDocument} />
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-meta text-foreground/60">
          The questions from this application have not been published yet.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {item.applicationUrl ? (
          <AttachmentButton
            url={item.applicationUrl}
            title={`RTI application ${item.code}`}
            label="View original RTI"
            className="px-3 py-2"
          />
        ) : null}
        {item.replyDocumentUrl ? (
          <AttachmentButton
            url={item.replyDocumentUrl}
            title={`Government reply — ${item.replyingAuthority ?? item.code}`}
            label="View original government reply"
            className="px-3 py-2"
          />
        ) : null}
        {item.documentsProvided?.map((document) => (
          <AttachmentButton key={document.id} document={document} className="px-3 py-2" />
        ))}
        <LinkButton to={item.promise?.url ?? "#"} variant="ghost" size="sm">
          Full promise record
        </LinkButton>
      </div>
    </div>
  );
}

function ResponseTable({ items, expanded, toggle }) {
  return (
    <div className="hidden overflow-x-auto rounded border border-border lg:block">
      <table className="w-full border-collapse text-left">
        <thead className="bg-muted/50">
          <tr>
            {[
              "RTI ID",
              "Promise ID",
              "Subject",
              "Information sought",
              "Government reply — summary",
              "Records provided",
              "Reply date",
              "Response status",
              "",
            ].map((heading) => (
              <th
                key={heading}
                scope="col"
                className="whitespace-nowrap px-4 py-3 text-label font-bold uppercase text-muted-foreground"
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const open = expanded.has(item.id);
            return (
              <Fragment key={item.id}>
                <tr
                  className="border-t border-border align-top"
                  data-testid={`rti-row-${item.code}`}
                >
                  <td className="px-4 py-4 font-mono text-meta font-medium">{item.code}</td>
                  <td className="px-4 py-4 text-meta">
                    <Link
                      to={item.promise?.url ?? "#"}
                      className="font-mono text-primary underline-offset-4 hover:underline"
                    >
                      {item.promise?.code}
                    </Link>
                  </td>
                  <td className="max-w-[14rem] px-4 py-4 text-meta text-foreground/80">
                    {item.subject || "—"}
                  </td>
                  <td className="max-w-[18rem] px-4 py-4 text-meta text-foreground/75">
                    {item.informationSought || "—"}
                    {item.questionCount > 1 ? (
                      <span className="ml-1 text-muted-foreground">
                        (+{item.questionCount - 1} more)
                      </span>
                    ) : null}
                  </td>
                  {/* The authority's words. Never this platform's. */}
                  <td className="max-w-[20rem] px-4 py-4 text-meta text-foreground/75">
                    {item.replySummary || "—"}
                  </td>
                  <td className="px-4 py-4 text-meta">
                    {item.documentsProvided?.length ? (
                      <span className="text-foreground/80">
                        {item.documentsProvided.map((d) => d.kindLabel).join(", ")}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-meta text-foreground/75">
                    {item.replyDate ? new Date(item.replyDate).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-4">
                    <ResponseStatusBadge status={item.responseStatus} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-4">
                    <button
                      type="button"
                      onClick={() => toggle(item.id)}
                      className="inline-flex items-center gap-1 text-meta font-medium text-primary hover:underline"
                      aria-expanded={open}
                    >
                      {open ? "Hide" : "View response"}
                      <ChevronDown
                        className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
                        aria-hidden="true"
                      />
                    </button>
                  </td>
                </tr>
                {open ? (
                  <tr className="border-t border-border">
                    <td colSpan={9} className="p-0">
                      <ExpandedRow item={item} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ResponseCards({ items, expanded, toggle }) {
  return (
    <div className="space-y-4 lg:hidden">
      {items.map((item) => {
        const open = expanded.has(item.id);
        return (
          <article key={item.id} className="overflow-hidden rounded border border-border bg-card">
            <div className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <span className="font-mono text-meta font-medium text-muted-foreground">
                  {item.code}
                </span>
                <ResponseStatusBadge status={item.responseStatus} />
              </div>

              <p className="mt-2 font-heading text-body font-semibold tracking-tight">
                {item.subject || "RTI application"}
              </p>

              <Link
                to={item.promise?.url ?? "#"}
                className="mt-1 block font-mono text-meta text-primary underline-offset-4 hover:underline"
              >
                {item.promise?.code} — {item.promise?.title}
              </Link>

              <dl className="mt-4 space-y-3">
                <div>
                  <dt className="text-label font-bold uppercase text-muted-foreground">
                    Information sought
                  </dt>
                  <dd className="mt-0.5 text-meta text-foreground/75">
                    {item.informationSought || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-label font-bold uppercase text-muted-foreground">
                    Government reply — summary
                  </dt>
                  <dd className="mt-0.5 text-meta text-foreground/75">
                    {item.replySummary || "—"}
                  </dd>
                </div>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  <div>
                    <dt className="text-label font-bold uppercase text-muted-foreground">
                      Reply date
                    </dt>
                    <dd className="mt-0.5 text-meta text-foreground/75">
                      {item.replyDate ? new Date(item.replyDate).toLocaleDateString() : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label font-bold uppercase text-muted-foreground">
                      Records provided
                    </dt>
                    <dd className="mt-0.5 text-meta text-foreground/75">
                      {item.documentsProvided?.length
                        ? item.documentsProvided.map((d) => d.kindLabel).join(", ")
                        : "—"}
                    </dd>
                  </div>
                </div>
              </dl>

              <button
                type="button"
                onClick={() => toggle(item.id)}
                className="mt-4 inline-flex items-center gap-1 text-meta font-medium text-primary"
                aria-expanded={open}
              >
                {open ? "Hide response" : "View response"}
                <ChevronDown
                  className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
                  aria-hidden="true"
                />
              </button>
            </div>
            {open ? <ExpandedRow item={item} /> : null}
          </article>
        );
      })}
    </div>
  );
}

export default function ManifestoRti() {
  const [data, setData] = useState({ items: [], summary: {}, total: 0, note: "" });
  const [vocabulary, setVocabulary] = useState({ rtiStatuses: [] });
  const [status, setStatus] = useState(ALL);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(() => new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getManifestoVocabulary().then(setVocabulary);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setLoading(true);
    getManifestoRtiSummary({
      status: status === ALL ? undefined : status,
      q: search || undefined,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [status, search]);

  const toggle = (id) =>
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const items = data.items ?? [];

  return (
    <div data-testid="manifesto-rti-page">
      <PageHero
        eyebrow="RTI records"
        lines={["What was asked.", "What came back."]}
        lede="Every RTI application filed against an Uttarakhand manifesto promise, with the questions put to the public authority and the answers received, reproduced as given."
      />

      <ModuleNav />

      <Section>
        <SummaryCards summary={data.summary ?? {}} />

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:w-2/3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by RTI ID, subject, authority or promise"
              aria-label="Search RTI records"
              className="pl-9"
            />
          </div>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger aria-label="Filter by RTI status">
              <SelectValue placeholder="Any RTI status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Any RTI status</SelectItem>
              {vocabulary.rtiStatuses?.map((item) => (
                <SelectItem key={item.key} value={item.key}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Tabs defaultValue="responses" className="mt-8">
          <TabsList>
            <TabsTrigger value="promises">RTI promise summary</TabsTrigger>
            <TabsTrigger value="responses">RTI response summary</TabsTrigger>
          </TabsList>

          {/* ---- Promise-wise overview ---- */}
          <TabsContent value="promises" className="mt-6">
            {loading ? (
              <p className="text-body text-foreground/60">Loading…</p>
            ) : items.length === 0 ? (
              <EmptyState
                title="No RTI applications published yet"
                body="Applications appear here once they have been filed against a published promise and the trail behind them is on file."
              />
            ) : (
              <div className="grid gap-3">
                {items.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-card p-5"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-meta text-muted-foreground">
                        {item.code} · {item.promise?.code}
                      </p>
                      <Link
                        to={item.promise?.url ?? "#"}
                        className="mt-1 block font-heading text-lead font-semibold tracking-tight hover:text-primary"
                      >
                        {item.promise?.title}
                      </Link>
                      <p className="mt-1 text-meta text-foreground/60">
                        {[item.publicAuthority, item.department].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <RtiStatusPill status={item.status} label={item.statusLabel} />
                      <PromiseStatusBadge status={item.promise?.status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* ---- The register proper ---- */}
          <TabsContent value="responses" className="mt-6">
            {loading ? (
              <p className="text-body text-foreground/60">Loading…</p>
            ) : items.length === 0 ? (
              <EmptyState
                title="No RTI responses published yet"
                body="This register fills as replies arrive. An application with no reply still appears, marked as awaited — the absence of a reply is itself part of the record."
              />
            ) : (
              <>
                <ResponseTable items={items} expanded={expanded} toggle={toggle} />
                <ResponseCards items={items} expanded={expanded} toggle={toggle} />
              </>
            )}
          </TabsContent>
        </Tabs>

        {data.note ? (
          <div className="mt-8">
            <Disclaimer title="Reply and status are different things" text={data.note} />
          </div>
        ) : null}
      </Section>
    </div>
  );
}
