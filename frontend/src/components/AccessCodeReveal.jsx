import { toast } from "sonner";
import { Copy, KeyRound } from "lucide-react";
import LinkButton from "@/components/LinkButton";

/*
 * Shown exactly once, right after signup. This is the only place the access
 * code is ever displayed in plaintext -- it is deliberately never printed on
 * the supporter certificate, since that graphic is designed to be downloaded
 * and posted publicly. If it's lost, the only recovery path is contacting the
 * team (see MemberLogin's "Lost your code?" link); there is no SMTP configured
 * in this project for a self-service resend.
 */
export default function AccessCodeReveal({ code, email }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      toast.success("Access code copied!");
    } catch {
      toast.error("Could not copy code");
    }
  };

  return (
    <div
      data-testid="access-code-reveal"
      className="rounded border border-secondary bg-secondary/10 p-6 text-center"
    >
      <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded bg-secondary">
        <KeyRound className="h-5 w-5 text-secondary-foreground" aria-hidden="true" />
      </div>
      <h2 className="font-heading text-title-4 font-bold">Save your dashboard access code</h2>
      <p className="mx-auto mt-2 max-w-md text-body-sm text-muted-foreground">
        You'll need this with your email ({email}) to sign in to your dashboard later. We show it
        only once, so save it now.
      </p>
      <div className="mx-auto mt-5 flex max-w-xs items-stretch gap-2">
        <p
          data-testid="access-code-value"
          className="flex h-12 flex-1 items-center justify-center rounded border border-border bg-card font-heading text-title-4 font-bold tracking-widest"
        >
          {code}
        </p>
        <button
          type="button"
          data-testid="copy-access-code"
          onClick={copy}
          aria-label="Copy access code"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded bg-foreground text-background transition-opacity hover:opacity-85"
        >
          <Copy className="h-4 w-4" />
        </button>
      </div>
      <LinkButton to="/login" variant="outline" className="mt-5">
        Go to dashboard login
      </LinkButton>
    </div>
  );
}
