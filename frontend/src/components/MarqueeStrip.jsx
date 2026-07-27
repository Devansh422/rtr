import Marquee from "react-fast-marquee";
import ChakraWheel from "@/components/ChakraWheel";

/*
 * Scrolling slogan band. Deliberately short: it anchors the bottom edge of a
 * section, so it should read as a rule with text in it rather than as a block of
 * its own. Height is driven by the type token plus tight padding.
 */
export default function MarqueeStrip({ items, speed = 40, className = "" }) {
  const words = items || [
    "ACCOUNTABILITY",
    "INFORMED CITIZENS",
    "DEMOCRATIC REFORM",
    "YOUR VOICE",
    "TRANSPARENCY",
    "CIVIC POWER",
    "THE FUTURE IS OURS",
  ];

  return (
    <div
      className={`marquee-clip border-y border-foreground/10 bg-primary py-2 ${className}`}
      data-testid="marquee-strip"
    >
      <Marquee speed={speed} gradient={false} autoFill>
        {words.map((w, i) => (
          <span
            key={i}
            className="mx-4 inline-flex items-center gap-4 font-heading text-meta font-bold uppercase tracking-[0.14em] text-primary-foreground"
          >
            {w}
            <ChakraWheel className="h-3 w-3 text-chakra" />
          </span>
        ))}
      </Marquee>
    </div>
  );
}
