import { useState } from "react";
import { Download, ExternalLink, FileText, Image as ImageIcon, Paperclip } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/*
 * Reading the actual record, without leaving the page.
 *
 * The module's claim is that every conclusion can be checked against the original
 * document. A link that dumps a citizen into a bare PDF viewer in a new tab
 * technically honours that and practically does not -- they lose the promise they
 * were reading and rarely come back. So the record opens in place, with its
 * provenance beside it, and the original is still one click away.
 *
 * WHAT IS AND IS NOT PREVIEWED. The file is embedded exactly as it is served,
 * never re-rendered or re-encoded (§18): the whole point is that the reader sees
 * the department's own scan. Browsers will refuse to frame plenty of government
 * sites -- X-Frame-Options is common on state portals -- so the fallback below is
 * the expected path for a link to a live gov.in page, not an error case, and it
 * says so rather than showing an empty grey box the reader will read as broken.
 */

const PDF_PATTERN = /\.pdf($|[?#])/i;
const IMAGE_PATTERN = /\.(png|jpe?g|gif|webp|avif)($|[?#])/i;

function fileKind(url) {
  if (!url) return "unknown";
  if (PDF_PATTERN.test(url)) return "pdf";
  if (IMAGE_PATTERN.test(url)) return "image";
  return "unknown";
}

/** The metadata every published record carries (§18). */
function DocumentMeta({ document }) {
  const rows = [
    ["Document ID", document.code],
    ["Type", document.kindLabel],
    ["Issuing authority", document.issuingAuthority],
    ["Department", document.department],
    ["Reference number", document.referenceNumber],
    ["Issued on", document.issuedOn ? new Date(document.issuedOn).toLocaleDateString() : null],
    ["Pages", document.pageCount],
    ["Obtained via", document.obtainedVia === "rti" ? "RTI reply" : document.obtainedVia],
    ["Published by", document.publisher],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");

  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="flex flex-wrap items-baseline gap-2">
          <dt className="text-label font-bold uppercase text-muted-foreground">{label}</dt>
          <dd className="text-meta text-foreground/80">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * The preview dialog.
 *
 * `document` is the API's document envelope. `title`/`url` are accepted directly
 * as well, for the two records that are not GovernmentDocument rows -- the RTI
 * application itself and the covering reply.
 */
export function DocumentPreviewDialog({ open, onOpenChange, document, title, url, sourceNote }) {
  const href = url ?? document?.fileUrl ?? document?.sourceUrl ?? null;
  const heading = title ?? document?.title ?? "Original record";
  const note = sourceNote ?? document?.sourceNote ?? "";
  const kind = fileKind(href);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="pr-8 font-heading text-lead font-semibold tracking-tight">
            {heading}
          </DialogTitle>
          <DialogDescription className="text-meta">
            Shown as issued. This platform stores records unaltered and does not edit the file it
            received.
          </DialogDescription>
        </DialogHeader>

        {document ? (
          <div className="rounded border border-border bg-muted/30 p-4">
            <DocumentMeta document={document} />
          </div>
        ) : null}

        {note ? (
          <p className="text-meta leading-relaxed text-foreground/70">
            <span className="font-semibold text-foreground/80">Where this came from: </span>
            {note}
          </p>
        ) : null}

        {href ? (
          <>
            <div className="overflow-hidden rounded border border-border bg-muted/20">
              {kind === "image" ? (
                <img
                  src={href}
                  alt={heading}
                  className="mx-auto max-h-[60vh] w-auto max-w-full object-contain"
                />
              ) : (
                <iframe
                  src={href}
                  title={`Preview of ${heading}`}
                  className="h-[60vh] w-full"
                  // Same-origin uploads need no privileges; a remote government
                  // PDF gets none either. Nothing in an archived record should be
                  // running script in this page's context.
                  sandbox=""
                />
              )}
            </div>

            <p className="text-meta text-muted-foreground">
              Some government sites do not allow their documents to be shown inside another page. If
              the preview above is blank, open the original directly.
            </p>

            <div className="flex flex-wrap gap-3">
              <Button asChild variant="default" size="sm">
                <a href={href} target="_blank" rel="noreferrer noopener">
                  <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                  Open the original
                </a>
              </Button>
              <Button asChild variant="outline" size="sm">
                <a href={href} download>
                  <Download className="mr-2 h-4 w-4" aria-hidden="true" />
                  Download
                </a>
              </Button>
              {document?.sourceUrl && document.sourceUrl !== href ? (
                <Button asChild variant="ghost" size="sm">
                  <a href={document.sourceUrl} target="_blank" rel="noreferrer noopener">
                    <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                    Where it was published
                  </a>
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <p className="rounded border border-dashed border-border p-6 text-center text-body text-foreground/70">
            No file has been published for this record yet. Its details are listed above.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

/**
 * The clickable attachment: an inline control that opens the record in place.
 *
 * Rendered as a button rather than a link because it does not navigate. Where a
 * document has no file at all it still renders -- as text, not as a dead control
 * -- because "this order exists, we do not hold a copy" is itself information.
 */
export function AttachmentButton({ document, label, url, title, sourceNote, className }) {
  const [open, setOpen] = useState(false);
  const href = url ?? document?.fileUrl ?? document?.sourceUrl ?? null;
  const kind = fileKind(href);
  const Icon = kind === "image" ? ImageIcon : kind === "pdf" ? FileText : Paperclip;
  const text = label ?? document?.title ?? title ?? "View record";

  if (!href && !document) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "inline-flex max-w-full items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-meta font-medium text-foreground/80 transition-colors hover:border-primary/40 hover:text-primary",
          className
        )}
        data-testid="attachment-button"
      >
        <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span className="truncate">{text}</span>
      </button>

      <DocumentPreviewDialog
        open={open}
        onOpenChange={setOpen}
        document={document}
        title={title}
        url={url}
        sourceNote={sourceNote}
      />
    </>
  );
}

/**
 * A government record as a card, for the document register (§11).
 *
 * Every field the brief lists is shown, and the primary/secondary marker comes
 * from the API's own classification of the link rather than from a guess made
 * here: a copy on the department's site and a copy someone re-hosted are not the
 * same evidence, and the reader is told which one they are looking at.
 */
export function DocumentCard({ document, showPromise = true }) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="flex h-full flex-col rounded border border-border bg-card p-5"
      data-testid={`document-${document.code}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <span className="text-label font-bold uppercase text-secondary">{document.kindLabel}</span>
        <span
          className={cn(
            "rounded border px-1.5 py-px text-[10px] uppercase tracking-wide",
            document.isPrimarySource
              ? "border-emerald-600/30 text-emerald-700 dark:text-emerald-400"
              : "border-border text-muted-foreground"
          )}
          title={
            document.isPrimarySource
              ? "Published on an official government domain."
              : "A copy of the record held somewhere other than an official domain."
          }
        >
          {document.isPrimarySource ? "primary source" : "secondary copy"}
        </span>
      </div>

      <p className="mt-3 font-heading text-lead font-semibold leading-snug tracking-tight">
        {document.title}
      </p>

      <dl className="mt-3 space-y-1 text-meta text-foreground/70">
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium text-muted-foreground">Issued by</dt>
          <dd>{document.issuingAuthority}</dd>
        </div>
        {document.referenceNumber ? (
          <div className="flex gap-2">
            <dt className="shrink-0 font-medium text-muted-foreground">Reference</dt>
            <dd className="break-all">{document.referenceNumber}</dd>
          </div>
        ) : null}
        {document.issuedOn ? (
          <div className="flex gap-2">
            <dt className="shrink-0 font-medium text-muted-foreground">Dated</dt>
            <dd>{new Date(document.issuedOn).toLocaleDateString()}</dd>
          </div>
        ) : null}
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium text-muted-foreground">Document ID</dt>
          <dd>{document.code}</dd>
        </div>
      </dl>

      {document.sourceNote ? (
        <p className="mt-3 text-meta leading-relaxed text-foreground/60">{document.sourceNote}</p>
      ) : null}

      {showPromise && document.promise ? (
        <a
          href={document.promise.url}
          className="mt-3 text-meta text-primary underline-offset-4 hover:underline"
        >
          Relates to {document.promise.code} — {document.promise.title}
        </a>
      ) : null}

      <div className="mt-auto pt-4">
        <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
          <FileText className="mr-2 h-4 w-4" aria-hidden="true" />
          View original
        </Button>
      </div>

      <DocumentPreviewDialog open={open} onOpenChange={setOpen} document={document} />
    </div>
  );
}
