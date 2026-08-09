import { useEffect, useState } from "react";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import LinkButton from "@/components/LinkButton";
import { PageHero, Section, SectionHeading, Pill } from "@/components/platform/Primitives";
import {
  NOT_FINISHED,
  ROLES,
  SECTIONS,
  STATUS,
  TRUST,
} from "@/lib/docsContent";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleDot,
  Clock,
  Compass,
  Info,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

/*
 * The plain-language guide at /docs.
 *
 * Written for a citizen, a journalist or a new volunteer. Everything it says comes
 * from lib/docsContent.js, so the table of contents, the section counts and the
 * feature list can never disagree with each other.
 *
 * Three deliberate choices about the page itself:
 *
 * - Every feature says whether you need an account, first, because that is the
 *   question everyone actually has.
 * - Every feature has a "worth knowing" note carrying its own limitation, rather
 *   than a disclaimer at the bottom of the page that nobody reads.
 * - The last two sections are "how we keep this trustworthy" and "what isn't
 *   finished". A guide that only lists what works is marketing.
 */

const STATUS_TONE = {
  [STATUS.LIVE.key]: { tone: "primary", Icon: CheckCircle2 },
  [STATUS.GROWING.key]: { tone: "secondary", Icon: CircleDot },
  [STATUS.SOON.key]: { tone: "muted", Icon: Clock },
};

const START_HERE = [
  {
    title: "I want to understand the argument",
    body: "Start with the Constitution Library, or take the half-hour course.",
    to: "/academy",
    cta: "Take the course",
    Icon: BookOpen,
  },
  {
    title: "I want to check on my representative",
    body: "Find who holds your seats, and what the public record says they have done.",
    to: "/my-representatives",
    cta: "Find my representatives",
    Icon: UserCheck,
  },
  {
    title: "I want to actually do something",
    body: "File an RTI, write to your MP or MLA, sign a petition, or take a volunteer task.",
    to: "/tools",
    cta: "See the civic tools",
    Icon: Compass,
  },
];

export default function Docs() {
  const [active, setActive] = useState(SECTIONS[0].id);

  /*
   * Highlight the section currently on screen in the sidebar. IntersectionObserver
   * rather than a scroll listener so it costs nothing on a phone, and it is skipped
   * entirely if the browser does not support it -- the links still work, they just
   * do not highlight.
   */
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const ids = [...SECTIONS.map((s) => s.id), "trust", "roles", "not-finished"];
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );
    ids.forEach((id) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });
    return () => observer.disconnect();
  }, []);

  const totalFeatures = SECTIONS.reduce((sum, section) => sum + section.features.length, 0);

  const tocLinks = [
    ...SECTIONS.map((section) => ({ id: section.id, label: section.title })),
    { id: "trust", label: "How we keep this trustworthy" },
    { id: "roles", label: "Who does what" },
    { id: "not-finished", label: "What isn't finished yet" },
  ];

  return (
    <div data-testid="docs-page">
      <PageHero
        eyebrow="A guide to this platform"
        lines={["What everything here", "does, and how", "to use it."]}
        lede={`Every feature on this site, explained without jargon: what it is for, what happens step by step when you use it, and what it cannot do. ${totalFeatures} features across ${SECTIONS.length} areas. No technical knowledge assumed.`}
      >
        <div className="flex flex-wrap gap-3">
          <LinkButton to="/join" size="lg">
            Join the movement
          </LinkButton>
          <LinkButton to="/constitution" variant="outline" size="lg">
            Start with the Constitution
          </LinkButton>
        </div>
      </PageHero>

      {/* Route people by intent before listing anything. */}
      <Section muted testId="docs-start-here">
        <SectionHeading eyebrow="Start here" title="What brought you to this site?" />
        <StaggerGroup className="mt-10 grid gap-5 md:grid-cols-3">
          {START_HERE.map((card) => (
            <StaggerItem key={card.title}>
              <div className="flex h-full flex-col rounded border border-border bg-card p-6">
                <div className="flex h-11 w-11 items-center justify-center rounded bg-secondary">
                  <card.Icon className="h-5 w-5 text-secondary-foreground" aria-hidden="true" />
                </div>
                <h3 className="mt-4 font-heading text-lead font-semibold tracking-tight">
                  {card.title}
                </h3>
                <p className="mt-2 flex-1 text-body text-foreground/70">{card.body}</p>
                <LinkButton to={card.to} variant="outline" size="sm" className="mt-5 self-start">
                  {card.cta}
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </LinkButton>
              </div>
            </StaggerItem>
          ))}
        </StaggerGroup>
      </Section>

      <Section testId="docs-body">
        <div className="grid gap-12 lg:grid-cols-[240px_1fr]">
          {/* Contents. Sticky on desktop, a plain list on mobile. */}
          <nav aria-label="Contents" className="lg:sticky lg:top-24 lg:self-start">
            <p className="text-label font-bold uppercase text-muted-foreground">Contents</p>
            <ul className="mt-4 space-y-1">
              {tocLinks.map((link) => (
                <li key={link.id}>
                  <a
                    href={`#${link.id}`}
                    className={`block rounded px-3 py-2 text-meta transition-colors ${
                      active === link.id
                        ? "bg-primary/10 font-semibold text-primary"
                        : "text-foreground/70 hover:bg-muted"
                    }`}
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="min-w-0 space-y-20">
            {SECTIONS.map((section) => (
              <section key={section.id} id={section.id} className="scroll-mt-24">
                <Reveal>
                  <h2 className="font-heading text-title-2 font-semibold tracking-tight">
                    {section.title}
                  </h2>
                  <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/75">
                    {section.lede}
                  </p>
                </Reveal>

                <div className="mt-10 space-y-8">
                  {section.features.map((feature) => {
                    const status = STATUS_TONE[feature.status.key] ?? STATUS_TONE.live;
                    return (
                      <article
                        key={feature.id}
                        id={feature.id}
                        className="scroll-mt-24 rounded border border-border bg-card p-7"
                        data-testid={`docs-feature-${feature.id}`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                            {feature.name}
                          </h3>
                          <Pill tone={status.tone}>
                            <status.Icon className="mr-1 h-3 w-3" aria-hidden="true" />
                            {feature.status.label}
                          </Pill>
                        </div>

                        <p className="mt-2 text-lead leading-relaxed text-foreground/80">
                          {feature.oneLine}
                        </p>

                        {/* The first question anyone has. */}
                        <p className="mt-4 inline-flex items-center gap-2 rounded border border-border bg-muted/50 px-3 py-1.5 text-meta text-foreground/75">
                          <UserCheck className="h-3.5 w-3.5" aria-hidden="true" />
                          {feature.who}
                        </p>

                        <div className="mt-5">
                          <p className="text-label font-bold uppercase text-muted-foreground">
                            How it works
                          </p>
                          <ol className="mt-3 space-y-2.5">
                            {feature.steps.map((step, index) => (
                              <li key={index} className="flex gap-3">
                                <span
                                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[0.65rem] font-bold text-secondary-foreground"
                                  aria-hidden="true"
                                >
                                  {index + 1}
                                </span>
                                <span className="text-body leading-relaxed text-foreground/80">
                                  {step}
                                </span>
                              </li>
                            ))}
                          </ol>
                        </div>

                        {feature.honest ? (
                          <div className="mt-5 rounded border border-amber-600/30 bg-amber-600/10 p-4">
                            <p className="flex items-start gap-2 text-meta leading-relaxed text-foreground/85">
                              <Info
                                className="mt-0.5 h-4 w-4 shrink-0 text-amber-700"
                                aria-hidden="true"
                              />
                              <span>
                                <strong className="font-semibold">Worth knowing: </strong>
                                {feature.honest}
                              </span>
                            </p>
                          </div>
                        ) : null}

                        <LinkButton
                          to={feature.path}
                          variant="outline"
                          size="sm"
                          className="mt-5"
                          data-testid={`docs-open-${feature.id}`}
                        >
                          Open {feature.name}
                          <ArrowRight className="h-4 w-4" aria-hidden="true" />
                        </LinkButton>
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}

            {/* ---- Trust ---- */}
            <section id="trust" className="scroll-mt-24">
              <Reveal>
                <h2 className="flex items-center gap-2 font-heading text-title-2 font-semibold tracking-tight">
                  <ShieldCheck className="h-7 w-7 text-secondary" aria-hidden="true" />
                  How we keep this trustworthy
                </h2>
                <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/75">
                  A site that publishes facts about named people has to be able to explain how it
                  knows them. These are the rules the software enforces &mdash; not promises we make,
                  but things the system will not let anyone do.
                </p>
              </Reveal>

              <div className="mt-10 grid gap-5 md:grid-cols-2">
                {TRUST.map((item) => (
                  <div key={item.id} className="rounded border border-border bg-card p-6">
                    <h3 className="font-heading text-lead font-semibold leading-snug tracking-tight">
                      {item.title}
                    </h3>
                    <p className="mt-3 text-body leading-relaxed text-foreground/75">{item.body}</p>
                  </div>
                ))}
              </div>

              <div className="mt-8 flex flex-wrap gap-3">
                <LinkButton to="/disclaimer" variant="outline" size="sm">
                  Full disclaimer and sources
                </LinkButton>
                <LinkButton to="/content-policy" variant="outline" size="sm">
                  Content policy
                </LinkButton>
                <LinkButton to="/privacy" variant="outline" size="sm">
                  Privacy policy
                </LinkButton>
              </div>
            </section>

            {/* ---- Roles ---- */}
            <section id="roles" className="scroll-mt-24">
              <Reveal>
                <h2 className="font-heading text-title-2 font-semibold tracking-tight">
                  Who does what
                </h2>
                <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/75">
                  Nobody on this platform can do everything. Jobs are split deliberately, so that no
                  single person can research a claim, approve it and publish it alone.
                </p>
              </Reveal>

              <div className="mt-8 overflow-x-auto">
                <table className="w-full min-w-[36rem] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="py-3 pr-6 text-label font-bold uppercase text-muted-foreground">
                        Who
                      </th>
                      <th className="py-3 text-label font-bold uppercase text-muted-foreground">
                        What they can do
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ROLES.map((role) => (
                      <tr key={role.name} className="border-b border-border align-top">
                        <td className="py-4 pr-6 font-heading text-body font-semibold tracking-tight">
                          {role.name}
                        </td>
                        <td className="py-4 text-body leading-relaxed text-foreground/75">
                          {role.can}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* ---- Honest limitations ---- */}
            <section id="not-finished" className="scroll-mt-24">
              <Reveal>
                <h2 className="font-heading text-title-2 font-semibold tracking-tight">
                  What isn&rsquo;t finished yet
                </h2>
                <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/75">
                  This is a volunteer-built platform and it is being built in the open. A guide that
                  only listed what works would be an advertisement, so here is the other half.
                </p>
              </Reveal>

              <div className="mt-8 space-y-4">
                {NOT_FINISHED.map((item) => (
                  <div key={item.title} className="rounded border border-border bg-muted/40 p-6">
                    <h3 className="font-heading text-lead font-semibold tracking-tight">
                      {item.title}
                    </h3>
                    <p className="mt-2 text-body leading-relaxed text-foreground/75">{item.body}</p>
                  </div>
                ))}
              </div>

              <div className="mt-10 rounded border border-primary/30 bg-primary/5 p-8">
                <h3 className="font-heading text-title-3 font-semibold tracking-tight">
                  Most of that gap is people, not code
                </h3>
                <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/75">
                  Researching one constituency, translating one article, checking one affidavit
                  against one profile &mdash; that is what moves this forward, and every one of those
                  is a real task on the volunteer board with verified hours attached.
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <LinkButton to="/volunteer-portal">See the task board</LinkButton>
                  <LinkButton to="/contact" variant="outline">
                    Tell us what is missing
                  </LinkButton>
                </div>
              </div>
            </section>
          </div>
        </div>
      </Section>

      <Section muted>
        <Reveal>
          <div className="text-center">
            <h2 className="font-heading text-title-2 font-semibold tracking-tight">
              Still not sure where to start?
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-body text-foreground/70">
              Ask the assistant a question in your own words, or write to us. Neither needs an
              account.
            </p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <LinkButton to="/ask" size="lg">
                Ask a question
              </LinkButton>
              <LinkButton to="/contact" variant="outline" size="lg">
                Contact the team
              </LinkButton>
            </div>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
