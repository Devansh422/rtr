import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill, SourceLink } from "@/components/platform/Primitives";
import ShareButtons from "@/components/ShareButtons";
import { getPetition, getPetitionSignatures } from "@/lib/platformApi";
import { signPetition, withdrawSignature, listMyPetitions } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, Check } from "lucide-react";

export default function PetitionDetail() {
  const { slug } = useParams();
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [petition, setPetition] = useState(null);
  const [signatures, setSignatures] = useState(null);
  const [hasSigned, setHasSigned] = useState(false);
  const [comment, setComment] = useState("");
  const [showName, setShowName] = useState(false);
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState("loading");

  const load = () => {
    getPetition(slug)
      .then((data) => {
        setPetition(data);
        setState("ready");
      })
      .catch(() => setState("missing"));
    getPetitionSignatures(slug).then(setSignatures);
  };

  useEffect(load, [slug]);

  useEffect(() => {
    if (memberStatus !== "in") return;
    listMyPetitions()
      .then((mine) => setHasSigned(mine.signed?.some((p) => p.slug === slug)))
      .catch(() => {});
  }, [memberStatus, slug]);

  const sign = async () => {
    setBusy(true);
    try {
      const result = await signPetition(slug, { comment, show_my_name: showName });
      setHasSigned(true);
      setComment("");
      toast.success(
        result.commentPending
          ? "Signed. Your comment is waiting for a moderator, but your signature counts now."
          : "Signed. Thank you.",
        { duration: 8000 }
      );
      load();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      toast.error(
        detail?.flags?.[0]?.explanation ??
          (typeof detail === "string" ? detail : "Could not record that signature.")
      );
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    setBusy(true);
    try {
      await withdrawSignature(slug);
      setHasSigned(false);
      toast.success("Your signature has been removed.");
      load();
    } catch {
      toast.error("Could not withdraw that signature.");
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") {
    return (
      <Section>
        <p className="text-body text-foreground/60">{t("common.loading")}</p>
      </Section>
    );
  }
  if (state === "missing") {
    return (
      <Section>
        <EmptyState
          title="Petition not found"
          body="It may still be in moderation, or it may have been withdrawn."
          action={<LinkButton to="/petitions">All petitions</LinkButton>}
        />
      </Section>
    );
  }

  const canSign = petition.status === "open";

  return (
    <div data-testid={`petition-detail-${petition.slug}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-4xl">
          <Link
            to="/petitions"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.petitions")}
          </Link>

          <div className="mt-6 flex flex-wrap gap-2">
            {petition.isOfficial ? <Pill tone="secondary">Official petition</Pill> : null}
            <Pill tone="muted">{petition.statusLabel}</Pill>
            {petition.state ? <Pill tone="muted">{petition.state}</Pill> : null}
          </div>

          <h1 className="mt-5 font-heading text-title-1 font-semibold leading-[1.05] tracking-tighter">
            {petition.title}
          </h1>
          <p className="mt-5 text-lead text-foreground/75">{petition.summary}</p>
          <p className="mt-6 text-body">
            <span className="text-foreground/60">Addressed to: </span>
            <strong className="font-heading font-semibold">{petition.addressedTo}</strong>
          </p>
        </div>
      </section>

      <Section>
        <div className="mx-auto grid w-full max-w-6xl gap-10 lg:grid-cols-[1fr_340px]">
          {/* The text of the petition. */}
          <div>
            <div className="space-y-4">
              {petition.body
                .split("\n\n")
                .filter(Boolean)
                .map((paragraph, index) => (
                  <p key={index} className="text-body leading-relaxed text-foreground/85">
                    {paragraph}
                  </p>
                ))}
            </div>

            {petition.statusNote ? (
              <div className="mt-8 rounded border border-border bg-muted/40 p-5">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  Latest update
                </p>
                <p className="mt-2 text-body text-foreground/80">{petition.statusNote}</p>
                {petition.outcomeSourceUrl ? (
                  <SourceLink
                    citation={{ url: petition.outcomeSourceUrl, title: "Evidence" }}
                    className="mt-3"
                  />
                ) : null}
              </div>
            ) : null}

            {/* Milestones. Small first ones on purpose: a progress bar whose first
                marker is 10,000 tells a petition with 40 signatures it has failed. */}
            {petition.milestones?.length ? (
              <div className="mt-8">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  Milestones reached
                </p>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {petition.milestones.map((milestone) => (
                    <li key={milestone.count}>
                      <Pill tone="primary">
                        <Check className="mr-1 h-3 w-3" aria-hidden="true" />
                        {milestone.count.toLocaleString("en-IN")} on{" "}
                        {new Date(milestone.reachedAt).toLocaleDateString()}
                      </Pill>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {signatures?.items?.length ? (
              <div className="mt-10">
                <h2 className="font-heading text-title-4 font-semibold tracking-tight">
                  Signers who chose to be listed
                </h2>
                <p className="mt-1 text-meta text-foreground/60">{signatures.note}</p>
                <ul className="mt-4 space-y-3">
                  {signatures.items.map((signature, index) => (
                    <li key={index} className="rounded border border-border bg-card p-4">
                      <p className="font-heading text-body font-semibold tracking-tight">
                        {signature.displayName}
                        {signature.state ? (
                          <span className="ml-2 font-normal text-foreground/60">
                            {signature.state}
                          </span>
                        ) : null}
                      </p>
                      {signature.comment ? (
                        <p className="mt-1 text-body text-foreground/75">{signature.comment}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          {/* Sign panel. */}
          <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            <div className="rounded border border-border bg-card p-6">
              <p className="font-heading text-title-2 font-semibold tracking-tight">
                {petition.signatureCount.toLocaleString("en-IN")}
              </p>
              <p className="text-meta text-foreground/60">
                {t("petitions.signatures")} of {petition.targetSignatures.toLocaleString("en-IN")}{" "}
                {t("petitions.target")}
              </p>
              <div className="mt-3 h-2 overflow-hidden rounded bg-muted" aria-hidden="true">
                <div
                  className="h-full rounded bg-primary transition-all"
                  style={{ width: `${petition.progressPercent}%` }}
                />
              </div>

              {memberStatus !== "in" ? (
                <div className="mt-6">
                  <LinkButton to="/login" className="w-full">
                    Sign in to sign
                  </LinkButton>
                  <p className="mt-3 text-meta text-foreground/60">
                    Every signature is tied to a verified member account and counted once. That is
                    what makes this number worth handing to an office.
                  </p>
                </div>
              ) : hasSigned ? (
                <div className="mt-6">
                  <p className="flex items-center gap-2 text-body font-medium text-primary">
                    <Check className="h-4 w-4" aria-hidden="true" />
                    {t("petitions.signed")}
                  </p>
                  <DynamicButton
                    variant="ghost"
                    size="sm"
                    className="mt-3 w-full"
                    onClick={withdraw}
                    disabled={busy}
                  >
                    {t("petitions.withdraw")}
                  </DynamicButton>
                </div>
              ) : canSign ? (
                <div className="mt-6 space-y-4">
                  <div>
                    <Label htmlFor="petition-comment">Add a comment (optional)</Label>
                    <Textarea
                      id="petition-comment"
                      rows={3}
                      maxLength={1000}
                      value={comment}
                      onChange={(event) => setComment(event.target.value)}
                      placeholder="Why this matters where you live"
                      data-testid="signature-comment"
                    />
                  </div>
                  <label htmlFor="show-name" className="flex cursor-pointer items-start gap-3">
                    <Checkbox
                      id="show-name"
                      checked={showName}
                      onCheckedChange={(value) => setShowName(value === true)}
                    />
                    <span className="text-meta text-foreground/80">
                      List my display name publicly. Your signature is counted either way &mdash;
                      this only controls whether you appear in the list.
                    </span>
                  </label>
                  <DynamicButton
                    className="w-full"
                    onClick={sign}
                    disabled={busy}
                    data-testid="sign-petition"
                  >
                    {busy ? "Signing..." : t("petitions.sign")}
                  </DynamicButton>
                </div>
              ) : (
                <p className="mt-6 text-body text-foreground/60">
                  This petition is {petition.statusLabel.toLowerCase()} and is no longer collecting
                  signatures.
                </p>
              )}
            </div>

            {petition.share ? (
              <div className="rounded border border-border bg-card p-6">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  {t("common.share")}
                </p>
                <div className="mt-3">
                  <ShareButtons
                    url={petition.share.copy}
                    title={`${petition.title} - sign this petition`}
                  />
                </div>
              </div>
            ) : null}
          </aside>
        </div>
      </Section>
    </div>
  );
}
