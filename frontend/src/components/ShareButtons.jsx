import { Facebook, Link2, Share2 } from "lucide-react";
import { toast } from "sonner";
import { XIcon } from "@/lib/social";

/*
 * Share row.
 *
 * Platform buttons carry their own brand colour as a solid fill, so they are
 * recognisable at a glance rather than reading as generic outlined icons. The two
 * non-platform actions (copy link, native share) use the site's own foreground
 * token, since inventing a brand colour for them would be misleading.
 *
 * Brand hexes are inline rather than themed: they belong to those platforms, not
 * to this design system, so they must not be restyled along with the rest of the
 * site. The X mark uses the shared XIcon -- lucide's `Twitter` glyph is the old
 * bird, which is no longer that platform's brand.
 */
const TILE =
  "flex h-10 w-10 items-center justify-center rounded transition-opacity hover:opacity-85 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
  "focus-visible:ring-offset-background";

export default function ShareButtons({
  title = "Join the #RightToRecall Movement",
  url: urlProp,
  className = "",
}) {
  const url = urlProp || (typeof window !== "undefined" ? window.location.href : "");
  const text = encodeURIComponent(title);
  const enc = encodeURIComponent(url);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied!");
    } catch {
      toast.error("Could not copy link");
    }
  };

  const nativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch {
        /* user cancelled */
      }
    } else {
      copy();
    }
  };

  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="share-buttons">
      <a
        data-testid="share-twitter"
        href={`https://twitter.com/intent/tweet?text=${text}&url=${enc}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share on X"
        className={TILE}
        style={{ backgroundColor: "#000000", color: "#ffffff" }}
      >
        <XIcon className="h-4 w-4" />
      </a>

      <a
        data-testid="share-facebook"
        href={`https://www.facebook.com/sharer/sharer.php?u=${enc}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share on Facebook"
        className={TILE}
        style={{ backgroundColor: "#1877F2", color: "#ffffff" }}
      >
        <Facebook className="h-4 w-4" aria-hidden="true" />
      </a>

      <button
        type="button"
        data-testid="share-copy"
        onClick={copy}
        aria-label="Copy link"
        className={`${TILE} bg-foreground text-background`}
      >
        <Link2 className="h-4 w-4" aria-hidden="true" />
      </button>

      <button
        type="button"
        data-testid="share-native"
        onClick={nativeShare}
        className="inline-flex h-10 items-center gap-2 rounded bg-foreground px-4 font-heading text-meta font-semibold text-background transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <Share2 className="h-4 w-4" aria-hidden="true" /> Share
      </button>
    </div>
  );
}
