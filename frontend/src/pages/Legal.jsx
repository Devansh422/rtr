import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageHero, Section, Pill } from "@/components/platform/Primitives";
import { getContentPolicy, getDisclaimer, getPrivacyPolicy } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";

/*
 * One component for the three published policies, chosen by `kind`.
 *
 * All of them are served from the API rather than written here, for the reason given
 * in backend/modules/legal/policies.py: a policy that lives in the frontend drifts
 * away from what the software actually does, and the version a user consented to
 * cannot be reconstructed. The page renders what the API says, whatever that is.
 */
export default function Legal({ kind = "privacy" }) {
  const { t } = useLocale();
  const [data, setData] = useState(null);

  useEffect(() => {
    const load =
      kind === "content-policy" ? getContentPolicy : kind === "disclaimer" ? getDisclaimer : getPrivacyPolicy;
    load().then(setData);
  }, [kind]);

  if (!data) {
    return (
      <Section>
        <p className="text-body text-foreground/60">{t("common.loading")}</p>
      </Section>
    );
  }

  // ---- Content policy ----
  if (kind === "content-policy") {
    return (
      <div data-testid="content-policy-page">
        <PageHero
          eyebrow="Content policy"
          lines={["What may be posted,", "and what is removed."]}
          lede="Published in full, because publishing it is what lets this platform credibly claim to be non-partisan. These are the same rules the software applies."
        >
          <Pill tone="muted">
            Version {data.version} &middot; effective {data.effective}
          </Pill>
        </PageHero>
        <Section>
          <div className="mx-auto w-full max-w-3xl space-y-8">
            {data.principles.map((principle, index) => (
              <div key={principle.title}>
                <h2 className="font-heading text-title-3 font-semibold tracking-tight">
                  {index + 1}. {principle.title}
                </h2>
                <p className="mt-3 text-body leading-relaxed text-foreground/80">{principle.body}</p>
              </div>
            ))}
            <p className="border-t border-border pt-6 text-meta text-foreground/60">
              If a moderator has removed something of yours and you think that was wrong, say so
              through the{" "}
              <Link to="/contact" className="text-primary underline-offset-4 hover:underline">
                contact form
              </Link>
              . Every removal is recorded in the audit log, so there is always a record to check.
            </p>
          </div>
        </Section>
      </div>
    );
  }

  // ---- Disclaimer ----
  if (kind === "disclaimer") {
    return (
      <div data-testid="disclaimer-page">
        <PageHero
          eyebrow="Disclaimer"
          lines={["Where our data", "comes from, and", "what it is not."]}
          lede={data.short}
        />
        <Section>
          <div className="mx-auto w-full max-w-3xl space-y-8">
            {data.full.map((section) => (
              <div key={section.heading}>
                <h2 className="font-heading text-title-3 font-semibold tracking-tight">
                  {section.heading}
                </h2>
                <p className="mt-3 text-body leading-relaxed text-foreground/80">{section.body}</p>
              </div>
            ))}
          </div>
        </Section>
      </div>
    );
  }

  // ---- Privacy policy ----
  return (
    <div data-testid="privacy-page">
      <PageHero
        eyebrow="Privacy"
        lines={["We collect as little", "as we can, and", "you can delete it."]}
        lede={data.summary}
      >
        <Pill tone="muted">
          Version {data.version} &middot; effective {data.effective} &middot; {data.statute}
        </Pill>
      </PageHero>

      <Section>
        <div className="mx-auto w-full max-w-3xl space-y-10">
          {data.sections.map((section) => (
            <div key={section.heading}>
              <h2 className="font-heading text-title-3 font-semibold tracking-tight">
                {section.heading}
              </h2>
              <p className="mt-3 whitespace-pre-line text-body leading-relaxed text-foreground/80">
                {section.body}
              </p>

              {/* The per-purpose table: exactly what is collected, why, for how long. */}
              {section.purposes ? (
                <div className="mt-6 space-y-4">
                  {data.purposes.map((purpose) => (
                    <div key={purpose.key} className="rounded border border-border bg-card p-5">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-heading text-lead font-semibold tracking-tight">
                          {purpose.label}
                        </p>
                        {purpose.required ? <Pill tone="secondary">Required to join</Pill> : (
                          <Pill tone="muted">Optional</Pill>
                        )}
                      </div>
                      <dl className="mt-3 space-y-1.5 text-meta text-foreground/80">
                        <div>
                          <dt className="inline font-semibold">Data: </dt>
                          <dd className="inline">{purpose.data.join(", ")}</dd>
                        </div>
                        <div>
                          <dt className="inline font-semibold">Why: </dt>
                          <dd className="inline">{purpose.why}</dd>
                        </div>
                        <div>
                          <dt className="inline font-semibold">Kept: </dt>
                          <dd className="inline">{purpose.retention}</dd>
                        </div>
                      </dl>
                    </div>
                  ))}
                </div>
              ) : null}

              {/* Your rights, and the exact place to exercise each one. */}
              {section.rights ? (
                <div className="mt-6 space-y-3">
                  {section.rights.map((right) => (
                    <div key={right.right} className="rounded border border-border bg-card p-5">
                      <p className="font-heading text-body font-semibold tracking-tight">
                        {right.right}
                      </p>
                      <p className="mt-1 text-meta text-foreground/75">{right.how}</p>
                    </div>
                  ))}
                  <Link
                    to="/dashboard"
                    className="inline-block text-body text-primary underline-offset-4 hover:underline"
                  >
                    Go to your dashboard to see, correct or delete your data
                  </Link>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
