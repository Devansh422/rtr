import { useState } from "react";
import { MaskedLines } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { submitContact } from "@/lib/api";
import ShareButtons from "@/components/ShareButtons";
import DynamicButton from "@/components/DynamicButton";
import Eyebrow from "@/components/Eyebrow";
import { SOCIAL_LINKS, CONTACT_EMAIL } from "@/lib/social";
import { ArrowUpRight, Mail, Check } from "lucide-react";
import { gsap, useGsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";

const EMPTY = { name: "", email: "", subject: "", message: "" };

export default function Contact() {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const reduced = prefersReducedMotion();

  /*
   * Scoped to the left column. The h1 is deliberately not a target -- MaskedLines
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
   * Scoped to the right column. The success panel is only mounted once `done`
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

  const submit = async (e) => {
    e.preventDefault();
    for (const k of Object.keys(EMPTY))
      if (!form[k]) return toast.error("Please fill in all fields");
    setLoading(true);
    try {
      await submitContact(form);
      setDone(true);
      toast.success("Message sent! We'll reply soon.");
    } catch {
      toast.error("Could not send. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="contact-page">
      {/*
       * One viewport, asymmetric 5/7 split rather than 50/50.
       *
       * The old layout put a stack of loose parts (heading, a floating card, a bare
       * icon row, a bare share row) beside a single filled card, so the two halves
       * carried very different weight. Now the contact methods are one hairline-
       * divided object and the form is another, and the form gets the wider column
       * because its fields need the measure. Two comparable blocks, not a list next
       * to a card.
       *
       * No extra top padding: full-section-hero already reserves 6rem for the
       * fixed navbar.
       */}
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto grid w-full max-w-7xl items-start gap-10 lg:grid-cols-12 lg:gap-x-16">
          <div ref={introRef} className="lg:col-span-5">
            <Eyebrow data-intro>Contact</Eyebrow>
            <h1 className="mt-5 font-heading text-title-1 font-semibold">
              <MaskedLines lines={["Let's talk", "accountability."]} />
            </h1>
            <p data-intro className="mt-6 max-w-md text-lead text-foreground/70">
              Media queries, partnership ideas, or just want to say hi? Drop us a line. We read
              everything.
            </p>

            {/*
             * Contact methods as one divided list. gap-px over bg-border draws the
             * rules, so no row needs its own border and the hairlines stay a true
             * 1px. The email row is a full-width list row rather than a button --
             * it is an entry in this list, and a button-shaped card here is what
             * made the column read as floating parts before.
             */}
            <div
              data-intro
              className="mt-9 grid gap-px overflow-hidden rounded border border-border bg-border"
            >
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                data-testid="contact-email-link"
                className="flex items-center gap-4 bg-card px-5 py-4 transition-colors hover:bg-muted"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-primary">
                  <Mail className="h-4 w-4 text-primary-foreground" aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block text-label font-bold uppercase text-muted-foreground">
                    Email
                  </span>
                  <span className="block truncate text-body font-medium">{CONTACT_EMAIL}</span>
                </span>
                <ArrowUpRight
                  className="ml-auto h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              </a>

              <div className="bg-card px-5 py-4">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  Follow the movement
                </p>
                {/* Solid brand tiles: recognisable at a glance, unlike outlined glyphs. */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {SOCIAL_LINKS.map(({ label, href, Icon, brand, onBrand }) => (
                    <a
                      key={label}
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={label}
                      data-testid={`contact-social-${label.toLowerCase().split(" ")[0]}`}
                      className="flex h-10 w-10 items-center justify-center rounded transition-opacity hover:opacity-85"
                      style={{ backgroundColor: brand, color: onBrand }}
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </a>
                  ))}
                </div>
              </div>

              <div className="bg-card px-5 py-4">
                <p className="text-label font-bold uppercase text-muted-foreground">
                  Spread the word
                </p>
                <ShareButtons
                  className="mt-3"
                  title="Check out the #RightToRecall Movement, a non-partisan push for democratic accountability."
                />
              </div>
            </div>
          </div>

          <div ref={successRef} className="lg:col-span-7">
            {done ? (
              <div
                data-panel
                className="flex flex-col items-center gap-4 rounded border border-border bg-card p-12 text-center"
              >
                <div
                  data-anim
                  className="flex h-16 w-16 items-center justify-center rounded bg-primary"
                >
                  <Check className="h-8 w-8 text-primary-foreground" aria-hidden="true" />
                </div>
                <h2 data-anim className="font-heading text-title-2 font-semibold">
                  Message sent!
                </h2>
                <p data-anim className="text-body text-muted-foreground">
                  Thanks for reaching out. We'll get back to you shortly.
                </p>
                <DynamicButton
                  data-anim
                  variant="outline"
                  className="mt-2"
                  onClick={() => {
                    setForm(EMPTY);
                    setDone(false);
                  }}
                >
                  Send another
                </DynamicButton>
              </div>
            ) : (
              /*
               * The form is contained by a labelled band over the field area, so it
               * reads as one addressed object rather than four inputs on a card.
               */
              <form
                onSubmit={submit}
                data-testid="contact-form"
                className="overflow-hidden rounded border border-border bg-card"
              >
                <div className="flex items-center justify-between gap-4 border-b border-border bg-muted/40 px-5 py-3">
                  <p className="text-label font-bold uppercase text-muted-foreground">
                    Send a message
                  </p>
                  <span className="text-micro font-bold uppercase text-muted-foreground">
                    Replies within 48h
                  </span>
                </div>

                <div className="space-y-5 p-6 md:p-8">
                  {/* Name and email pair up so the form stays inside one viewport. */}
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="Name">
                      <Input
                        data-testid="contact-name"
                        value={form.name}
                        onChange={set("name")}
                        placeholder="Your name"
                        className="h-12 rounded"
                      />
                    </Field>
                    <Field label="Email">
                      <Input
                        data-testid="contact-email"
                        type="email"
                        value={form.email}
                        onChange={set("email")}
                        placeholder="you@email.com"
                        className="h-12 rounded"
                      />
                    </Field>
                  </div>
                  <Field label="Subject">
                    <Input
                      data-testid="contact-subject"
                      value={form.subject}
                      onChange={set("subject")}
                      placeholder="What's this about?"
                      className="h-12 rounded"
                    />
                  </Field>
                  <Field label="Message">
                    <Textarea
                      data-testid="contact-message"
                      value={form.message}
                      onChange={set("message")}
                      placeholder="Your message…"
                      rows={4}
                      className="rounded"
                    />
                  </Field>
                  <DynamicButton
                    type="submit"
                    loading={loading}
                    variant="secondary"
                    className="h-11 w-full"
                    data-testid="contact-submit"
                  >
                    Send Message
                  </DynamicButton>
                </div>
              </form>
            )}
          </div>
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
