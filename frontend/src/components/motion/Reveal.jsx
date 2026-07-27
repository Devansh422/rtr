import { cloneElement, useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

/*
 * Scroll and entrance primitives, GSAP-backed.
 *
 * The public API is deliberately identical to the framer-motion version these
 * replaced (Reveal / MaskedLines / StaggerGroup / StaggerItem, same props), so
 * the nine pages consuming them needed no changes.
 *
 * Every animation runs inside a gsap.context() whose cleanup reverts both the
 * tweens and their ScrollTriggers on unmount. Without that, route changes leak
 * triggers and elements can stay stuck at opacity 0.
 */

// Matches the cubic-bezier the design previously used: [0.76, 0, 0.24, 1].
const EASE = "power4.inOut";

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export const Reveal = ({ children, delay = 0, y = 40, className = "", ...props }) => {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce = prefersReducedMotion();
    const ctx = gsap.context(() => {
      gsap.from(el, {
        opacity: 0,
        // Reduced-motion users get the fade but none of the travel.
        y: reduce ? 0 : y,
        duration: reduce ? 0.3 : 0.8,
        delay,
        ease: EASE,
        scrollTrigger: {
          trigger: el,
          // bottom-=80 mirrors the old viewport={{ margin: "-80px" }}.
          start: "top bottom-=80",
          once: true,
        },
      });
    }, el);

    return () => ctx.revert();
  }, [delay, y]);

  return (
    <div ref={ref} className={className} {...props}>
      {children}
    </div>
  );
};

/*
 * Line-by-line masked reveal. Each line sits in an overflow-hidden wrapper and
 * slides up from fully below its own box. Fires on mount rather than on scroll,
 * matching the original -- these are used for above-the-fold headings.
 */
export const MaskedLines = ({ lines = [], className = "", lineClassName = "", start = 0 }) => {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const targets = el.querySelectorAll("[data-masked-line]");
    if (!targets.length) return;

    const reduce = prefersReducedMotion();
    const ctx = gsap.context(() => {
      if (reduce) {
        gsap.fromTo(
          targets,
          { opacity: 0 },
          { opacity: 1, duration: 0.3, delay: start, stagger: 0.05 }
        );
        return;
      }
      gsap.fromTo(
        targets,
        { yPercent: 110 },
        { yPercent: 0, duration: 1.1, delay: start, ease: EASE, stagger: 0.12 }
      );
    }, el);

    return () => ctx.revert();
  }, [start, lines.length]);

  return (
    <span ref={ref} className={className}>
      {lines.map((line, i) => (
        <span key={i} className="block overflow-hidden">
          <span data-masked-line className={`block ${lineClassName}`}>
            {line}
          </span>
        </span>
      ))}
    </span>
  );
};

/*
 * Passes an index and stagger step down to StaggerItem children so each item can
 * offset its own delay. Kept as cloneElement to preserve the original contract.
 */
export const StaggerGroup = ({ children, className = "", stagger = 0.12 }) => {
  const items = Array.isArray(children) ? children : [children];
  return (
    <div className={className}>
      {items.map((child, i) =>
        child ? cloneElement(child, { key: child.key ?? i, _index: i, _stagger: stagger }) : child
      )}
    </div>
  );
};

export const StaggerItem = ({ children, className = "", y = 40, _index = 0, _stagger = 0.12 }) => {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce = prefersReducedMotion();
    const ctx = gsap.context(() => {
      gsap.from(el, {
        opacity: 0,
        y: reduce ? 0 : y,
        duration: reduce ? 0.3 : 0.7,
        delay: _index * _stagger,
        ease: EASE,
        scrollTrigger: {
          trigger: el,
          start: "top bottom-=60",
          once: true,
        },
      });
    }, el);

    return () => ctx.revert();
  }, [y, _index, _stagger]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
};
