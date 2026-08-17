import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Reveal, MaskedLines } from "@/components/motion/Reveal";
import { Section, SectionHeading, Pill, SourceLink } from "@/components/platform/Primitives";
import StateSignatureSections from "@/components/platform/StateSignatureSections";
import ConsentNotice from "@/components/platform/ConsentNotice";
import AccessCodeReveal from "@/components/AccessCodeReveal";
import ShareButtons from "@/components/ShareButtons";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import {
  getNationalPetition,
  getPetitionSignatures,
  recordConsent,
  signPetitionPublicly,
} from "@/lib/platformApi";
import { listMyPetitions, setMemberToken, signPetition, withdrawSignature } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { Check, ShieldCheck, PenLine } from "lucide-react";

/*
 * The common cause: one national petition, signed on one page.
 *
 * WHY THIS PAGE EXISTS SEPARATELY FROM /petitions. The directory answers "what
 * petitions are open"; almost nobody arrives asking that. They arrive from a
 * WhatsApp message about the demand itself, and the page they land on has one
 * job -- let them sign it -- so this one leads with the ask, the count and the
 * form, and keeps the directory for people who want to browse.
 *
 * THE SIGNING PATH. A visitor with no account fills in one form and is signed
 * and joined in a single request (`POST /petitions/{slug}/sign-public`), which
 * returns a member token this page stores immediately: they can withdraw the
 * signature they just made without hunting for an access code in an inbox. A
 * signed-in member gets the one-click version. Both land in the same table
 * behind the same uniqueness constraint -- see the backend module docstring for
 * why that constraint is the whole point.
 */

const EMPTY_FORM = { name: "", email: "", stateCode: "", city: "", comment: "" };

export default function CommonCause() {
  const { t } = useLocale();
  const { status: memberStatus, profile, refresh } = useMemberAuth();

  const [petition, setPetition] = useState(null);
  const [signatures, setSignatures] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | missing
  const [hasSigned, setHasSigned] = useState(false);
  const [selectedCode, setSelectedCode] = useState(null);

  const [form, setForm] = useState(EMPTY_FORM);
  const [showName, setShowName] = useState(false);
  const [consented, setConsented] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const signRef = useRef(null);

  const load = useCallback(() => {
    getNationalPetition()
      .then((data) => {
        setPetition(data);
        setState("ready");
        getPetitionSignatures(data.slug).then(setSignatures);
      })
      .catch(() => setState("missing"));
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    if (memberStatus !== "in") return;
    listMyPetitions()
      .then((mine) => setHasSigned(Boolean(mine.signed?.some((p) => p.isNational))))
      .catch(() => {});
  }, [memberStatus, petition?.slug]);

  const states = useMemo(() => petition?.stateBreakdown?.states ?? [], [petition]);

  /* The supporter record stores the state as free text (a name), so a member's
     own state is matched back to a code rather than assumed to be one. */
  const memberStateCode = useMemo(() => {
    const named = profile?.supporter?.state;
    if (!named) return "";
    return states.find((row) => row.name.toLowerCase() === named.toLowerCase())?.code ?? "";
  }, [profile, states]);

  useEffect(() => {
    if (memberStateCode && !selectedCode) setSelectedCode(memberStateCode);
  }, [memberStateCode, selectedCode]);

  const scrollToForm = (code) => {
    if (code) {
      setSelectedCode(code);
      setForm((current) => ({ ...current, stateCode: code }));
    }
    signRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const showError = (error, fallback) => {
    const detail = error?.response?.data?.detail;
    toast.error(
      detail?.flags?.[0]?.explanation ??
        detail?.message ??
        (typeof detail === "string" ? detail : fallback)
    );
  };

  const signAsMember = async () => {
    setBusy(true);
    try {
      await signPetition(petition.slug, {
        comment: form.comment,
        show_my_name: showName,
        // Only ever fills a gap: the backend refuses to overwrite a state the
        // member has already recorded.
        state_code: form.stateCode || selectedCode || undefined,
      });
      setHasSigned(true);
      setForm(EMPTY_FORM);
      toast.success("Signed. Thank you.");
      load();
    } catch (error) {
      showError(error, "Could not record that signature.");
    } finally {
      setBusy(false);
    }
  };

  const signAsVisitor = async (event) => {
    event.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.stateCode) {
      return toast.error("Please fill in your name, email and state.");
    }
    if (!consented) {
      return toast.error("Please read and agree to the data notice before signing.");
    }
    setBusy(true);
    const email = form.email.trim();
    try {
      const response = await signPetitionPublicly(petition.slug, {
        name: form.name.trim(),
        email,
        state_code: form.stateCode,
        city: form.city.trim() || null,
        comment: form.comment,
        show_my_name: showName,
        consent: true,
      });
      // Signing signed them in. Stored before the consent write and before the
      // reload, so nothing later in this function can leave them holding a
      // signature they cannot manage.
      setMemberToken(response.memberToken);
      await refresh();
      recordConsent(email, ["membership"], "petition-sign");

      // The address is carried on the result because the form is cleared in the
      // same update, and the access-code panel has to say which account it is for.
      setResult({ ...response, email });
      setHasSigned(true);
      setSelectedCode(response.state ?? selectedCode);
      setForm(EMPTY_FORM);
      setConsented(false);
      load();
    } catch (error) {
      showError(error, "Could not record that signature.");
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    setBusy(true);
    try {
      await withdrawSignature(petition.slug);
      setHasSigned(false);
      setResult(null);
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
        <div className="rounded border border-dashed border-border bg-card/50 p-10 text-center">
          <p className="font-heading text-lead font-semibold tracking-tight">
            The national petition is not open on this deployment yet.
          </p>
          <p className="mx-auto mt-2 max-w-lg text-body text-foreground/70">
            It is created when the platform starts up. In the meantime, every petition started by
            members is in the directory.
          </p>
          <div className="mt-6 flex justify-center">
            <LinkButton to="/petitions">All petitions</LinkButton>
          </div>
        </div>
      </Section>
    );
  }

  const breakdown = petition.stateBreakdown;
  const remaining = petition.nextMilestone
    ? petition.nextMilestone - petition.signatureCount
    : null;
  const signedIn = memberStatus === "in";

  return (
    <div data-testid="common-cause-page">
      {/* ---------------- Hero: the ask and the count ---------------- */}
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto grid w-full max-w-7xl gap-12 lg:grid-cols-[1fr_380px] lg:items-end">
          <div>
            <p className="text-label font-bold uppercase text-secondary">
              {t("commonCause.eyebrow")}
            </p>
            <h1 className="mt-6 font-heading text-title-1 font-semibold leading-[0.95] tracking-tighter">
              <MaskedLines lines={["One demand.", "One petition.", "Every state."]} />
            </h1>
            <p className="mt-8 max-w-3xl text-lead text-foreground/70">{petition.summary}</p>

            <div className="mt-8 flex flex-wrap gap-2">
              <Pill tone="secondary">Official petition</Pill>
              <Pill tone="muted">{petition.statusLabel}</Pill>
              <Pill tone="muted">Open to every state and union territory</Pill>
            </div>

            <p className="mt-8 text-body">
              <span className="text-foreground/60">Addressed to: </span>
              <strong className="font-heading font-semibold">{petition.addressedTo}</strong>
            </p>
          </div>

          {/* The counter. Leads with the next milestone rather than the percentage
              of the final target: "412 more to 5,000" is something a reader can
              act on this afternoon; "3% of 100,000" tells them not to bother. */}
          <div className="rounded border border-border bg-card p-6" data-testid="signature-counter">
            <p className="font-heading text-[3.5rem] font-semibold leading-none tracking-tighter text-primary">
              {petition.signatureCount.toLocaleString("en-IN")}
            </p>
            <p className="mt-2 text-body text-foreground/70">
              {t("petitions.signatures")} from {breakdown.statesWithSignatures} of{" "}
              {breakdown.totalStates} states and union territories
            </p>

            <div className="mt-5 h-2 overflow-hidden rounded bg-muted" aria-hidden="true">
              <div
                className="h-full rounded bg-primary transition-all"
                style={{ width: `${petition.progressPercent}%` }}
              />
            </div>
            <p className="mt-2 text-meta text-foreground/60">
              {remaining !== null
                ? `${remaining.toLocaleString("en-IN")} more to reach ${petition.nextMilestone.toLocaleString("en-IN")}`
                : `Target of ${petition.targetSignatures.toLocaleString("en-IN")} passed`}
            </p>

            <DynamicButton className="mt-6 w-full" onClick={() => scrollToForm()} data-testid="hero-sign">
              <PenLine className="h-4 w-4" aria-hidden="true" />
              {hasSigned ? "You have signed - share it" : t("commonCause.sign")}
            </DynamicButton>
            <p className="mt-3 text-meta text-foreground/60">
              One signature per verified account, enforced by the database. Your name is published
              only if you ask for it.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- The text, and the form ---------------- */}
      <Section>
        <div className="grid gap-12 lg:grid-cols-[1fr_400px]">
          <div>
            <h2 className="font-heading text-title-2 font-semibold tracking-tight">
              {petition.title}
            </h2>
            <div className="mt-6 space-y-5">
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
              <div className="mt-12">
                <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                  Signers who chose to be listed
                </h3>
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

          {/* ---- Sign panel ---- */}
          <aside ref={signRef} className="lg:sticky lg:top-24 lg:self-start" id="sign">
            {result ? (
              <div className="space-y-4" data-testid="signed-panel">
                <div className="rounded border border-secondary bg-secondary/10 p-6">
                  <p className="flex items-center gap-2 font-heading text-title-4 font-semibold tracking-tight">
                    <Check className="h-5 w-5 text-secondary" aria-hidden="true" />
                    Signature {result.signatureCount.toLocaleString("en-IN")} recorded
                  </p>
                  <p className="mt-2 text-body text-foreground/75">
                    {result.nextMilestone
                      ? `${(result.nextMilestone - result.signatureCount).toLocaleString("en-IN")} more signatures and this petition passes ${result.nextMilestone.toLocaleString("en-IN")}. The fastest way there is the person you send this to next.`
                      : "Thank you. The fastest way to the next milestone is the person you send this to next."}
                  </p>
                  {result.commentPending ? (
                    <p className="mt-3 text-meta text-foreground/70">
                      Your comment is with a moderator. Your signature counts either way.
                    </p>
                  ) : null}
                  <div className="mt-5">
                    <ShareButtons
                      url={petition.share?.copy}
                      title={`${petition.title} - sign this petition`}
                    />
                  </div>
                </div>

                {result.accessCode ? (
                  <AccessCodeReveal code={result.accessCode} email={result.email} />
                ) : null}

                <div className="rounded border border-border bg-card p-5">
                  <p className="text-meta leading-relaxed text-foreground/70">
                    You are signed in on this device. Your dashboard shows everything you have
                    signed, and lets you withdraw any of it.
                  </p>
                  <LinkButton to="/dashboard" variant="outline" className="mt-4 w-full">
                    Go to my dashboard
                  </LinkButton>
                </div>
              </div>
            ) : hasSigned ? (
              <div className="rounded border border-border bg-card p-6" data-testid="already-signed">
                <p className="flex items-center gap-2 text-body font-medium text-primary">
                  <Check className="h-4 w-4" aria-hidden="true" />
                  {t("petitions.signed")}
                </p>
                <p className="mt-3 text-meta text-foreground/70">
                  Share it with the people who would sign it if they knew it existed.
                </p>
                <div className="mt-4">
                  <ShareButtons
                    url={petition.share?.copy}
                    title={`${petition.title} - sign this petition`}
                  />
                </div>
                <DynamicButton
                  variant="ghost"
                  size="sm"
                  className="mt-5 w-full"
                  onClick={withdraw}
                  disabled={busy}
                >
                  {t("petitions.withdraw")}
                </DynamicButton>
              </div>
            ) : signedIn ? (
              <div className="rounded border border-border bg-card p-6" data-testid="member-sign">
                <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                  {t("commonCause.sign")}
                </h3>
                <p className="mt-2 text-meta text-foreground/70">
                  Signed in as {profile?.supporter?.name ?? profile?.email}.
                </p>

                {!memberStateCode ? (
                  <div className="mt-4">
                    <Label htmlFor="member-state">Your state</Label>
                    <StateSelect
                      id="member-state"
                      states={states}
                      value={form.stateCode || selectedCode || ""}
                      onChange={(code) => {
                        setForm({ ...form, stateCode: code });
                        setSelectedCode(code);
                      }}
                    />
                    <p className="mt-1.5 text-meta text-foreground/55">
                      Recorded once, so your signature counts towards your state.
                    </p>
                  </div>
                ) : null}

                <div className="mt-4">
                  <Label htmlFor="member-comment">Add a comment (optional)</Label>
                  <Textarea
                    id="member-comment"
                    rows={3}
                    maxLength={1000}
                    value={form.comment}
                    onChange={(event) => setForm({ ...form, comment: event.target.value })}
                    placeholder="Why this matters where you live"
                  />
                </div>

                <ShowNameToggle checked={showName} onChange={setShowName} idSuffix="member" />

                <DynamicButton
                  className="mt-4 w-full"
                  onClick={signAsMember}
                  disabled={busy}
                  data-testid="member-sign-button"
                >
                  {busy ? "Signing..." : t("commonCause.sign")}
                </DynamicButton>
              </div>
            ) : (
              <form
                onSubmit={signAsVisitor}
                className="rounded border border-border bg-card p-6"
                data-testid="public-sign-form"
              >
                <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                  {t("commonCause.sign")}
                </h3>
                <p className="mt-2 text-meta text-foreground/70">
                  No separate signup. Signing creates your member account and signs you in on this
                  device.
                </p>

                <div className="mt-5 space-y-4">
                  <div>
                    <Label htmlFor="sign-name">Full name *</Label>
                    <Input
                      id="sign-name"
                      value={form.name}
                      onChange={(event) => setForm({ ...form, name: event.target.value })}
                      placeholder="Your name"
                      data-testid="sign-name"
                    />
                  </div>
                  <div>
                    <Label htmlFor="sign-email">Email *</Label>
                    <Input
                      id="sign-email"
                      type="email"
                      value={form.email}
                      onChange={(event) => setForm({ ...form, email: event.target.value })}
                      placeholder="you@email.com"
                      data-testid="sign-email"
                    />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="sign-state">State *</Label>
                      <StateSelect
                        id="sign-state"
                        states={states}
                        value={form.stateCode}
                        onChange={(code) => {
                          setForm({ ...form, stateCode: code });
                          setSelectedCode(code);
                        }}
                      />
                    </div>
                    <div>
                      <Label htmlFor="sign-city">City (optional)</Label>
                      <Input
                        id="sign-city"
                        value={form.city}
                        onChange={(event) => setForm({ ...form, city: event.target.value })}
                        placeholder="Your city"
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="sign-comment">Add a comment (optional)</Label>
                    <Textarea
                      id="sign-comment"
                      rows={3}
                      maxLength={1000}
                      value={form.comment}
                      onChange={(event) => setForm({ ...form, comment: event.target.value })}
                      placeholder="Why this matters where you live"
                    />
                  </div>
                </div>

                <ShowNameToggle checked={showName} onChange={setShowName} idSuffix="public" />

                <ConsentNotice purpose="membership" onChange={setConsented} className="mt-4" />

                <DynamicButton
                  type="submit"
                  className="mt-4 w-full"
                  loading={busy}
                  disabled={!consented}
                  data-testid="public-sign-button"
                >
                  {t("commonCause.sign")}
                </DynamicButton>
                <p className="mt-3 text-meta text-foreground/60">
                  Already a member?{" "}
                  <Link to="/login" className="text-primary underline-offset-4 hover:underline">
                    Sign in
                  </Link>{" "}
                  and sign in one click.
                </p>
              </form>
            )}
          </aside>
        </div>
      </Section>

      {/* ---------------- State-wise sections ---------------- */}
      <Section muted testId="state-sections">
        <SectionHeading
          eyebrow={t("commonCause.stateEyebrow")}
          title={t("commonCause.stateHeading")}
          lede="Under Article 328 a state legislature can enact recall for its own members without waiting for Parliament, so the number that matters to a Chief Minister is the one from their own state. Every state and union territory is listed, including the ones still on zero."
        />
        <StateSignatureSections
          className="mt-10"
          breakdown={breakdown}
          selectedCode={selectedCode}
          onSelectState={setSelectedCode}
          onSignForState={hasSigned ? null : scrollToForm}
        />
      </Section>

      {/* ---------------- Why the number can be trusted ---------------- */}
      <Section>
        <Reveal>
          <div className="rounded border border-border bg-card p-8">
            <h2 className="flex items-center gap-2 font-heading text-title-3 font-semibold tracking-tight">
              <ShieldCheck className="h-6 w-6 text-secondary" aria-hidden="true" />
              What this number claims, and what it does not
            </h2>
            <div className="mt-5 grid gap-6 md:grid-cols-2">
              <p className="text-body leading-relaxed text-foreground/70">
                Every signature is tied to a member account and counted once per petition, enforced
                by a constraint in the database rather than by a check the code might skip. A
                petition with fifty thousand signatures that a script can inflate is worth less than
                one with five hundred that cannot &mdash; the first can be dismissed in a sentence
                by the office it is addressed to.
              </p>
              <p className="text-body leading-relaxed text-foreground/70">
                What it does not claim: nobody here has proved they control the email address they
                signed with, because this platform does not yet send confirmation mail. So this is a
                count of accounts, one per person acting in good faith, not a verified electoral
                roll &mdash; and we would rather say so than let the number imply more than it can
                carry.
              </p>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <LinkButton to="/petitions" variant="outline">
                Petitions started by members
              </LinkButton>
              <LinkButton to="/constitution/328" variant="ghost">
                Read Article 328
              </LinkButton>
            </div>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}

/* Native select rather than the shadcn one: 36 options, and this has to be
   usable on a low-end phone where a portalled listbox is the slowest thing on
   the page. Same styling as the join form's state field. */
function StateSelect({ id, states, value, onChange }) {
  return (
    <select
      id={id}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      data-testid={id}
      className="h-10 w-full rounded border border-input bg-background px-3 text-body text-foreground outline-none focus:ring-1 focus:ring-secondary"
    >
      <option value="">Select state</option>
      {states.map((row) => (
        <option key={row.code} value={row.code}>
          {row.name}
        </option>
      ))}
    </select>
  );
}

function ShowNameToggle({ checked, onChange, idSuffix }) {
  const id = `show-name-${idSuffix}`;
  return (
    <label htmlFor={id} className="mt-4 flex cursor-pointer items-start gap-3">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onChange(value === true)}
        className="mt-0.5"
      />
      <span className="text-meta text-foreground/80">
        List my name publicly on this petition. Your signature is counted either way &mdash; this
        only controls whether you appear in the list of signers.
      </span>
    </label>
  );
}
