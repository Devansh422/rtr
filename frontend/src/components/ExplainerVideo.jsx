import { useEffect, useRef, useState } from "react";
import { Vote, Search, RefreshCw, Play, Pause, RotateCcw, SkipForward } from "lucide-react";
import { gsap, EASE, EASE_OUT, prefersReducedMotion } from "@/lib/motion";
import ChakraWheel from "@/components/ChakraWheel";

const SCENES = [
  {
    kicker: "In 30 seconds",
    title: "What is Right to Recall?",
    sub: "A simple idea for a stronger democracy.",
    tone: "bg-secondary text-white",
    Icon: ChakraWheel,
    iconWrap: "text-white",
  },
  {
    kicker: "Step 1",
    title: "You elect your representative.",
    sub: "Democracy begins with your vote.",
    tone: "bg-primary text-[#0b1030]",
    Icon: Vote,
    iconWrap: "text-[#0b1030]",
  },
  {
    kicker: "Step 2",
    title: "You stay informed.",
    sub: "Track their work with open data and RTI tools.",
    tone: "bg-card text-foreground border border-border",
    Icon: Search,
    iconWrap: "text-secondary",
  },
  {
    kicker: "Step 3",
    title: "If needed, you can recall.",
    sub: "Responsibly, and only where the constitution allows.",
    tone: "bg-chakra text-white",
    Icon: RefreshCw,
    iconWrap: "text-white",
  },
  {
    kicker: "The result",
    title: "Democracy that listens, all year round.",
    sub: "Not just on election day.",
    tone: "bg-secondary text-white",
    Icon: ChakraWheel,
    iconWrap: "text-white",
  },
];

const SCENE_MS = 6000;
const TOTAL = SCENES.length * SCENE_MS;

export default function ExplainerVideo({ onEnded, onSkip }) {
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const raf = useRef(null);
  const last = useRef(null);
  const endedFired = useRef(false);
  const sceneRef = useRef(null);

  useEffect(() => {
    const tick = (t) => {
      if (last.current == null) last.current = t;
      const dt = t - last.current;
      last.current = t;
      setElapsed((e) => {
        const next = Math.min(TOTAL, e + dt);
        if (next >= TOTAL && !endedFired.current) {
          endedFired.current = true;
          setPlaying(false);
          onEnded && onEnded();
        }
        return next;
      });
      raf.current = requestAnimationFrame(tick);
    };
    if (playing) {
      last.current = null;
      raf.current = requestAnimationFrame(tick);
    }
    return () => raf.current && cancelAnimationFrame(raf.current);
  }, [playing, onEnded]);

  const sceneIndex = Math.min(SCENES.length - 1, Math.floor(elapsed / SCENE_MS));
  const scene = SCENES[sceneIndex];
  const Icon = scene.Icon;

  /*
   * Scene transition. The scene div carries key={sceneIndex}, so React remounts
   * it on each advance and this effect re-runs -- the panel crossfades in and its
   * contents stagger up behind it.
   */
  useEffect(() => {
    const el = sceneRef.current;
    if (!el) return;

    const reduce = prefersReducedMotion();
    const ctx = gsap.context(() => {
      const tl = gsap.timeline();
      tl.from(el, {
        opacity: 0,
        scale: reduce ? 1 : 1.02,
        duration: reduce ? 0.2 : 0.5,
        ease: EASE,
      });
      tl.from(
        "[data-scene-item]",
        {
          opacity: 0,
          y: reduce ? 0 : 20,
          duration: reduce ? 0.2 : 0.5,
          stagger: reduce ? 0 : 0.1,
          ease: EASE_OUT,
        },
        0.15
      );
    }, el);

    return () => ctx.revert();
  }, [sceneIndex]);

  const replay = () => {
    endedFired.current = false;
    setElapsed(0);
    setPlaying(true);
  };

  return (
    <div className="w-full" data-testid="explainer-video">
      <div className="relative aspect-[4/3] overflow-hidden rounded border border-border sm:aspect-video">
        <div
          ref={sceneRef}
          key={sceneIndex}
          className={`absolute inset-0 flex flex-col items-center justify-center px-8 text-center ${scene.tone}`}
        >
          <div
            data-scene-item
            className={`mb-6 flex h-20 w-20 items-center justify-center ${scene.iconWrap}`}
          >
            <Icon
              className={Icon === ChakraWheel ? "h-16 w-16" : "h-14 w-14"}
              {...(Icon === ChakraWheel ? { spin: true } : {})}
            />
          </div>
          <p
            data-scene-item
            className="mb-3 text-meta font-bold uppercase tracking-[0.3em] opacity-80"
          >
            {scene.kicker}
          </p>
          <h3
            data-scene-item
            className="max-w-xl font-heading text-title-2 font-bold leading-tight"
          >
            {scene.title}
          </h3>
          <p data-scene-item className="mt-3 max-w-md text-lead opacity-90">
            {scene.sub}
          </p>
        </div>
      </div>

      {/* Segmented progress */}
      <div className="mt-4 flex gap-1.5" data-testid="explainer-progress">
        {SCENES.map((_, i) => {
          const segStart = i * SCENE_MS;
          const pct = Math.max(0, Math.min(1, (elapsed - segStart) / SCENE_MS)) * 100;
          return (
            <div key={i} className="h-1.5 flex-1 overflow-hidden rounded bg-muted">
              <div
                className="h-full rounded bg-primary transition-[width] duration-100"
                style={{ width: `${pct}%` }}
              />
            </div>
          );
        })}
      </div>

      {/* Controls */}
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            data-testid="explainer-playpause"
            onClick={() => setPlaying((p) => !p)}
            className="flex h-10 w-10 items-center justify-center rounded border border-border bg-card transition-colors hover:bg-muted"
            aria-label={playing ? "Pause" : "Play"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button
            data-testid="explainer-replay"
            onClick={replay}
            className="flex h-10 w-10 items-center justify-center rounded border border-border bg-card transition-colors hover:bg-muted"
            aria-label="Replay"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
        <button
          data-testid="explainer-skip"
          onClick={onSkip}
          className="inline-flex items-center gap-2 rounded px-4 py-2 text-body font-semibold text-muted-foreground transition-colors hover:text-foreground"
        >
          Skip <SkipForward className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
