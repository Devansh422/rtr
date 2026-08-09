import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Input } from "@/components/ui/input";
import DynamicButton from "@/components/DynamicButton";
import { PageHero, Section, Pill } from "@/components/platform/Primitives";
import { verifyCertificate } from "@/lib/platformApi";
import { AlertTriangle, BadgeCheck, Search } from "lucide-react";

/*
 * Public certificate verification.
 *
 * Unauthenticated by design: the person checking is an employer or a university, not
 * a member. It shows the holder's name, what the certificate was for and whether it
 * is still valid — and nothing else. Not their email, not their other certificates.
 */
export default function CertificateVerify() {
  const { code: codeParam } = useParams();
  const [code, setCode] = useState(codeParam ?? "");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const check = async (value) => {
    const target = (value ?? code).trim().toUpperCase();
    if (!target) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await verifyCertificate(target));
    } catch (caught) {
      setError(caught?.response?.data?.detail ?? "Could not check that code.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (codeParam) check(codeParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codeParam]);

  return (
    <div data-testid="certificate-verify-page">
      <PageHero
        eyebrow="Verify a certificate"
        lines={["Is this certificate", "genuine?"]}
        lede="Every certificate this platform issues carries a short code. Type it here to confirm who holds it, what it was for, and whether it is still valid."
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            check();
          }}
          className="flex max-w-md gap-2"
        >
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="RTR-XXXX-XXXX"
              className="pl-9 font-mono uppercase"
              aria-label="Certificate code"
              data-testid="certificate-code-input"
            />
          </div>
          <DynamicButton type="submit" disabled={busy}>
            {busy ? "Checking..." : "Verify"}
          </DynamicButton>
        </form>
      </PageHero>

      <Section>
        <div className="mx-auto w-full max-w-2xl">
          {error ? (
            <div className="rounded border border-destructive/30 bg-destructive/5 p-6">
              <p className="flex items-start gap-2 font-heading text-lead font-semibold tracking-tight">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
                Not verified
              </p>
              <p className="mt-2 text-body text-foreground/75">{error}</p>
            </div>
          ) : null}

          {result ? (
            <div
              className={`rounded border p-7 ${
                result.valid ? "border-primary/30 bg-primary/5" : "border-destructive/30 bg-destructive/5"
              }`}
              data-testid="certificate-result"
            >
              <p className="flex items-center gap-2 font-heading text-title-4 font-semibold tracking-tight">
                {result.valid ? (
                  <BadgeCheck className="h-6 w-6 text-primary" aria-hidden="true" />
                ) : (
                  <AlertTriangle className="h-6 w-6 text-destructive" aria-hidden="true" />
                )}
                {result.valid ? "Genuine certificate" : "This certificate has been revoked"}
              </p>

              <dl className="mt-6 space-y-3">
                <div>
                  <dt className="text-label font-bold uppercase text-muted-foreground">Holder</dt>
                  <dd className="mt-0.5 font-heading text-lead font-semibold tracking-tight">
                    {result.holderName}
                  </dd>
                </div>
                <div>
                  <dt className="text-label font-bold uppercase text-muted-foreground">For</dt>
                  <dd className="mt-0.5 text-body">{result.title}</dd>
                </div>
                <div>
                  <dt className="text-label font-bold uppercase text-muted-foreground">Type</dt>
                  <dd className="mt-0.5 text-body">{result.kindLabel}</dd>
                </div>
                <div>
                  <dt className="text-label font-bold uppercase text-muted-foreground">Issued</dt>
                  <dd className="mt-0.5 text-body">
                    {result.issuedAt ? new Date(result.issuedAt).toLocaleDateString() : "-"} by{" "}
                    {result.issuer}
                  </dd>
                </div>
                {Object.entries(result.detail ?? {})
                  .filter(([key]) => !key.endsWith("Slug"))
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt className="text-label font-bold uppercase text-muted-foreground">{key}</dt>
                      <dd className="mt-0.5 text-body">{String(value)}</dd>
                    </div>
                  ))}
              </dl>

              {result.revokedReason ? (
                <p className="mt-5 rounded border border-destructive/30 bg-card p-4 text-meta text-foreground/80">
                  <strong className="font-semibold">Reason: </strong>
                  {result.revokedReason}
                </p>
              ) : null}

              <div className="mt-6 flex flex-wrap gap-2">
                <Pill tone="muted">Code: {result.code}</Pill>
                <Pill tone={result.valid ? "primary" : "default"}>
                  {result.valid ? "Valid" : "Revoked"}
                </Pill>
              </div>
            </div>
          ) : null}

          {!result && !error ? (
            <p className="text-body text-foreground/60">
              Codes look like <span className="font-mono">RTR-K7M2-9PQX</span>. They never contain
              the letters O or I, or the digits 0 or 1, so those are the characters to double-check
              if a code will not verify.
            </p>
          ) : null}
        </div>
      </Section>
    </div>
  );
}
