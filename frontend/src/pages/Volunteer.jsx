import { useState } from "react";
import { MaskedLines } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { submitVolunteer } from "@/lib/api";
import { recordConsent } from "@/lib/platformApi";
import ConsentNotice from "@/components/platform/ConsentNotice";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import Eyebrow from "@/components/Eyebrow";
import AccessCodeReveal from "@/components/AccessCodeReveal";
import { ArrowDown, Check, Sparkles } from "lucide-react";
import { gsap, useGsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";

const STATES = [
  "Andhra Pradesh",
  "Assam",
  "Bihar",
  "Delhi",
  "Gujarat",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Punjab",
  "Rajasthan",
  "Tamil Nadu",
  "Telangana",
  "Uttar Pradesh",
  "West Bengal",
  "Other",
];
const PROFESSIONS = [
  "Student",
  "Professional",
  "Educator",
  "Lawyer",
  "Designer / Creator",
  "Entrepreneur",
  "Homemaker",
  "Other",
];

const EMPTY = { name: "", email: "", phone: "", state: "", profession: "", reason: "" };

const BENEFITS = [
  "Flexible, remote-friendly roles",
  "Learn real civic skills",
  "Meet like-minded changemakers",
];

/*
 * The four things volunteers actually do. This exists to give the hero's right
 * column something concrete to hold: the left side is the pitch, so the right
 * side answers the question the pitch provokes ("fit doing what, exactly?")
 * rather than repeating it.
 */
/*
 * The nine volunteer areas the movement actually recruits for. This is the
 * canonical list from the campaign brief -- do not paraphrase or regroup it.
 *
 * Note these are displayed only. The signup form currently records `profession`,
 * not area, so a volunteer cannot yet pick one of these; wiring that up needs a
 * new field on the backend's VolunteerCreate model. Until then this panel sets
 * expectations rather than capturing a choice.
 */
const AREAS = [
  "Research",
  "Content Writing",
  "Graphic Design",
  "Social Media",
  "Legal Research",
  "RTI & Policy Research",
  "Event Coordination",
  "Technology & Development",
  "Community Outreach",
];

// The hero's scroll cue and the form section share this anchor.
const FORM_ANCHOR = "volunteer-signup";

export default function Volunteer() {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [result, setResult] = useState(null);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const reduced = prefersReducedMotion();

  /*
   * Scoped to the hero section. The h1 is deliberately not a target -- MaskedLines
   * runs its own masked reveal on the heading lines and a parent tween would
   * fight it.
   */
  const introRef = useGsap(() => {
    gsap.from("[data-intro]", {
      opacity: 0,
      y: reduced ? 0 : 24,
      duration: 0.6,
      stagger: 0.09,
      ease: EASE_OUT,
    });
  }, []);

  /*
   * Scoped to the form section. The success panel is only mounted once `done`
   * flips, so this re-runs on that change rather than on first render.
   */
  const successRef = useGsap(() => {
    const tl = gsap.timeline();
    tl.from("[data-panel]", { opacity: 0, scale: 0.95, duration: 0.4, ease: EASE_OUT });
    tl.from(
      "[data-anim]",
      { opacity: 0, y: reduced ? 0 : 14, duration: 0.45, stagger: 0.07, ease: EASE_OUT },
      "-=0.2"
    );
  }, [done]);

  // DPDP Act 2023: consent must be informed and specific, so the submit button
  // stays disabled until the notice next to it has been agreed to.
  const [consented, setConsented] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const required = ["name", "email", "phone", "state", "profession", "reason"];
    for (const r of required) if (!form[r]) return toast.error("Please fill in all fields");
    if (!consented) return toast.error("Please read and agree to the data notice first.");
    setLoading(true);
    try {
      const res = await submitVolunteer(form);
      // Recorded after the signup succeeds, so no consent row exists for a
      // submission that failed. Never blocks the signup itself.
      recordConsent(form.email, ["volunteering"], "volunteer-signup");
      setResult(res);
      setDone(true);
      toast.success("Thank you! We'll be in touch soon.");
    } catch (err) {
      const msg =
        err?.response?.data?.detail?.[0]?.msg || "Something went wrong. Please try again.";
      toast.error(typeof msg === "string" ? msg : "Please check your details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="volunteer-page">
      {/*
       * SECTION 1 -- the pitch, exactly one viewport, no form.
       *
       * A 12-column split rather than 50/50: the heading needs the wider measure
       * (7 cols) and the areas panel reads fine at 5. The benefits strip is a
       * third grid child spanning all 12, which lands it as a full-width footer
       * rule under both columns without a second wrapper.
       *
       * No extra top padding here -- full-section-hero already reserves 6rem for
       * the fixed navbar, and stacking pt-* on top drops content below the fold.
       */}
      <section className="full-section-hero px-6 md:px-12">
        <div
          ref={introRef}
          className="mx-auto grid w-full max-w-7xl items-start gap-10 lg:grid-cols-12 lg:gap-x-16 lg:gap-y-14"
        >
          {/*
           * Widened to 8 of 12 columns: at 7 the display-size heading broke into
           * four very short lines ("Give a few" / "hours." / ...), which read as a
           * wrapping accident rather than a deliberate break. Two lines at this
           * width is the intended rhythm.
           */}
          <div className="lg:col-span-8">
            <Eyebrow data-intro>Volunteer</Eyebrow>
            <h1 className="mt-5 font-heading text-title-1 font-semibold">
              <MaskedLines lines={["Give a few hours.", "Change the conversation."]} />
            </h1>
            <p data-intro className="mt-6 max-w-2xl text-lead text-foreground/70">
              No experience needed. Whether you're a student, designer, teacher, or just curious,
              there's a role for you. We'll guide you every step of the way.
            </p>

            {/* Scroll cue: the form lives in the next section, so the hero has to point at it. */}
            <div data-intro className="mt-9 flex flex-wrap items-center gap-x-5 gap-y-3">
              <LinkButton href={`#${FORM_ANCHOR}`} variant="secondary">
                Sign up below <ArrowDown className="h-4 w-4" aria-hidden="true" />
              </LinkButton>
              <span className="text-meta text-muted-foreground">
                Six fields, about two minutes.
              </span>
            </div>
          </div>

          {/*
           * Right anchor. Header band plus gap-px rows over bg-border: the
           * dividers are drawn by the grid gap, so no row carries its own border
           * and the hairlines stay exactly 1px at every zoom level.
           */}
          <div data-intro className="overflow-hidden rounded border border-border lg:col-span-4">
            <div className="flex items-center justify-between gap-4 bg-muted/40 px-5 py-3">
              <p className="text-label font-bold uppercase text-muted-foreground">
                Where you'd fit
              </p>
              <span className="text-micro font-bold uppercase text-muted-foreground">
                {AREAS.length} areas
              </span>
            </div>
            {/*
             * One row per area, single column at this narrower span. Names only,
             * no description line: nine descriptions would overflow the viewport
             * and the labels are self-explanatory.
             */}
            <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-1">
              {AREAS.map((area, i) => (
                <div key={area} className="flex items-baseline gap-3 bg-card px-5 py-3.5">
                  <span className="font-heading text-micro font-bold text-muted-foreground">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <p className="font-heading text-body font-bold">{area}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Full-width benefits strip closing the viewport. */}
          <div
            data-intro
            className="grid gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-3 lg:col-span-12"
          >
            {BENEFITS.map((p) => (
              <div key={p} className="flex items-center gap-3 bg-card px-5 py-4">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-primary">
                  <Check className="h-3.5 w-3.5 text-primary-foreground" aria-hidden="true" />
                </span>
                <span className="text-body-sm text-foreground/80">{p}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/*
       * SECTION 2 -- the form. Content-height, not a second viewport: a form is
       * as tall as it is and centring it in 100svh would strand it. scroll-mt
       * clears the fixed navbar when the hero's cue jumps here.
       */}
      <section id={FORM_ANCHOR} className="scroll-mt-24 px-6 py-20 md:px-12 md:py-28">
        <div ref={successRef} className="mx-auto w-full max-w-2xl">
          {done ? (
            <div data-panel className="flex flex-col items-center gap-6">
              <div className="flex flex-col items-center gap-4 rounded border border-border bg-card p-12 text-center">
                <div
                  data-anim
                  className="flex h-16 w-16 items-center justify-center rounded bg-primary"
                >
                  <Sparkles className="h-8 w-8 text-primary-foreground" aria-hidden="true" />
                </div>
                <h2 data-anim className="font-heading text-title-2 font-semibold">
                  You're on the list!
                </h2>
                <p data-anim className="text-body text-muted-foreground">
                  Thanks for stepping up. Our team will reach out with next steps soon.
                </p>
              </div>

              {result?.access_code && (
                <div data-anim className="w-full">
                  <AccessCodeReveal code={result.access_code} email={form.email} />
                </div>
              )}

              <DynamicButton
                data-anim
                variant="outline"
                onClick={() => {
                  setForm(EMPTY);
                  setResult(null);
                  setDone(false);
                }}
              >
                Submit another
              </DynamicButton>
            </div>
          ) : (
            <>
              <div className="mb-8">
                <Eyebrow>Sign up</Eyebrow>
                <h2 className="mt-4 font-heading text-title-2 font-semibold">
                  Tell us about yourself
                </h2>
                <p className="mt-3 text-body text-foreground/70">
                  We use this to match you with a role near you. Nothing is shared publicly.
                </p>
              </div>

              <form
                onSubmit={submit}
                data-testid="volunteer-form"
                className="space-y-5 rounded border border-border bg-card p-6 md:p-8"
              >
                <div className="grid gap-5 sm:grid-cols-2">
                  <Field label="Full name">
                    <Input
                      data-testid="volunteer-name"
                      value={form.name}
                      onChange={set("name")}
                      placeholder="Your name"
                      className="h-12 rounded"
                    />
                  </Field>
                  <Field label="Email">
                    <Input
                      data-testid="volunteer-email"
                      type="email"
                      value={form.email}
                      onChange={set("email")}
                      placeholder="you@email.com"
                      className="h-12 rounded"
                    />
                  </Field>
                </div>
                <div className="grid gap-5 sm:grid-cols-2">
                  <Field label="Phone">
                    <Input
                      data-testid="volunteer-phone"
                      value={form.phone}
                      onChange={set("phone")}
                      placeholder="+91 …"
                      className="h-12 rounded"
                    />
                  </Field>
                  <Field label="State">
                    <Select
                      testid="volunteer-state"
                      value={form.state}
                      onChange={set("state")}
                      options={STATES}
                      placeholder="Select state"
                    />
                  </Field>
                </div>
                <Field label="Profession">
                  <Select
                    testid="volunteer-profession"
                    value={form.profession}
                    onChange={set("profession")}
                    options={PROFESSIONS}
                    placeholder="Select profession"
                  />
                </Field>
                <Field label="Why do you want to join?">
                  <Textarea
                    data-testid="volunteer-reason"
                    value={form.reason}
                    onChange={set("reason")}
                    placeholder="Tell us what accountability means to you…"
                    rows={4}
                    className="rounded"
                  />
                </Field>
                <ConsentNotice purpose="volunteering" onChange={setConsented} />
                <DynamicButton
                  type="submit"
                  loading={loading}
                  disabled={!consented}
                  variant="secondary"
                  className="h-11 w-full"
                  data-testid="volunteer-submit"
                >
                  Become a Volunteer
                </DynamicButton>
              </form>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

const Field = ({ label, children }) => (
  <label className="block">
    <Eyebrow as="span" className="mb-2 block text-muted-foreground">
      {label}
    </Eyebrow>
    {children}
  </label>
);

const Select = ({ testid, value, onChange, options, placeholder }) => (
  <select
    data-testid={testid}
    value={value}
    onChange={onChange}
    className="h-12 w-full rounded border border-input bg-background px-4 text-body text-foreground outline-none focus:ring-2 focus:ring-secondary"
  >
    <option value="">{placeholder}</option>
    {options.map((o) => (
      <option key={o} value={o}>
        {o}
      </option>
    ))}
  </select>
);
