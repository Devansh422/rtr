import { cn } from "@/lib/utils";

/*
 * Single source of truth for button appearance.
 *
 * Buttons appear as three different elements across the site: a <button> for
 * actions (DynamicButton), a react-router <Link> for internal navigation, and an
 * <a> for external links. They must look identical, so the classes live here and
 * all three consume them. Previously each navigation "button" was a hand-written
 * class string, which drifted in height, padding and font size.
 *
 * Semantics for `variant`:
 *   default    the primary action in a view. One per view, ideally
 *   secondary  an equally weighted alternative action
 *   outline    a secondary action that should recede
 *   ghost      tertiary / toolbar actions
 *   link       inline text action, no chrome
 *   destructive irreversible actions
 *
 * Semantics for `size`, pick by context, not by taste:
 *   sm       inline with body copy, or inside a card
 *   default  standalone actions in a section
 *   lg       a page's single hero action
 *   icon     square, icon-only (always pair with aria-label)
 */

export const BUTTON_VARIANTS = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90",
  destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
  outline: "border border-border bg-card hover:bg-muted",
  secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/90",
  ghost: "hover:bg-muted",
  link: "text-primary underline-offset-4 hover:underline",
};

export const BUTTON_SIZES = {
  sm: "h-8 gap-1.5 px-3 text-meta",
  default: "h-10 gap-2 px-5 text-body",
  lg: "h-12 gap-2 px-7 text-lead",
  icon: "h-10 w-10",
};

const BUTTON_BASE = [
  "inline-flex select-none items-center justify-center whitespace-nowrap rounded",
  "font-heading font-semibold transition-colors",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
  "focus-visible:ring-offset-2 focus-visible:ring-offset-background",
  "disabled:cursor-not-allowed disabled:opacity-60",
  // Keep icons from being stretched by the flex container.
  "[&_svg]:shrink-0",
].join(" ");

export function buttonClasses({ variant = "default", size = "default", className = "" } = {}) {
  return cn(
    BUTTON_BASE,
    BUTTON_VARIANTS[variant] ?? BUTTON_VARIANTS.default,
    BUTTON_SIZES[size] ?? BUTTON_SIZES.default,
    className
  );
}
