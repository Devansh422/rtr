import { useEffect, useRef } from "react";
import { Reveal, MaskedLines } from "@/components/motion/Reveal";
import { gsap, prefersReducedMotion } from "@/lib/motion";
import { useJoin } from "@/context/JoinContext";
import Eyebrow from "@/components/Eyebrow";
import DynamicButton from "@/components/DynamicButton";
import { Target, Eye, HeartHandshake, ArrowRight } from "lucide-react";

const CHAPTERS = [
  {
    n: "01",
    title: "What is Right to Recall?",
    text: "Right to Recall is a democratic mechanism that lets citizens formally review and, where the law allows, remove an elected representative before their term ends. Think of it as a feedback loop for democracy, a way to stay engaged between elections, not just on polling day.",
  },
  {
    n: "02",
    title: "Why India needs it",
    text: "India is the world's largest democracy and one of its youngest. With half the country under 30, the appetite for transparency and participation has never been higher. Recall provisions already exist in several state municipal and panchayat laws. This movement is about informed, responsible civic engagement with those tools.",
  },
];

const PRINCIPLES = [
  {
    icon: Eye,
    label: "Our Vision",
    tone: "bg-secondary text-secondary-foreground",
    text: "A democracy where every citizen feels the power to participate meaningfully, not once every few years, but as an ongoing, informed, and hopeful part of everyday civic life.",
  },
  {
    icon: Target,
    label: "Our Mission",
    tone: "bg-primary text-primary-foreground",
    text: "To educate a new generation about democratic accountability, provide practical civic tools, and build a peaceful, fact-based movement for responsible reform.",
  },
];

const TIMELINE = [
  {
    year: "The Idea",
    title: "A civic conversation begins",
    text: "Students and citizens start asking: what happens between elections? The idea of accountability tools gains momentum online.",
  },
  {
    year: "The Charter",
    title: "Citizen-drafted framework",
    text: "A model Right to Recall framework is drafted in the open: transparent, constitutional, and non-partisan.",
  },
  {
    year: "The Drive",
    title: "Campus Democracy Drive",
    text: "Civic literacy workshops reach hundreds of colleges, teaching first-time voters how accountability actually works.",
  },
  {
    year: "Today",
    title: "A growing movement",
    text: "Tens of thousands of supporters across 50+ cities, united by one idea: democracy works better with informed citizens.",
  },
];

export default function About() {
  const { openJoin } = useJoin();

  const journeyRef = useRef(null);
  const trackRef = useRef(null);

  /*
   * "The journey" scrolls horizontally while the section is pinned.
   *
   * The section sticks to the viewport and vertical scroll is translated into
   * horizontal movement of the track, so the timeline reads left-to-right as the
   * reader scrolls down. `end` is derived from the track's real overflow width so
   * the pin lasts exactly as long as there is content to travel, and
   * invalidateOnRefresh recomputes it on resize.
   *
   * Guarded by gsap.matchMedia so this only applies from 768px up. On narrow
   * screens pinning fights native touch scrolling, so the track stays a plain
   * swipeable overflow-x container instead (see the classes on the wrapper).
   * Under prefers-reduced-motion it is skipped entirely for the same reason.
   */
  useEffect(() => {
    const section = journeyRef.current;
    const track = trackRef.current;
    if (!section || !track || prefersReducedMotion()) return;

    const mm = gsap.matchMedia();

    mm.add("(min-width: 768px)", () => {
      const overflow = () => Math.max(0, track.scrollWidth - section.offsetWidth);

      const tween = gsap.to(track, {
        x: () => -overflow(),
        ease: "none",
        scrollTrigger: {
          trigger: section,
          start: "top top",
          end: () => `+=${overflow()}`,
          pin: true,
          scrub: 1,
          anticipatePin: 1,
          invalidateOnRefresh: true,
        },
      });

      return () => tween.kill();
    });

    return () => mm.revert();
  }, []);

  return (
    <div data-testid="about-page">
      {/*
       * ABOUT: the movement's position, the two chapters, and the two
       * principles, combined into one section.
       *
       * Content-height rather than full-viewport: there is far more than a
       * screen's worth here, so forcing 100vh would only add dead space. The
       * header splits (statement left, position right) and the four content
       * blocks sit inside one bordered object built from a `gap-px` grid over
       * `bg-border`, which draws the hairlines without any child needing its own
       * border.
       */}
      <section className="px-6 pb-20 pt-28 md:px-12 md:pb-28 md:pt-36">
        <div className="mx-auto w-full max-w-7xl">
          <div className="grid gap-8 border-b border-border pb-10 md:grid-cols-12 md:items-end">
            <div className="md:col-span-7">
              <Eyebrow>About the movement</Eyebrow>
              <h1 className="mt-gap-title font-heading text-title-1 font-extrabold">
                <MaskedLines lines={["Democracy is not", "a spectator sport."]} />
              </h1>
            </div>
            <Reveal delay={0.85} className="md:col-span-5">
              <p className="text-body text-foreground/70">
                We are a non-partisan civic movement. We do not support or oppose any party or
                individual. Our only agenda is democratic accountability and informed public
                engagement.
              </p>
            </Reveal>
          </div>

          <div className="mt-gap-block overflow-hidden rounded border border-border">
            {/* The two chapters: the argument */}
            <div className="grid gap-px bg-border md:grid-cols-2">
              {CHAPTERS.map((c) => (
                <div key={c.n} className="flex flex-col bg-card p-7 md:p-9">
                  <span className="font-heading text-title-1 font-extrabold leading-none text-primary/25">
                    {c.n}
                  </span>
                  <h2 className="mt-5 font-heading text-title-3 font-extrabold">{c.title}</h2>
                  <p className="mt-3 text-body text-foreground/70">{c.text}</p>
                </div>
              ))}
            </div>

            {/* The two principles: what we're for */}
            <div className="grid gap-px border-t border-border bg-border md:grid-cols-2">
              {PRINCIPLES.map((p) => (
                <div key={p.label} className="flex gap-5 bg-muted/40 p-7 md:p-9">
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded ${p.tone}`}
                  >
                    <p.icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="font-heading text-title-4 font-bold">{p.label}</h3>
                    <p className="mt-2 text-body text-foreground/70">{p.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/*
       * THE JOURNEY.
       *
       * From 768px up: the section pins and vertical scroll drives the track
       * sideways, so it must be exactly one viewport tall.
       *
       * Below 768px: no pin, no horizontal scroll at all. The track becomes a
       * plain vertical stack (`flex-col`, full-width cards, height auto) because a
       * sideways swipe region inside a vertically scrolling page is easy to miss
       * and fights the scroll direction the reader is already using.
       */}
      <section
        ref={journeyRef}
        data-testid="about-journey"
        className="flex flex-col justify-center overflow-hidden border-y border-border bg-muted/20 py-16 md:min-h-svh"
      >
        <div className="mx-auto w-full max-w-7xl px-6 md:px-12">
          <Reveal>
            <Eyebrow>The journey</Eyebrow>
            <h2 className="mt-gap-title font-heading text-title-2 font-extrabold">
              How we got here.
            </h2>
            <p className="mt-3 hidden text-body text-muted-foreground md:block">
              {/* Only shown where the movement IS sideways. */}
              Scroll to move through the timeline.
            </p>
          </Reveal>
        </div>

        <div className="mt-10 md:mt-12 md:overflow-x-hidden">
          <div
            ref={trackRef}
            className="flex w-full flex-col gap-4 px-6 md:w-max md:flex-row md:gap-6 md:px-12"
          >
            {TIMELINE.map((t, i) => (
              <article
                key={t.year}
                className="flex w-full flex-col rounded border border-border bg-card p-6 md:w-[24rem] md:shrink-0 md:p-7"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-primary font-heading text-micro font-bold text-primary-foreground">
                    {i + 1}
                  </span>
                  <Eyebrow>{t.year}</Eyebrow>
                </div>

                {/*
                 * Connector. Horizontal on desktop where cards sit side by side;
                 * the arrow is dropped on mobile since a stacked list reads
                 * top-to-bottom and a right-pointing arrow would misdirect.
                 */}
                <div className="mt-5 flex items-center gap-2" aria-hidden="true">
                  <span className="h-px flex-1 bg-border" />
                  {i < TIMELINE.length - 1 && (
                    <ArrowRight className="hidden h-3.5 w-3.5 text-muted-foreground md:block" />
                  )}
                </div>

                <h3 className="mt-5 font-heading text-title-4 font-bold">{t.title}</h3>
                <p className="mt-2 text-body text-foreground/70">{t.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-20 md:px-12 md:py-28">
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="rounded bg-primary p-10 text-center md:p-16">
              <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded bg-primary-foreground/10">
                <HeartHandshake className="h-6 w-6 text-primary-foreground" aria-hidden="true" />
              </div>
              <h2 className="mx-auto max-w-2xl font-heading text-title-2 font-extrabold text-primary-foreground">
                Ready to help build an accountable democracy?
              </h2>
              <DynamicButton
                onClick={openJoin}
                data-testid="about-join-button"
                size="lg"
                className="mt-8 bg-primary-foreground text-primary hover:bg-primary-foreground/90"
              >
                Join the Movement <ArrowRight className="h-5 w-5" />
              </DynamicButton>
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
