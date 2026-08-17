import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";

import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { PageHero, Section, EmptyState, Pill } from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import { AttachmentButton } from "@/components/manifesto/DocumentPreview";
import { getManifestoReplies } from "@/lib/platformApi";

/*
 * Every government reply received, newest first (§10).
 *
 * A register of replies rather than of applications, and the difference is not
 * cosmetic: one application can produce a first reply, a transfer under s.6(3)
 * and then an appellate reply, and each of those is a separate statement by a
 * public authority. Listing only the latest would quietly drop what the
 * department said first, which is often the more revealing document.
 *
 * The `summary` field is shown as a note ABOUT the reply, attributed as such. It
 * is a neutral description of what the document is -- never an evaluation of
 * whether the answer was adequate, which belongs in an assessment on the promise
 * page where the records sit beside it.
 */

const formatDate = (value) => (value ? new Date(value).toLocaleDateString() : null);

export default function ManifestoReplies() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getManifestoReplies({ limit: 200 })
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="manifesto-replies-page">
      <PageHero
        eyebrow="Government replies"
        lines={["The replies,", "as received."]}
        lede="Every reply received from a public authority against an RTI filed on a manifesto promise. Each one is published with its reference number and its original document."
      />

      <ModuleNav />

      <Section>
        <p className="text-meta text-foreground/60">
          {loading ? "Loading…" : `${data.total} repl${data.total === 1 ? "y" : "ies"} on file`}
        </p>

        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">Loading…</p>
          ) : data.items.length === 0 ? (
            <EmptyState
              title="No replies published yet"
              body="Replies appear here as public authorities answer the applications filed against published promises. Where the statutory period has passed without a reply, that is recorded on the promise itself."
            />
          ) : (
            <StaggerGroup className="grid gap-4">
              {data.items.map((reply) => (
                <StaggerItem key={reply.id}>
                  <article
                    className="rounded border border-border bg-card p-6"
                    data-testid={`reply-${reply.id}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-mono text-meta text-muted-foreground">
                          {reply.rtiCode}
                          {reply.referenceNumber ? ` · ${reply.referenceNumber}` : ""}
                        </p>
                        <h2 className="mt-1 font-heading text-lead font-semibold tracking-tight">
                          {reply.replyingAuthority}
                        </h2>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {reply.isAppealReply ? <Pill tone="secondary">Appeal reply</Pill> : null}
                        {reply.pageCount ? <Pill tone="muted">{reply.pageCount} pages</Pill> : null}
                      </div>
                    </div>

                    <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                      {[
                        ["Reply dated", formatDate(reply.replyDated)],
                        ["Received on", formatDate(reply.receivedOn)],
                        ["Department", reply.department],
                        ["Reference number", reply.referenceNumber],
                      ]
                        .filter(([, value]) => value)
                        .map(([label, value]) => (
                          <div key={label}>
                            <dt className="text-label font-bold uppercase text-muted-foreground">
                              {label}
                            </dt>
                            <dd className="mt-0.5 text-meta text-foreground/80">{value}</dd>
                          </div>
                        ))}
                    </dl>

                    {reply.summary ? (
                      <p className="mt-4 rounded border border-border bg-muted/30 p-4 text-meta leading-relaxed text-foreground/70">
                        <span className="font-semibold text-foreground/85">
                          Note on this reply:{" "}
                        </span>
                        {reply.summary}
                      </p>
                    ) : null}

                    {reply.promise ? (
                      <Link
                        to={reply.promise.url}
                        className="mt-4 block text-meta text-primary underline-offset-4 hover:underline"
                      >
                        Filed against {reply.promise.code} — {reply.promise.title}
                      </Link>
                    ) : null}

                    {reply.documentUrl ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        <AttachmentButton
                          url={reply.documentUrl}
                          title={`Government reply — ${reply.replyingAuthority}`}
                          label="View the original reply"
                          className="px-3 py-2"
                        />
                        <a
                          href={reply.documentUrl}
                          download
                          className="inline-flex items-center gap-1.5 rounded border border-border bg-card px-3 py-2 text-meta font-medium text-foreground/80 hover:border-primary/40 hover:text-primary"
                        >
                          <Download className="h-3.5 w-3.5" aria-hidden="true" />
                          Download the original
                        </a>
                      </div>
                    ) : (
                      <p className="mt-4 text-meta text-foreground/60">
                        The scan of this reply has not been published yet.
                      </p>
                    )}
                  </article>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>
    </div>
  );
}
