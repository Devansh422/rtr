import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill, SourceLink, Disclaimer } from "@/components/platform/Primitives";
import CorrectionDialog from "@/components/platform/CorrectionDialog";
import { getReport } from "@/lib/platformApi";
import { confirmReport } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { ArrowLeft, Users } from "lucide-react";

export default function ReportDetail() {
  const { slug } = useParams();
  const { status: memberStatus } = useMemberAuth();
  const [report, setReport] = useState(null);
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getReport(slug)
      .then((data) => {
        setReport(data);
        setState("ready");
      })
      .catch(() => setState("missing"));
  }, [slug]);

  const confirm = async () => {
    setBusy(true);
    try {
      const result = await confirmReport(slug, "");
      setReport((prev) => ({ ...prev, confirmations: result.confirmations }));
      toast.success("Recorded. Corroboration is what turns an anecdote into data.");
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not record that.");
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") {
    return (
      <Section>
        <p className="text-body text-foreground/60">Loading...</p>
      </Section>
    );
  }
  if (state === "missing") {
    return (
      <Section>
        <EmptyState
          title="Report not found"
          body="It may still be in the moderation queue, or it may not have been published."
          action={<LinkButton to="/reports">All reports</LinkButton>}
        />
      </Section>
    );
  }

  return (
    <div data-testid={`report-detail-${report.slug}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-3xl">
          <Link
            to="/reports"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            Citizen report cards
          </Link>

          <div className="mt-6 flex flex-wrap gap-2">
            <Pill tone="muted">{report.serviceLabel}</Pill>
            <Pill tone={report.status === "resolved" ? "primary" : "muted"}>{report.statusLabel}</Pill>
            {report.rating ? <Pill tone="muted">Rated {report.rating}/5</Pill> : null}
          </div>

          <h1 className="mt-5 font-heading text-title-2 font-semibold leading-[1.1] tracking-tighter">
            {report.title}
          </h1>
          <p className="mt-4 text-body text-foreground/60">
            {[report.locality, report.constituency, report.state].filter(Boolean).join(" · ")}
            {report.filedOn ? ` · filed ${report.filedOn}` : ""}
          </p>
        </div>
      </section>

      <Section>
        <div className="mx-auto w-full max-w-3xl space-y-8">
          <div className="space-y-4">
            {report.body
              .split("\n\n")
              .filter(Boolean)
              .map((paragraph, index) => (
                <p key={index} className="text-body leading-relaxed text-foreground/85">
                  {paragraph}
                </p>
              ))}
          </div>

          {report.verificationNote ? (
            <div className="rounded border border-border bg-muted/40 p-5">
              <p className="text-label font-bold uppercase text-muted-foreground">
                How this was checked
              </p>
              <p className="mt-2 text-body text-foreground/80">{report.verificationNote}</p>
            </div>
          ) : null}

          {/* The other side of the story, given the same prominence. */}
          {report.response ? (
            <div className="rounded border border-primary/30 bg-primary/5 p-6">
              <p className="text-label font-bold uppercase text-primary">
                Response from {report.response.from}
              </p>
              <p className="mt-2 text-body leading-relaxed text-foreground/85">
                {report.response.text}
              </p>
              {report.response.sourceUrl ? (
                <SourceLink
                  citation={{ url: report.response.sourceUrl, title: "The response on the record" }}
                  className="mt-3"
                />
              ) : null}
              {report.response.receivedOn ? (
                <p className="mt-2 text-meta text-foreground/60">
                  Received {report.response.receivedOn}
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-6">
            <span className="inline-flex items-center gap-1.5 text-body">
              <Users className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              {report.confirmations} {report.confirmations === 1 ? "person" : "people"} confirm this
            </span>
            {memberStatus === "in" ? (
              <DynamicButton variant="outline" size="sm" onClick={confirm} disabled={busy}>
                This is happening to me too
              </DynamicButton>
            ) : (
              <LinkButton to="/login" variant="ghost" size="sm">
                Sign in to confirm
              </LinkButton>
            )}
            <CorrectionDialog entityType="report" entityId={report.slug} triggerVariant="ghost" />
          </div>

          <Disclaimer text={report.disclaimer} title="About this report" />
        </div>
      </Section>
    </div>
  );
}
