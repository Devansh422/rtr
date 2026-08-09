import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import DynamicButton from "@/components/DynamicButton";
import { submitCorrection } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { Flag } from "lucide-react";

/*
 * "Suggest a correction", the §7 dispute workflow at the point of use.
 *
 * On every page that carries a factual claim about a named person or the text of the
 * Constitution. Two things it does that a generic feedback form would not:
 *
 * - It asks for a SOURCE, prominently, and says plainly that a correction with a
 *   public record attached is resolved much faster. That is true (the reviewer can
 *   act on it immediately) and it shifts the submission quality.
 * - It works without an account. Requiring sign-in to report an error about a
 *   powerful person filters out exactly the people most likely to know about one.
 */
export default function CorrectionDialog({ entityType, entityId, fieldKey, fieldLabel, triggerVariant = "outline" }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    summary: "",
    detail: "",
    proposed_value: "",
    source_url: "",
    source_title: "",
    contact_email: "",
  });

  const set = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await submitCorrection({
        entity_type: entityType,
        entity_id: entityId,
        field_key: fieldKey ?? "",
        ...form,
        contact_email: form.contact_email || undefined,
      });
      toast.success(result.message, { duration: 9000 });
      setOpen(false);
      setForm({
        summary: "",
        detail: "",
        proposed_value: "",
        source_url: "",
        source_title: "",
        contact_email: "",
      });
    } catch (error) {
      // The API returns structured policy flags for a refused submission, and the
      // person deserves to see which rule they hit rather than a generic failure.
      const detail = error?.response?.data?.detail;
      if (detail?.flags?.length) {
        toast.error(detail.flags[0].explanation, { duration: 12000 });
      } else {
        toast.error(typeof detail === "string" ? detail : "Could not file that correction.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <DynamicButton
          variant={triggerVariant}
          size="sm"
          data-testid={`correction-trigger-${fieldKey || entityId}`}
        >
          <Flag className="h-4 w-4" aria-hidden="true" />
          {t("common.suggestCorrection")}
        </DynamicButton>
      </DialogTrigger>

      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {t("common.suggestCorrection")}
            {fieldLabel ? `: ${fieldLabel}` : ""}
          </DialogTitle>
          <DialogDescription>
            A correction that cites a public record -- a court filing, an ECI affidavit, an RTI
            reply or an official order -- is acted on much faster, because a reviewer can check it
            against the source immediately.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="correction-summary">What is wrong?</Label>
            <Input
              id="correction-summary"
              required
              minLength={10}
              maxLength={300}
              value={form.summary}
              onChange={set("summary")}
              placeholder="One line: the figure, the claim, or the wording that is incorrect"
              data-testid="correction-summary"
            />
          </div>

          <div>
            <Label htmlFor="correction-source">Link to the public record</Label>
            <Input
              id="correction-source"
              type="url"
              value={form.source_url}
              onChange={set("source_url")}
              placeholder="https://..."
              data-testid="correction-source"
            />
            <p className="mt-1 text-meta text-foreground/60">
              Optional, but corrections without one wait for a researcher to find the source
              themselves.
            </p>
          </div>

          <div>
            <Label htmlFor="correction-proposed">What should it say instead?</Label>
            <Input
              id="correction-proposed"
              value={form.proposed_value}
              onChange={set("proposed_value")}
              placeholder="The correct figure or wording"
            />
          </div>

          <div>
            <Label htmlFor="correction-detail">Anything else a reviewer should know</Label>
            <Textarea
              id="correction-detail"
              rows={3}
              value={form.detail}
              onChange={set("detail")}
              placeholder="Do not include phone numbers, email addresses or ID numbers -- the form will refuse them."
            />
          </div>

          <div>
            <Label htmlFor="correction-email">Your email, if you want a reply</Label>
            <Input
              id="correction-email"
              type="email"
              value={form.contact_email}
              onChange={set("contact_email")}
              placeholder="Optional. Never published, and deleted on request."
            />
          </div>

          <DynamicButton type="submit" disabled={busy} className="w-full" data-testid="correction-submit">
            {busy ? "Sending..." : "File this correction"}
          </DynamicButton>
        </form>
      </DialogContent>
    </Dialog>
  );
}
