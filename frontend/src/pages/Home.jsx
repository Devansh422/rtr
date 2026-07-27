import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { gsap, EASE_OUT, prefersReducedMotion } from "@/lib/motion";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import {
  ArrowRight,
  Vote,
  ScrollText,
  RefreshCw,
  ShieldCheck,
  Users,
  TrendingUp,
  MapPin,
  Clock,
} from "lucide-react";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import Eyebrow from "@/components/Eyebrow";
import ChakraWheel from "@/components/ChakraWheel";
import MarqueeStrip from "@/components/MarqueeStrip";
import ShareButtons from "@/components/ShareButtons";
import { useJoin } from "@/context/JoinContext";
import { getCampaigns, getBlogs, getTestimonials, getLeaders } from "@/lib/api";
import { progressPercent, formatCount, formatDate } from "@/lib/content";

const HERO_IMG =
  "https://images.unsplash.com/photo-1591261495530-262c58c5f31a?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400";
const JOIN_IMG =
  "https://images.unsplash.com/photo-1607748862156-7c548e7e98f4?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400";

const WHY = [
  {
    icon: Users,
    title: "Voters need real power",
    text: "Elections happen once every few years. Accountability should not. Recall keeps the conversation alive between votes.",
  },
  {
    icon: ShieldCheck,
    title: "Accountability builds trust",
    text: "When representatives know citizens are engaged, governance improves. Transparency is a feature, not a threat.",
  },
  {
    icon: TrendingUp,
    title: "Democracy needs reform",
    text: "Half of India is under 30. Modern tools for civic participation make democracy feel within reach again.",
  },
];

const STEPS = [
  {
    icon: Vote,
    title: "Elect",
    text: "Citizens vote representatives into office through free and fair elections. Democracy begins with your voice.",
  },
  {
    icon: ScrollText,
    title: "Review",
    text: "Track performance transparently using public records, RTI tools, and open data. Stay informed, not in the dark.",
  },
  {
    icon: RefreshCw,
    title: "Recall",
    text: "Where the constitution provides for it, citizens can responsibly initiate recall with proper safeguards.",
  },
];

const StatusBadge = ({ status }) => {
  const map = {
    ACTIVE: "bg-primary text-primary-foreground",
    UPCOMING: "bg-secondary text-secondary-foreground",
    VICTORY: "bg-foreground text-background",
  };
  return (
    <span
      className={`inline-block rounded px-3 py-1 text-micro font-bold uppercase ${map[status] || "bg-muted"}`}
    >
      {status}
    </span>
  );
};

export default function Home() {
  const { openJoin } = useJoin();
  const [campaigns, setCampaigns] = useState([]);
  const [blogs, setBlogs] = useState([]);
  const [testimonials, setTestimonials] = useState([]);
  const [leaders, setLeaders] = useState([]);

  /*
   * "Ongoing" means ACTIVE. If nothing is marked active, fall back to whatever
   * exists rather than rendering an empty section -- a fresh install with no
   * status set would otherwise show nothing here.
   */
  const ongoingCampaigns = useMemo(() => {
    const active = campaigns.filter((c) => c.status === "ACTIVE");
    return (active.length > 0 ? active : campaigns).slice(0, 3);
  }, [campaigns]);

  // Newest first. The API already sorts blogs by date desc, but sorting here too
  // keeps the section correct regardless of what order the endpoint returns.
  const latestArticles = useMemo(
    () => [...blogs].sort((a, b) => new Date(b.date ?? 0) - new Date(a.date ?? 0)).slice(0, 3),
    [blogs]
  );

  const heroRef = useRef(null);
  const heroImgRef = useRef(null);
  const heroFrameRef = useRef(null);

  /*
   * Hero entrance. One timeline sequences the badge, the word-by-word reveal of
   * the demand, and the bottom block, so the relative beats stay locked together
   * even if the copy changes.
   *
   * Each word of the demand sits in its own overflow-hidden wrapper and slides up
   * from fully below it; staggering those is what makes the reveal read as sleek
   * rather than as one heavy block moving.
   */
  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;

    const reduce = prefersReducedMotion();
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: EASE_OUT } });

      tl.from("[data-hero-badge]", {
        opacity: 0,
        y: reduce ? 0 : 12,
        duration: reduce ? 0.2 : 0.5,
      });

      if (reduce) {
        tl.from("[data-demand-line]", { opacity: 0, duration: 0.3, stagger: 0.06 }, 0.2);
      } else {
        tl.from(
          "[data-demand-line]",
          { yPercent: 118, duration: 1.15, stagger: 0.11, ease: "expo.out" },
          0.15
        );
      }

      tl.from(
        "[data-hero-foot]",
        { opacity: 0, y: reduce ? 0 : 18, duration: reduce ? 0.2 : 0.8 },
        reduce ? 0.4 : 0.75
      );
    }, el);

    return () => ctx.revert();
  }, []);

  /*
   * Clip-zoom reveal on the hero image.
   *
   * The frame's inset clip-path opens outward while the image itself settles from
   * an over-scale back to 1:1. Running the two in opposite directions is what
   * gives the "unveil" feel -- the picture appears to be revealed rather than
   * simply fading or sliding in. No opacity is animated, so the image is never
   * washed out.
   *
   * Under reduced-motion the frame is set to its final state immediately.
   */
  useEffect(() => {
    const frame = heroFrameRef.current;
    const img = heroImgRef.current;
    if (!frame || !img) return;

    if (prefersReducedMotion()) {
      gsap.set(frame, { clipPath: "inset(0% 0% 0% 0%)" });
      gsap.set(img, { scale: 1 });
      return;
    }

    const ctx = gsap.context(() => {
      // Scroll-triggered rather than on a timer: the block sits below the fold,
      // so a delayed tween would have already finished by the time it's seen.
      const tl = gsap.timeline({
        scrollTrigger: { trigger: frame, start: "top bottom-=120", once: true },
      });

      tl.fromTo(
        frame,
        { clipPath: "inset(14% 20% 14% 20%)" },
        { clipPath: "inset(0% 0% 0% 0%)", duration: 1.3, ease: "expo.out" }
      ).fromTo(img, { scale: 1.3 }, { scale: 1, duration: 1.5, ease: "expo.out" }, 0);
    }, frame);

    return () => ctx.revert();
  }, []);

  useEffect(() => {
    getCampaigns()
      .then(setCampaigns)
      .catch(() => {});
    getBlogs()
      .then(setBlogs)
      .catch(() => {});
    getTestimonials()
      .then(setTestimonials)
      .catch(() => {});
    getLeaders()
      .then(setLeaders)
      .catch(() => {});
  }, []);

  return (
    <div data-testid="home-page">
      {/* HERO */}
      <section ref={heroRef} className="relative flex min-h-svh flex-col overflow-hidden pt-16">
        {/*
         * Background photograph.
         *
         * A scrim is layered over it, which is a deliberate exception to the
         * no-overlay rule: the headline and body copy sit directly on top, and
         * without it the text drops below the 4.5:1 contrast floor over the
         * image's lighter regions. The 5:4 feature image further down carries no
         * overlay at all, because nothing is set over it.
         *
         * The scrim is stronger at the bottom, where the small copy and buttons
         * live, and lighter at the top where only the large display text sits.
         */}
        {/*
         * z-0 here with relative z-10 on the content siblings, rather than a
         * negative z-index on this layer: a negative z-index child paints behind
         * its parent's own background, so `-z-10` risks the photo disappearing
         * under an ancestor's bg-background depending on where a stacking context
         * happens to be established.
         */}
        <div className="absolute inset-0 z-0" aria-hidden="true">
          <img src="/hero.jpg" alt="" className="h-full w-full object-cover" fetchPriority="high" />
          <div className="absolute inset-0 bg-background/70" />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-background/25" />
        </div>

        {/*
         * The demand is the focal element, optically centred in the viewport, with
         * the non-partisan badge sitting directly above it as a caption. flex-1
         * lets this block absorb the space above the bottom copy, so it stays
         * centred without absolute positioning (which would overlap the copy on
         * short screens).
         */}
        <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-8 md:px-12">
          <div
            data-hero-badge
            className="mb-6 inline-flex items-center gap-2 rounded border border-border bg-card px-3 py-1.5 text-label font-bold uppercase"
          >
            <ChakraWheel className="h-3.5 w-3.5 text-chakra" /> A non-partisan civic movement
          </div>

          {/*
           * Two stacked lines, centred. Each line sits in its own overflow-hidden
           * box and slides up from fully below it: the clip is why it reads as a
           * reveal rather than a slide. leading-[1.12] gives the two lines room to
           * breathe; the display token's default 1.06 was too tight once the text
           * wrapped to a second line.
           */}
          <h1 className="text-center font-heading text-display font-extrabold leading-[1.12] text-secondary">
            {["#Bring", "Right to Recall."].map((line) => (
              <span key={line} className="block overflow-hidden">
                <span data-demand-line className="block">
                  {line}
                </span>
              </span>
            ))}
          </h1>
        </div>

        {/* Statement, copy and actions: bottom-left. */}
        <div className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-10 md:px-12">
          <div
            data-hero-foot
            className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between"
          >
            <div className="max-w-xl">
              <div className="tricolor-bar mb-5 h-1 w-16 rounded" aria-hidden="true" />
              <h2 className="font-heading text-title-2 font-extrabold leading-[0.95]">
                India deserves accountability.
              </h2>
              <p className="mt-4 text-body leading-relaxed text-foreground/70">
                Understand it in 3 minutes. A hopeful, fact-based movement giving citizens the power
                to stay engaged with democracy, not just on election day, but every day.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <DynamicButton data-testid="hero-join-button" onClick={openJoin} size="sm">
                Join the Movement
                <ArrowRight className="h-4 w-4" />
              </DynamicButton>
              <LinkButton href="#why" data-testid="hero-learn-button" variant="outline" size="sm">
                Learn More
              </LinkButton>
            </div>
          </div>
        </div>

        {/* Marquee pinned to the bottom edge of the hero. */}
        <div className="relative z-10">
          <MarqueeStrip
            items={[
              "ONE NATION · ONE DEMAND",
              "ENACT THE RIGHT TO RECALL LAW IN INDIA",
              "POWER TO THE PEOPLE",
              "ACCOUNTABILITY IN DEMOCRACY",
            ]}
          />
        </div>
      </section>

      {/*
       * THE DEMAND: image and petition share one section.
       *
       * The 5:4 image sits centred at the top as the emotional anchor, then the
       * demand itself reads directly beneath it as the formal ask. Keeping them in
       * one section means the picture is never seen without the words it belongs to.
       *
       * Image: clip-zoom reveal, no overlay, fade or opacity.
       */}
      <section
        className="full-section border-t border-border px-6 md:px-12"
        data-testid="demand-section"
      >
        <div className="mx-auto w-full max-w-4xl py-gap-section">
          <div className="flex justify-center">
            <div ref={heroFrameRef} className="w-full overflow-hidden rounded border border-border">
              <div className="relative aspect-[5/4]">
                <img
                  ref={heroImgRef}
                  src={HERO_IMG}
                  alt="Young citizens holding signs at a peaceful community gathering"
                  className="absolute inset-0 h-full w-full object-cover"
                />
              </div>
            </div>
          </div>

          {/* The petition, centred under the image. */}
          <Reveal className="mt-gap-block">
            <div className="text-center">
              <div className="tricolor-bar mx-auto mb-5 h-1 w-14 rounded" aria-hidden="true" />
              <Eyebrow>Our Demand</Eyebrow>
              <p className="mt-3 font-heading text-title-2 font-extrabold">
                One nation, one demand.
              </p>
            </div>

            <blockquote className="mx-auto mt-8 max-w-2xl text-center font-heading text-title-4 font-semibold">
              “We call upon all State Governments and the Government of India to introduce, debate,
              pass, and implement a comprehensive{" "}
              <span className="text-secondary">Right to Recall Law</span>, ensuring greater
              accountability, transparency, and democratic responsibility of elected
              representatives.”
            </blockquote>

            {/* The four verbs of the ask, made scannable. */}
            <div className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-4">
              {["Introduce", "Debate", "Pass", "Implement"].map((step, i) => (
                <div key={step} className="bg-card px-3 py-3.5 text-center">
                  <p className="font-heading text-micro font-bold text-muted-foreground">
                    0{i + 1}
                  </p>
                  <p className="mt-1 font-heading text-meta font-bold">{step}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <DynamicButton onClick={openJoin} data-testid="demand-cta" size="sm">
                Add Your Voice <ArrowRight className="h-4 w-4" />
              </DynamicButton>
              <LinkButton to="/knowledge" variant="outline" size="sm">
                Read the case
              </LinkButton>
            </div>

            <p className="mt-6 text-center text-meta text-muted-foreground">
              Addressed to all State Governments and the Government of India.
            </p>
          </Reveal>
        </div>
      </section>

      {/* THE CASE: why it matters + how it works */}
      <section id="why" className="full-section mx-auto w-full max-w-7xl px-6 md:px-12">
        {/*
         * Header splits so neither side is left with dead space: label and
         * statement on the left, the framing sentence on the right.
         */}
        <Reveal>
          <div className="grid gap-6 border-b border-border pb-8 md:grid-cols-12 md:items-end">
            <div className="md:col-span-7">
              <Eyebrow>The case</Eyebrow>
              <h2 className="mt-gap-title font-heading text-title-2 font-extrabold">
                Democracy works better when citizens stay in the loop.
              </h2>
            </div>
            <p className="text-body text-foreground/70 md:col-span-5">
              Two questions worth separating: why accountability between elections matters, and the
              mechanism that delivers it.
            </p>
          </div>
        </Reveal>

        {/*
         * One object, two labelled bands, both on the same three-column rhythm.
         *
         * The previous version put a bare list beside a filled card, which read as
         * lopsided -- two different visual weights and two different heights. Here
         * every cell is identical in construction, so balance is structural rather
         * than something to eyeball. The shared column rhythm also lines each
         * argument up above the step it corresponds to.
         *
         * gap-px over bg-border draws the dividers, so no cell needs its own border.
         */}
        <div className="mt-gap-block overflow-hidden rounded border border-border">
          {/* Band 1: the argument */}
          <div className="flex items-center justify-between gap-4 bg-muted/40 px-5 py-3">
            <p className="text-label font-bold uppercase text-muted-foreground">Why it matters</p>
            <span className="text-micro font-bold uppercase text-muted-foreground">01 / 03</span>
          </div>

          <div className="grid gap-px bg-border md:grid-cols-3">
            {WHY.map((w, i) => (
              <div key={w.title} className="flex h-full flex-col bg-card p-6">
                <div className="flex items-center justify-between">
                  <w.icon className="h-4 w-4 text-primary" aria-hidden="true" />
                  <span className="font-heading text-micro font-bold text-muted-foreground">
                    0{i + 1}
                  </span>
                </div>
                <h3 className="mt-5 font-heading text-title-4 font-bold">{w.title}</h3>
                <p className="mt-2 text-body text-foreground/70">{w.text}</p>
              </div>
            ))}
          </div>

          {/* Band 2: the mechanism */}
          <div className="flex items-center justify-between gap-4 border-t border-border bg-muted/40 px-5 py-3">
            <p className="text-label font-bold uppercase text-muted-foreground">How it works</p>
            <span className="inline-flex items-center gap-1.5 text-micro font-bold uppercase text-muted-foreground">
              <RefreshCw className="h-3 w-3" aria-hidden="true" /> A loop, not a one-off
            </span>
          </div>

          <div className="grid gap-px bg-border md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div key={s.title} className="flex h-full flex-col bg-card p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-secondary">
                    <s.icon className="h-4 w-4 text-secondary-foreground" aria-hidden="true" />
                  </div>
                  <h3 className="font-heading text-title-4 font-bold">{s.title}</h3>
                  {/* Arrow implies the sequence; hidden on the last step. */}
                  {i < STEPS.length - 1 && (
                    <ArrowRight
                      className="ml-auto hidden h-4 w-4 text-muted-foreground md:block"
                      aria-hidden="true"
                    />
                  )}
                </div>
                <p className="mt-4 text-body text-foreground/70">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/*
       * ONGOING CAMPAIGNS then ARTICLES.
       *
       * Both are content-height (py-20/py-28) rather than `full-section`: a
       * three-card grid does not fill a viewport, so forcing 100vh here would
       * strand the cards in the middle of empty space. The full-height treatment
       * is kept for the narrative sections above, where it earns its place.
       */}

      {ongoingCampaigns.length > 0 && (
        <section
          className="border-t border-border px-6 py-20 md:px-12 md:py-28"
          data-testid="current-campaign"
        >
          <div className="mx-auto w-full max-w-7xl">
            <Reveal>
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
                <div>
                  <Eyebrow>Ongoing campaigns</Eyebrow>
                  <h2 className="mt-gap-title font-heading text-title-2 font-extrabold">
                    Where the work is happening.
                  </h2>
                </div>
                <LinkButton to="/campaigns" variant="outline" size="sm">
                  All campaigns <ArrowRight className="h-4 w-4" />
                </LinkButton>
              </div>
            </Reveal>

            <StaggerGroup className="mt-10 grid gap-6 md:grid-cols-3">
              {ongoingCampaigns.map((c) => {
                // liveSupporters (baseline + real /join signups) falls back to
                // the raw admin baseline if the API hasn't computed it.
                const liveCount = c.liveSupporters ?? c.supporters;
                return (
                  <StaggerItem key={c.id}>
                    <Link
                      to={`/campaigns/${c.id}`}
                      data-testid={`home-campaign-${c.id}`}
                      className="group flex h-full flex-col overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-1"
                    >
                      <div className="relative h-44 overflow-hidden">
                        <img
                          src={c.image}
                          alt=""
                          loading="lazy"
                          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        />
                        <div className="absolute left-3 top-3">
                          <StatusBadge status={c.status} />
                        </div>
                      </div>

                      <div className="flex flex-1 flex-col p-6">
                        {c.location && (
                          <p className="inline-flex items-center gap-1.5 text-label font-bold uppercase text-muted-foreground">
                            <MapPin className="h-3 w-3" aria-hidden="true" /> {c.location}
                          </p>
                        )}
                        <h3 className="mt-3 font-heading text-title-4 font-bold">{c.title}</h3>
                        <p className="mt-2 flex-1 text-body text-foreground/70">{c.description}</p>

                        {progressPercent(liveCount, c.goal) !== null && (
                          <div className="mt-5">
                            <div className="flex items-baseline justify-between text-meta">
                              <span className="font-semibold text-foreground/80">
                                {formatCount(liveCount)} supporters
                              </span>
                              <span className="font-bold text-secondary">
                                {Math.round(progressPercent(liveCount, c.goal))}%
                              </span>
                            </div>
                            <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-muted">
                              <div
                                className="h-full rounded bg-primary"
                                style={{ width: `${progressPercent(liveCount, c.goal)}%` }}
                              />
                            </div>
                          </div>
                        )}

                        <span className="mt-5 inline-flex items-center gap-2 text-label font-bold uppercase text-foreground">
                          {c.cta || "Read more"} <ArrowRight className="h-3.5 w-3.5" />
                        </span>
                      </div>
                    </Link>
                  </StaggerItem>
                );
              })}
            </StaggerGroup>
          </div>
        </section>
      )}

      {latestArticles.length > 0 && (
        <section
          className="border-t border-border bg-muted/30 px-6 py-20 md:px-12 md:py-28"
          data-testid="home-articles"
        >
          <div className="mx-auto w-full max-w-7xl">
            <Reveal>
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
                <div>
                  <Eyebrow>From the knowledge hub</Eyebrow>
                  <h2 className="mt-gap-title font-heading text-title-2 font-extrabold">
                    Read up on the argument.
                  </h2>
                </div>
                <LinkButton to="/blog" variant="outline" size="sm">
                  All articles <ArrowRight className="h-4 w-4" />
                </LinkButton>
              </div>
            </Reveal>

            <StaggerGroup className="mt-10 grid gap-6 md:grid-cols-3">
              {latestArticles.map((b) => (
                <StaggerItem key={b.id}>
                  <Link
                    to={`/blog/${b.id}`}
                    data-testid={`home-article-${b.id}`}
                    className="group flex h-full flex-col overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-1"
                  >
                    <div className="h-44 overflow-hidden">
                      <img
                        src={b.image}
                        alt=""
                        loading="lazy"
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                      />
                    </div>

                    <div className="flex flex-1 flex-col p-6">
                      <div className="flex items-center gap-3">
                        <span className="rounded bg-secondary px-2 py-0.5 text-micro font-bold uppercase text-secondary-foreground">
                          {b.category}
                        </span>
                        <span className="inline-flex items-center gap-1 text-meta text-muted-foreground">
                          <Clock className="h-3 w-3" aria-hidden="true" /> {b.readTime}
                        </span>
                      </div>

                      <h3 className="mt-4 font-heading text-title-4 font-bold">{b.title}</h3>
                      <p className="mt-2 flex-1 text-body text-foreground/70">{b.excerpt}</p>

                      <div className="mt-5 flex items-center justify-between text-meta text-muted-foreground">
                        <span>{b.author}</span>
                        <span>{formatDate(b.date)}</span>
                      </div>
                    </div>
                  </Link>
                </StaggerItem>
              ))}
            </StaggerGroup>
          </div>
        </section>
      )}

      {/* TESTIMONIALS */}
      {testimonials.length > 0 && (
        <section className="full-section border-t border-border bg-muted/30 px-6 md:px-12">
          <div className="mx-auto w-full max-w-7xl">
            <Reveal>
              <h2 className="max-w-2xl font-heading text-title-1 font-semibold tracking-tight">
                Voices of the movement.
              </h2>
            </Reveal>
            <StaggerGroup className="mt-14 grid gap-6 md:grid-cols-3">
              {testimonials.map((t) => (
                <StaggerItem key={t.id}>
                  <div className="h-full rounded border border-border bg-card p-8">
                    <p className="font-heading text-title-4 leading-snug tracking-tight">
                      “{t.quote}”
                    </p>
                    <div className="mt-6 flex items-center gap-3">
                      <img src={t.avatar} alt={t.name} className="h-11 w-11 rounded object-cover" />
                      <div>
                        <p className="font-semibold">{t.name}</p>
                        <p className="text-body text-muted-foreground">{t.role}</p>
                      </div>
                    </div>
                  </div>
                </StaggerItem>
              ))}
            </StaggerGroup>
          </div>
        </section>
      )}

      {/* LEGACY / LEADERS */}
      {leaders.length > 0 && (
        <section
          className="full-section border-t border-border px-6 md:px-12"
          data-testid="legacy-section"
        >
          <div className="mx-auto w-full max-w-7xl">
            <Reveal>
              <div className="tricolor-bar mb-6 h-1.5 w-24 rounded" aria-hidden="true" />
              <p className="text-label font-bold uppercase text-secondary">
                The legacy we carry forward
              </p>
              <h2 className="mt-4 max-w-3xl font-heading text-title-1 font-semibold tracking-tight">
                India's democracy was built by those who trusted the people.
              </h2>
              <p className="mt-5 max-w-2xl text-foreground/70">
                We stand on the shoulders of leaders who believed accountability, courage, and the
                will of the people are the heartbeat of a free nation.
              </p>
            </Reveal>

            <StaggerGroup className="mt-14 grid gap-6 md:grid-cols-3">
              {leaders.map((l) => (
                <StaggerItem key={l.id}>
                  <figure
                    className="group h-full overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-2"
                    data-testid={`leader-card-${l.id}`}
                  >
                    <div className="relative aspect-[4/5] overflow-hidden bg-muted">
                      <img
                        src={l.image}
                        alt={`Portrait of ${l.name}`}
                        loading="lazy"
                        className="h-full w-full object-cover object-top grayscale transition-all duration-500 group-hover:grayscale-0 group-hover:scale-105"
                      />
                      <div
                        className="absolute inset-x-0 bottom-0 h-1.5 tricolor-bar"
                        aria-hidden="true"
                      />
                    </div>
                    <figcaption className="flex h-full flex-col p-7">
                      <blockquote className="font-heading text-lead leading-snug tracking-tight text-foreground">
                        “{l.quote}”
                      </blockquote>
                      <div className="mt-6 border-t border-border pt-4">
                        <p className="font-heading text-lead font-semibold tracking-tight">
                          {l.name}
                        </p>
                        <p className="text-body text-secondary">{l.role}</p>
                        <p className="mt-0.5 text-meta font-medium uppercase tracking-widest text-muted-foreground">
                          {l.years}
                        </p>
                      </div>
                    </figcaption>
                  </figure>
                </StaggerItem>
              ))}
            </StaggerGroup>
          </div>
        </section>
      )}

      {/* JOIN CTA */}
      <section
        className="full-section mx-auto w-full max-w-7xl px-6 md:px-12"
        data-testid="join-community"
      >
        <div className="relative overflow-hidden rounded border border-border">
          <img
            src={JOIN_IMG}
            alt="Young people laughing together"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-foreground/70" />
          <div className="relative px-8 py-20 text-center md:px-12 md:py-28">
            <Reveal>
              <h2 className="mx-auto max-w-3xl font-heading text-title-1 font-semibold tracking-tight text-background">
                Be part of something bigger than an election.
              </h2>
              <p className="mx-auto mt-5 max-w-xl text-background/80">
                Join thousands of citizens building a more accountable democracy. It takes 20
                seconds.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <DynamicButton onClick={openJoin} data-testid="cta-join-button" size="lg">
                  Join the Movement
                </DynamicButton>
                {/*
                 * Sits on a dark scrim, so `outline` (which is card-on-border)
                 * would disappear. A solid background surface reads as the
                 * secondary action here without inventing a new variant.
                 */}
                <LinkButton
                  to="/volunteer"
                  data-testid="cta-volunteer-button"
                  size="lg"
                  className="bg-background text-foreground hover:bg-background/90"
                >
                  Volunteer
                </LinkButton>
              </div>
              <div className="mt-10 flex justify-center">
                <ShareButtons title="I just joined the #RightToRecall Movement, a non-partisan push for democratic accountability." />
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </div>
  );
}
