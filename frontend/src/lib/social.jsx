import { Instagram, Facebook, Youtube } from "lucide-react";

export const CONTACT_EMAIL = "socialservant@gmail.com";

export const XIcon = ({ className = "" }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24h-6.657l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

/*
 * `brand` is each platform's official colour, used where the icons are shown as
 * solid filled tiles. Kept as inline hex rather than Tailwind classes because
 * these are third-party brand colours, not part of this site's design tokens --
 * putting them in the theme would imply they are ours to restyle.
 *
 * `onBrand` is the foreground that clears contrast on that fill.
 */
export const SOCIAL_LINKS = [
  {
    label: "Instagram",
    href: "https://www.instagram.com/righttorecallmovement",
    Icon: Instagram,
    brand: "#E4405F",
    onBrand: "#ffffff",
  },
  {
    label: "Facebook",
    href: "https://www.facebook.com/share/18tKeR4YNr/",
    Icon: Facebook,
    brand: "#1877F2",
    onBrand: "#ffffff",
  },
  {
    label: "X (Twitter)",
    href: "https://x.com/RightToRecall_",
    Icon: XIcon,
    brand: "#000000",
    onBrand: "#ffffff",
  },
  {
    label: "YouTube",
    href: "https://youtube.com/@righttorecallmovement",
    Icon: Youtube,
    brand: "#FF0000",
    onBrand: "#ffffff",
  },
];
