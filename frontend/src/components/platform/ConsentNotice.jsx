import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Checkbox } from "@/components/ui/checkbox";
import { getConsentNotices } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { ShieldCheck } from "lucide-react";

/*
 * The DPDP consent notice that goes NEXT TO a submit button.
 *
 * §1 makes this a Phase-0 requirement, and §11 records that the erasure endpoint
 * shipped while this did not. The wording comes from `/api/legal/consent-notices`
 * rather than being written here, so a form's notice and the privacy policy cannot
 * drift apart -- which is the failure mode that makes a consent notice worthless.
 *
 * Two deliberate choices:
 *
 * - It is NOT a link to a policy. The Act requires an informed, specific notice, and
 *   "by continuing you agree to our privacy policy" is neither. The actual list of
 *   what is collected, why, and for how long is on screen.
 * - The checkbox is unticked and the parent controls its own submit button from
 *   `onChange`. A pre-ticked box is not consent.
 */
export default function ConsentNotice({ purpose, onChange, className, testId }) {
  const { t } = useLocale();
  const [spec, setSpec] = useState(null);
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    getConsentNotices().then((data) => {
      setSpec(data.purposes?.find((p) => p.key === purpose) ?? null);
    });
  }, [purpose]);

  useEffect(() => {
    onChange?.(agreed);
  }, [agreed, onChange]);

  if (!spec) {
    // Render nothing rather than a placeholder: a half-drawn consent notice next to
    // a live submit button is worse than a moment's absence.
    return null;
  }

  const inputId = `consent-${purpose}`;

  return (
    <div
      className={`rounded border border-border bg-muted/40 p-5 ${className ?? ""}`}
      data-testid={testId ?? `consent-notice-${purpose}`}
    >
      <p className="flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        {t("consent.title")}
      </p>

      <dl className="mt-3 space-y-2 text-meta leading-relaxed text-foreground/80">
        <div>
          <dt className="inline font-semibold">We will collect: </dt>
          <dd className="inline">{spec.data.join(", ")}.</dd>
        </div>
        <div>
          <dt className="inline font-semibold">Why: </dt>
          <dd className="inline">{spec.notice.split("Why: ")[1]?.split("How long:")[0] ?? spec.notice}</dd>
        </div>
        <div>
          <dt className="inline font-semibold">How long: </dt>
          <dd className="inline">{spec.retention}</dd>
        </div>
      </dl>

      <p className="mt-3 text-meta text-foreground/70">{t("consent.deleteAnytime")}</p>

      <label htmlFor={inputId} className="mt-4 flex cursor-pointer items-start gap-3">
        <Checkbox
          id={inputId}
          checked={agreed}
          onCheckedChange={(value) => setAgreed(value === true)}
          data-testid={`consent-checkbox-${purpose}`}
          className="mt-0.5"
        />
        <span className="text-body">
          {t("consent.agree")}{" "}
          <Link to="/privacy" className="text-primary underline-offset-4 hover:underline">
            {t("consent.readPolicy")}
          </Link>
        </span>
      </label>
    </div>
  );
}
