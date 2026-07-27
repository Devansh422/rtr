import { MessageCircle, Facebook, Instagram } from "lucide-react";
import { toast } from "sonner";
import { XIcon, SOCIAL_LINKS } from "@/lib/social";

const INSTAGRAM =
  SOCIAL_LINKS.find((s) => s.label === "Instagram")?.href ||
  "https://www.instagram.com/righttorecallmovement";

export default function SupporterShare() {
  const url = typeof window !== "undefined" ? window.location.origin : "";
  const message = `I just joined the #RightToRecall Movement, supporting greater accountability in democracy. Add your voice too:`;
  const full = `${message} ${url}`;

  const shares = [
    {
      key: "whatsapp",
      label: "WhatsApp",
      Icon: MessageCircle,
      className: "bg-[#25D366] text-white",
      href: `https://wa.me/?text=${encodeURIComponent(full)}`,
    },
    {
      key: "x",
      label: "X",
      Icon: XIcon,
      className: "bg-foreground text-background",
      href: `https://twitter.com/intent/tweet?text=${encodeURIComponent(message)}&url=${encodeURIComponent(url)}`,
    },
    {
      key: "facebook",
      label: "Facebook",
      Icon: Facebook,
      className: "bg-[#1877F2] text-white",
      href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(message)}`,
    },
  ];

  const shareInstagram = async () => {
    try {
      await navigator.clipboard.writeText(full);
      toast.success("Caption copied! Paste it into your Instagram story or post.");
    } catch {
      toast.message("Share on Instagram", {
        description: "Opening Instagram. Add your caption there.",
      });
    }
    window.open(INSTAGRAM, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="flex flex-wrap items-center justify-center gap-3" data-testid="supporter-share">
      {shares.map(({ key, label, Icon, className, href }) => (
        <a
          key={key}
          data-testid={`share-${key}`}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={`inline-flex items-center gap-2 rounded px-5 py-3 text-body font-semibold transition-transform hover:scale-105 active:scale-95 ${className}`}
        >
          <Icon className="h-4 w-4" /> {label}
        </a>
      ))}
      <button
        data-testid="share-instagram"
        onClick={shareInstagram}
        className="inline-flex items-center gap-2 rounded bg-gradient-to-tr from-[#F58529] via-[#DD2A7B] to-[#8134AF] px-5 py-3 text-body font-semibold text-white transition-transform hover:scale-105 active:scale-95"
      >
        <Instagram className="h-4 w-4" /> Instagram
      </button>
    </div>
  );
}
