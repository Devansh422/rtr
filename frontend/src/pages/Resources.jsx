import { useEffect, useState } from "react";
import { Reveal, MaskedLines, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import DynamicButton from "@/components/DynamicButton";
import { getResources, getFaq } from "@/lib/api";
import { toast } from "sonner";
import { FileText, Wrench, BookOpen } from "lucide-react";

const typeIcon = { Document: FileText, Toolkit: Wrench, Research: BookOpen };

export default function Resources() {
  const [resources, setResources] = useState([]);
  const [faq, setFaq] = useState([]);

  useEffect(() => {
    getResources()
      .then(setResources)
      .catch(() => {});
    getFaq()
      .then(setFaq)
      .catch(() => {});
  }, []);

  const handleDownload = async (r) => {
    // The resource file field is not yet wired to real storage, so this
    // acknowledges the request rather than fetching bytes.
    await new Promise((resolve) => setTimeout(resolve, 600));
    toast.success(`${r.title} is coming to your inbox soon!`);
  };

  return (
    <div data-testid="resources-page">
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          <p className="text-label font-bold uppercase text-secondary">Resources</p>
          <h1 className="mt-6 font-heading text-title-1 font-semibold leading-[0.95] tracking-tighter">
            <MaskedLines lines={["Everything you", "need to act."]} />
          </h1>
          <p className="mt-8 max-w-2xl text-lead text-foreground/70">
            Free toolkits, research, and templates. Download, share, and put democracy to work.
          </p>
        </div>
      </section>

      {/* Downloads */}
      <section className="full-section px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          <StaggerGroup className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {resources.map((r) => {
              const Icon = typeIcon[r.type] || FileText;
              return (
                <StaggerItem key={r.id}>
                  <div
                    className="group flex h-full flex-col rounded border border-border bg-card p-7 transition-transform duration-300 hover:-translate-y-2"
                    data-testid={`resource-card-${r.id}`}
                  >
                    <div className="flex h-12 w-12 items-center justify-center rounded bg-secondary">
                      <Icon className="h-6 w-6 text-secondary-foreground" />
                    </div>
                    <span className="mt-5 text-label font-bold uppercase text-muted-foreground">
                      {r.type}
                    </span>
                    <h3 className="mt-2 font-heading text-title-4 font-semibold tracking-tight">
                      {r.title}
                    </h3>
                    <p className="mt-2 flex-1 text-body text-foreground/70">{r.description}</p>
                    <DynamicButton
                      variant="outline"
                      size="sm"
                      className="mt-6 self-start"
                      data-testid={`resource-download-${r.id}`}
                      onClick={() => handleDownload(r)}
                    >
                      {r.downloadLabel || "Download"}
                    </DynamicButton>
                  </div>
                </StaggerItem>
              );
            })}
          </StaggerGroup>
        </div>
      </section>

      {/* FAQ */}
      <section className="full-section border-t border-border bg-muted/30 px-6 md:px-12">
        <div className="mx-auto w-full max-w-3xl">
          <Reveal>
            <p className="text-center text-label font-bold uppercase text-secondary">FAQ</p>
            <h2 className="mt-4 text-center font-heading text-title-1 font-semibold tracking-tight">
              Questions, answered.
            </h2>
          </Reveal>
          <Reveal delay={0.1}>
            <Accordion
              type="single"
              collapsible
              className="mt-12 space-y-3"
              data-testid="faq-accordion"
            >
              {faq.map((f) => (
                <AccordionItem
                  key={f.id}
                  value={f.id}
                  className="overflow-hidden rounded border border-border bg-card px-5"
                >
                  <AccordionTrigger
                    data-testid={`faq-trigger-${f.id}`}
                    className="text-left font-heading text-lead font-medium tracking-tight hover:no-underline"
                  >
                    {f.question}
                  </AccordionTrigger>
                  <AccordionContent className="text-foreground/70">{f.answer}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
