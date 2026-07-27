import { cn } from "@/lib/utils";

/*
 * The small uppercase label that sits above a section heading.
 *
 * It appeared ~20 times as a hand-written class string, which drifted (some had
 * tracking-widest, some tracking-wider, sizes varied). The tracking now lives in
 * the `text-label` type token, so this component only decides colour and weight.
 */
export default function Eyebrow({ children, className = "", as: Tag = "p", ...props }) {
  return (
    <Tag className={cn("text-label font-bold uppercase text-secondary", className)} {...props}>
      {children}
    </Tag>
  );
}
