import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import LinkButton from "@/components/LinkButton";
import { PageHero, Section, SectionHeading, Pill } from "@/components/platform/Primitives";
import { getPilGuide, getRtiGuide, getTools } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { FileText, Scale, ShieldOff } from "lucide-react";

/*
 * Civic tools index, plus the RTI and PIL guidance.
 *
 * The PIL section is the interesting one: it explains the route and states plainly
 * that the platform will not draft a petition, then points at free legal aid. That
 * refusal is a feature, not a gap -- a template cannot know someone's facts, and a
 * badly drafted PIL is dismissed with costs.
 */
export default function Tools() {
  const { t } = useLocale();
  const [tools, setTools] = useState({ kinds: [], guides: [] });
  const [rti, setRti] = useState(null);
  const [pil, setPil] = useState(null);

  useEffect(() => {
    getTools().then(setTools);
    getRtiGuide().then(setRti);
    getPilGuide().then(setPil);
  }, []);

  const kinds = tools.kinds.filter((kind) => kind.templates.length);

  return (
    <div data-testid="tools-page">
      <PageHero
        eyebrow="Civic tools"
        lines={["Use the rights", "you already have."]}
        lede={t("tools.lede")}
      />

      <Section testId="tool-list">
        <SectionHeading
          title="Generators"
          lede="Each one is a template drafted from the statute and signed off by the legal team, filled in with what you type. Nothing you enter is stored."
        />
        <div className="mt-10 space-y-12">
          {kinds.map((kind) => (
            <div key={kind.key}>
              <h3 className="font-heading text-title-4 font-semibold tracking-tight">{kind.label}</h3>
              <StaggerGroup className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {kind.templates.map((template) => (
                  <StaggerItem key={template.key}>
                    <Link
                      to={`/tools/${template.key}`}
                      className="group flex h-full flex-col rounded border border-border bg-card p-6 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40"
                      data-testid={`tool-${template.key}`}
                    >
                      <div className="flex h-11 w-11 items-center justify-center rounded bg-secondary">
                        <FileText className="h-5 w-5 text-secondary-foreground" aria-hidden="true" />
                      </div>
                      <p className="mt-4 font-heading text-lead font-semibold tracking-tight group-hover:text-primary">
                        {template.title}
                      </p>
                      <p className="mt-2 flex-1 text-body text-foreground/70">
                        {template.description}
                      </p>
                      {template.state ? (
                        <Pill tone="muted" className="mt-3 self-start">
                          {template.state} only
                        </Pill>
                      ) : null}
                    </Link>
                  </StaggerItem>
                ))}
              </StaggerGroup>
            </div>
          ))}
        </div>
      </Section>

      {/* RTI guidance. */}
      {rti ? (
        <Section muted testId="rti-guide">
          <SectionHeading eyebrow="Guide" title={rti.title} lede={`Under the ${rti.statute}`} />
          <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_360px]">
            <ol className="space-y-4">
              {rti.steps.map((step) => (
                <li key={step.step} className="flex gap-4 rounded border border-border bg-card p-5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary font-heading text-meta font-bold text-primary-foreground">
                    {step.step}
                  </span>
                  <div>
                    <p className="font-heading text-lead font-semibold tracking-tight">{step.title}</p>
                    <p className="mt-1.5 text-body leading-relaxed text-foreground/75">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>

            <aside className="space-y-4">
              <div className="rounded border border-border bg-card p-6">
                <p className="font-heading text-lead font-semibold tracking-tight">
                  What can be withheld
                </p>
                <p className="mt-2 text-meta text-foreground/70">{rti.exemptions.note}</p>
                <ul className="mt-3 space-y-2">
                  {rti.exemptions.points.map((point) => (
                    <li key={point} className="text-meta leading-relaxed text-foreground/80">
                      &bull; {point}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded border border-border bg-muted/40 p-5">
                <p className="text-meta leading-relaxed text-foreground/70">{rti.disclaimer}</p>
              </div>
              <LinkButton to="/tools/rti-general" className="w-full">
                Generate an RTI application
              </LinkButton>
            </aside>
          </div>
        </Section>
      ) : null}

      {/* PIL Resource Centre. */}
      {pil ? (
        <Section testId="pil-guide">
          <SectionHeading eyebrow="PIL Resource Centre" title={pil.title} />
          <div className="mt-8 rounded border border-orange-700/30 bg-orange-700/5 p-6">
            <p className="flex items-start gap-3 text-body leading-relaxed text-foreground/85">
              <ShieldOff className="mt-0.5 h-5 w-5 shrink-0 text-orange-700" aria-hidden="true" />
              {pil.openingNote}
            </p>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {pil.basis.map((item) => (
              <div key={item.article} className="rounded border border-border bg-card p-6">
                <div className="flex items-center gap-2">
                  <Scale className="h-5 w-5 text-secondary" aria-hidden="true" />
                  <Link
                    to={`/constitution/${item.article}`}
                    className="font-heading text-lead font-semibold tracking-tight text-primary underline-offset-4 hover:underline"
                  >
                    Article {item.article}
                  </Link>
                </div>
                <p className="mt-2 font-heading text-body font-semibold tracking-tight">
                  {item.title}
                </p>
                <p className="mt-2 text-body text-foreground/75">{item.body}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 grid gap-10 lg:grid-cols-2">
            <div>
              <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                Who can file, and why courts scrutinise motive
              </h3>
              <p className="mt-3 text-body leading-relaxed text-foreground/75">{pil.whoCanFile}</p>

              <h3 className="mt-8 font-heading text-title-4 font-semibold tracking-tight">
                Before you talk to a lawyer
              </h3>
              <ul className="mt-3 space-y-2">
                {pil.checklist.map((item) => (
                  <li key={item} className="flex gap-2 text-body text-foreground/80">
                    <span aria-hidden="true" className="text-secondary">
                      &#9744;
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="font-heading text-title-4 font-semibold tracking-tight">
                Free legal help you are entitled to
              </h3>
              <div className="mt-3 space-y-4">
                {pil.freeLegalHelp.map((item) => (
                  <div key={item.name} className="rounded border border-border bg-card p-5">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="font-heading text-body font-semibold tracking-tight text-primary underline-offset-4 hover:underline"
                    >
                      {item.name}
                    </a>
                    <p className="mt-1.5 text-meta leading-relaxed text-foreground/75">
                      {item.detail}
                    </p>
                  </div>
                ))}
              </div>

              <h3 className="mt-8 font-heading text-title-4 font-semibold tracking-tight">
                What this platform does instead
              </h3>
              <ul className="mt-3 space-y-2">
                {pil.whatWeDoInstead.map((item) => (
                  <li key={item} className="text-body text-foreground/80">
                    &bull; {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-10 rounded border border-border bg-muted/40 p-6">
            <p className="text-meta leading-relaxed text-foreground/70">{pil.disclaimer}</p>
          </div>
        </Section>
      ) : null}
    </div>
  );
}
