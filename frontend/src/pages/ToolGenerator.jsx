import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { downloadDocx, generateDocument, getTemplate, openPrintView } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { AlertCircle, ArrowLeft, Download, Eye, Printer } from "lucide-react";

/*
 * The RTI / representation generator form.
 *
 * The field list, its help text and the legal basis all come from the template in the
 * API, so a template edit reaches the form without a frontend change -- and a
 * template still in legal review cannot be generated at all (the API refuses it).
 *
 * The warning that nothing is stored is prominent and true: the backend logs that a
 * document was generated and never what it said.
 */
export default function ToolGenerator() {
  const { key } = useParams();
  const { t } = useLocale();
  const [template, setTemplate] = useState(null);
  const [state, setState] = useState("loading");
  const [values, setValues] = useState({});
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getTemplate(key)
      .then((data) => {
        setTemplate(data);
        setState("ready");
        // Pre-fill today's date: it is the one field where a sensible default is
        // always right and typing it is pure friction.
        setValues((prev) => ({ ...prev, letter_date: new Date().toISOString().slice(0, 10) }));
      })
      .catch((error) => setState(error?.response?.status === 409 ? "review" : "missing"));
  }, [key]);

  const set = (name) => (value) => setValues((prev) => ({ ...prev, [name]: value }));

  const missing = useMemo(
    () =>
      (template?.fields ?? [])
        .filter((field) => field.required && !String(values[field.name] ?? "").trim())
        .map((field) => field.label),
    [template, values]
  );

  const run = async (mode) => {
    setBusy(true);
    try {
      if (mode === "preview") {
        setPreview(await generateDocument(key, values));
      } else if (mode === "docx") {
        await downloadDocx(key, values, `${key}.docx`);
        toast.success("Downloaded. Edit it before you send it.");
      } else {
        openPrintView(key, values);
      }
    } catch (error) {
      const detail = error?.response?.data?.detail;
      toast.error(
        detail?.missing?.length
          ? `Still needed: ${detail.missing.join(", ")}`
          : typeof detail === "string"
            ? detail
            : "Could not generate that document."
      );
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") {
    return (
      <Section>
        <p className="text-body text-foreground/60">{t("common.loading")}</p>
      </Section>
    );
  }
  if (state !== "ready") {
    return (
      <Section>
        <EmptyState
          title={state === "review" ? "This template is awaiting legal review" : "Template not found"}
          body={
            state === "review"
              ? "Templates state what the law requires, so they are not usable until the legal team has signed off on the current wording. That gate is deliberate."
              : "Check the address, or pick a tool from the index."
          }
          action={<LinkButton to="/tools">All civic tools</LinkButton>}
        />
      </Section>
    );
  }

  return (
    <div data-testid={`tool-generator-${key}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-4xl">
          <Link
            to="/tools"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.tools")}
          </Link>
          <div className="mt-6 flex flex-wrap gap-2">
            <Pill tone="muted">{template.kindLabel}</Pill>
            {template.isLegallyApproved ? <Pill tone="primary">Legal team approved</Pill> : null}
          </div>
          <h1 className="mt-5 font-heading text-title-2 font-semibold leading-[1.1] tracking-tighter">
            {template.title}
          </h1>
          <p className="mt-4 text-lead text-foreground/75">{template.description}</p>
        </div>
      </section>

      <Section>
        <div className="mx-auto grid w-full max-w-6xl gap-10 lg:grid-cols-[1fr_340px]">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              run("preview");
            }}
            className="space-y-5"
          >
            <div className="rounded border border-amber-600/30 bg-amber-600/10 p-4">
              <p className="flex items-start gap-2 text-meta leading-relaxed text-foreground/85">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
                {t("tools.nothingStored")}
              </p>
            </div>

            {template.fields.map((field) => {
              const id = `field-${field.name}`;
              return (
                <div key={field.name}>
                  <Label htmlFor={id}>
                    {field.label}
                    {field.required ? <span className="ml-1 text-destructive">*</span> : null}
                  </Label>

                  {field.type === "textarea" ? (
                    <Textarea
                      id={id}
                      rows={field.maxLength && field.maxLength > 1500 ? 8 : 4}
                      maxLength={field.maxLength}
                      required={field.required}
                      value={values[field.name] ?? ""}
                      onChange={(event) => set(field.name)(event.target.value)}
                    />
                  ) : field.type === "select" ? (
                    <Select
                      value={values[field.name] ?? ""}
                      onValueChange={set(field.name)}
                    >
                      <SelectTrigger id={id}>
                        <SelectValue placeholder="Choose one" />
                      </SelectTrigger>
                      <SelectContent>
                        {(field.options ?? []).map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      id={id}
                      type={field.type === "date" ? "date" : "text"}
                      maxLength={field.maxLength}
                      required={field.required}
                      value={values[field.name] ?? ""}
                      onChange={(event) => set(field.name)(event.target.value)}
                    />
                  )}

                  {field.help ? (
                    <p className="mt-1 text-meta leading-relaxed text-foreground/60">{field.help}</p>
                  ) : null}
                </div>
              );
            })}

            <div className="flex flex-wrap gap-3 border-t border-border pt-5">
              <DynamicButton type="submit" disabled={busy || missing.length > 0}>
                <Eye className="h-4 w-4" aria-hidden="true" />
                {t("tools.preview")}
              </DynamicButton>
              <DynamicButton
                type="button"
                variant="outline"
                disabled={busy || missing.length > 0}
                onClick={() => run("docx")}
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                {t("tools.downloadDocx")}
              </DynamicButton>
              <DynamicButton
                type="button"
                variant="outline"
                disabled={busy || missing.length > 0}
                onClick={() => run("print")}
              >
                <Printer className="h-4 w-4" aria-hidden="true" />
                {t("tools.printPdf")}
              </DynamicButton>
            </div>

            {missing.length ? (
              <p className="text-meta text-foreground/60">Still needed: {missing.join(", ")}.</p>
            ) : null}
          </form>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            <div className="rounded border border-border bg-card p-6">
              <p className="text-label font-bold uppercase text-secondary">{t("tools.legalBasis")}</p>
              <p className="mt-2 text-meta leading-relaxed text-foreground/80">
                {template.legalBasis}
              </p>
            </div>
            <div className="rounded border border-border bg-card p-6">
              <p className="text-label font-bold uppercase text-secondary">
                {t("tools.filingNotes")}
              </p>
              <p className="mt-2 whitespace-pre-line text-meta leading-relaxed text-foreground/80">
                {template.filingNotes}
              </p>
            </div>
          </aside>
        </div>

        {preview ? (
          <div className="mx-auto mt-12 w-full max-w-4xl" data-testid="tool-preview">
            <h2 className="font-heading text-title-4 font-semibold tracking-tight">
              {t("tools.preview")}
            </h2>
            <p className="mt-2 text-meta text-foreground/60">{preview.disclaimer}</p>
            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded border border-border bg-card p-6 font-sans text-body leading-relaxed">
              {preview.text}
            </pre>
          </div>
        ) : null}
      </Section>
    </div>
  );
}
