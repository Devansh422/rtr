import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { joinMovement } from "@/lib/api";
import { gsap, EASE, prefersReducedMotion } from "@/lib/motion";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import ExplainerVideo from "@/components/ExplainerVideo";
import SupporterCertificate from "@/components/SupporterCertificate";
import SupporterShare from "@/components/SupporterShare";
import { Check, ArrowRight, PartyPopper, BookOpen } from "lucide-react";

const STATES = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Delhi",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Other",
];
const STEPS = ["Watch", "Pledge", "Details", "Done"];
const PLEDGE = "I support greater accountability in democracy through the Right to Recall.";
const EMPTY = { name: "", state: "", city: "", email: "", mobile: "" };

export default function SupporterFlow() {
  const [stepIndex, setStepIndex] = useState(0);
  const [pledged, setPledged] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const stepRef = useRef(null);
  const partyRef = useRef(null);
  const stepperRef = useRef(null);

  /* Step transition. The wrapper carries key={stepIndex}, so React remounts it
     and this effect re-runs on every step change. */
  useEffect(() => {
    const el = stepRef.current;
    if (!el) return;
    const reduce = prefersReducedMotion();
    const ctx = gsap.context(() => {
      gsap.from(el, {
        opacity: 0,
        y: reduce ? 0 : 16,
        duration: reduce ? 0.2 : 0.5,
        ease: EASE,
      });
      const party = partyRef.current;
      if (party && !reduce) {
        gsap.from(party, {
          scale: 0.6,
          opacity: 0,
          duration: 0.6,
          ease: "back.out(1.7)",
          delay: 0.15,
        });
      }
    }, el);
    return () => ctx.revert();
  }, [stepIndex]);

  /* Small pop on the dot that just became active. */
  useEffect(() => {
    const root = stepperRef.current;
    if (!root || prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      const dot = root.querySelector(`[data-step-dot="${stepIndex}"]`);
      if (dot) gsap.fromTo(dot, { scale: 0.8 }, { scale: 1, duration: 0.4, ease: "back.out(2)" });
    }, root);
    return () => ctx.revert();
  }, [stepIndex]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.state || !form.city || !form.email) {
      return toast.error("Please fill in your name, state, city and email.");
    }
    setLoading(true);
    try {
      const res = await joinMovement({ ...form, pledge: true });
      setResult(res);
      setStepIndex(3);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const msg = err?.response?.data?.detail?.[0]?.msg;
      toast.error(typeof msg === "string" ? msg : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="supporter-flow">
      {/*
       * Exactly one viewport. Each step is sized to fit inside it rather than the
       * page growing, so the stepper stays visible while the reader works through
       * the flow. Steps are individually compact (see the notes below); the only
       * one that can exceed the fold is Done, which has the certificate to show.
       */}
      <section className="flex min-h-svh flex-col justify-center px-6 py-20 md:px-8">
        <div className="mx-auto w-full max-w-3xl">
          {/* Stepper */}
          <div
            ref={stepperRef}
            className="mb-7 flex items-center justify-center gap-2 sm:gap-3"
            data-testid="flow-stepper"
          >
            {STEPS.map((s, i) => (
              <div key={s} className="flex items-center gap-2 sm:gap-4">
                <div className="flex items-center gap-2">
                  <span
                    data-step-dot={i}
                    className={`flex h-7 w-7 items-center justify-center rounded text-micro font-bold transition-colors ${
                      i < stepIndex
                        ? "bg-secondary text-secondary-foreground"
                        : i === stepIndex
                          ? "bg-primary text-primary-foreground"
                          : "border border-border bg-card text-muted-foreground"
                    }`}
                  >
                    {i < stepIndex ? <Check className="h-4 w-4" /> : i + 1}
                  </span>
                  <span
                    className={`hidden text-label font-bold uppercase sm:block ${i === stepIndex ? "text-foreground" : "text-muted-foreground"}`}
                  >
                    {s}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <span
                    className={`h-px w-6 sm:w-10 ${i < stepIndex ? "bg-secondary" : "bg-border"}`}
                  />
                )}
              </div>
            ))}
          </div>

          <div key={stepIndex} ref={stepRef}>
            {/* STEP: WATCH */}
            {stepIndex === 0 && (
              <div>
                <div className="mb-5 text-center">
                  <p className="text-label font-bold uppercase text-secondary">Step 1 · Watch</p>
                  <h1 className="mt-2 font-heading text-title-2 font-bold">
                    What is Right to Recall?
                  </h1>
                  <p className="mt-2 text-body text-foreground/70">
                    A 30-second explainer. Then add your voice.
                  </p>
                </div>
                {/*
                 * Width-capped, not height-capped. The player is an aspect-ratio
                 * box (4:3 on mobile, 16:9 from sm up), so its height follows its
                 * width; a max-height here would do nothing. These caps keep the
                 * derived height inside the fold alongside the stepper and CTA.
                 */}
                <div className="mx-auto w-full max-w-[26rem] sm:max-w-xl">
                  <ExplainerVideo onEnded={() => {}} onSkip={() => setStepIndex(1)} />
                </div>
                <DynamicButton
                  data-testid="watch-continue"
                  onClick={() => setStepIndex(1)}
                  className="mt-6 w-full"
                >
                  Continue <ArrowRight className="h-4 w-4" />
                </DynamicButton>
              </div>
            )}

            {/* STEP: PLEDGE */}
            {stepIndex === 1 && (
              <div>
                <div className="mb-5 text-center">
                  <p className="text-label font-bold uppercase text-secondary">Step 2 · Pledge</p>
                  <h1 className="mt-2 font-heading text-title-2 font-bold">Take the pledge.</h1>
                </div>
                <div className="rounded border border-border bg-card p-6 md:p-8">
                  <div className="mb-5 h-1 w-16 rounded tricolor-bar" aria-hidden="true" />
                  <p className="font-heading text-title-3 font-semibold">“{PLEDGE}”</p>
                  <button
                    type="button"
                    data-testid="pledge-checkbox"
                    onClick={() => setPledged((p) => !p)}
                    className="mt-6 flex w-full items-center gap-3 rounded border border-border bg-background p-3.5 text-left transition-colors hover:bg-muted"
                  >
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded border-2 transition-colors ${pledged ? "border-secondary bg-secondary text-secondary-foreground" : "border-muted-foreground/40"}`}
                    >
                      {pledged && <Check className="h-4 w-4" />}
                    </span>
                    <span className="text-body font-medium">Yes, I take this pledge.</span>
                  </button>
                </div>
                <div className="mt-6 flex gap-3">
                  <DynamicButton variant="outline" onClick={() => setStepIndex(0)}>
                    Back
                  </DynamicButton>
                  <DynamicButton
                    data-testid="pledge-continue"
                    disabled={!pledged}
                    onClick={() => setStepIndex(2)}
                    className="flex-1"
                  >
                    Continue <ArrowRight className="h-4 w-4" />
                  </DynamicButton>
                </div>
              </div>
            )}

            {/* STEP: DETAILS */}
            {stepIndex === 2 && (
              <div>
                <div className="mb-5 text-center">
                  <p className="text-label font-bold uppercase text-secondary">
                    Step 3 · Your details
                  </p>
                  <h1 className="mt-2 font-heading text-title-2 font-bold">Become a Supporter.</h1>
                  <p className="mt-2 text-body text-foreground/70">
                    Takes 20 seconds. We never share your details.
                  </p>
                </div>
                <form
                  onSubmit={submit}
                  data-testid="supporter-form"
                  className="space-y-3.5 rounded border border-border bg-card p-6 md:p-7"
                >
                  <Field label="Full name *">
                    <Input
                      data-testid="supporter-name"
                      value={form.name}
                      onChange={set("name")}
                      placeholder="Your name"
                      className="h-10 rounded"
                    />
                  </Field>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="State *">
                      <select
                        data-testid="supporter-state"
                        value={form.state}
                        onChange={set("state")}
                        className="h-10 w-full rounded border border-input bg-background px-4 text-body text-foreground outline-none focus:ring-1 focus:ring-secondary"
                      >
                        <option value="">Select state</option>
                        {STATES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="City *">
                      <Input
                        data-testid="supporter-city"
                        value={form.city}
                        onChange={set("city")}
                        placeholder="Your city"
                        className="h-10 rounded"
                      />
                    </Field>
                  </div>
                  {/* Paired so the five inputs occupy three rows, not five. */}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Email *">
                      <Input
                        data-testid="supporter-email"
                        type="email"
                        value={form.email}
                        onChange={set("email")}
                        placeholder="you@email.com"
                        className="h-10 rounded"
                      />
                    </Field>
                    <Field label="Mobile (optional)">
                      <Input
                        data-testid="supporter-mobile"
                        value={form.mobile}
                        onChange={set("mobile")}
                        placeholder="+91 …"
                        className="h-10 rounded"
                      />
                    </Field>
                  </div>
                  <div className="flex gap-3 pt-1">
                    <DynamicButton type="button" variant="outline" onClick={() => setStepIndex(1)}>
                      Back
                    </DynamicButton>
                    <DynamicButton
                      type="submit"
                      loading={loading}
                      variant="secondary"
                      className="flex-1"
                      data-testid="become-supporter-button"
                    >
                      Become a Supporter
                    </DynamicButton>
                  </div>
                </form>
              </div>
            )}

            {/* STEP: DONE */}
            {stepIndex === 3 && result && (
              <div data-testid="thank-you">
                <div className="mb-6 text-center">
                  <div
                    ref={partyRef}
                    className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded bg-secondary"
                  >
                    <PartyPopper className="h-6 w-6 text-secondary-foreground" />
                  </div>
                  <p className="text-label font-bold uppercase text-secondary">
                    You're in{result.already ? " (already a member)" : ""}!
                  </p>
                  <h1 className="mt-2 font-heading text-title-2 font-bold">
                    Welcome to the movement, {result.name?.split(" ")[0] || "friend"}.
                  </h1>
                  <p className="mt-2 text-body text-foreground/70">
                    Here is your digital certificate, badge and Movement ID.
                  </p>
                </div>

                <SupporterCertificate
                  name={result.name}
                  movementId={result.movement_id}
                  date={result.created_at}
                />

                <div className="mt-6 rounded border border-border bg-card p-5 text-center">
                  <h2 className="font-heading text-title-4 font-bold">Now, spread the word.</h2>
                  <div className="mt-4 flex justify-center">
                    <SupporterShare />
                  </div>
                </div>

                <div className="mt-5 flex flex-col justify-center gap-3 sm:flex-row">
                  <LinkButton to="/knowledge" data-testid="explore-knowledge" variant="default">
                    <BookOpen className="h-4 w-4" /> Explore the Knowledge Hub
                  </LinkButton>
                  <LinkButton to="/" variant="outline">
                    Back to Home
                  </LinkButton>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

const Field = ({ label, children }) => (
  <label className="block">
    <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
      {label}
    </span>
    {children}
  </label>
);
