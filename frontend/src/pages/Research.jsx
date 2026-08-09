import { useEffect, useState } from "react";
import { toast } from "sonner";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import DynamicButton from "@/components/DynamicButton";
import { PageHero, Section, SectionHeading, EmptyState, Pill, SourceLink } from "@/components/platform/Primitives";
import { getDocumentKinds, getDocuments, registerDownload } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { Download, ExternalLink, Search } from "lucide-react";

const ALL = "__all__";

export default function Research() {
  const { t } = useLocale();
  const [collection, setCollection] = useState("research");
  const [meta, setMeta] = useState({ kinds: [], licences: [] });
  const [documents, setDocuments] = useState({ items: [], total: 0 });
  const [kind, setKind] = useState(ALL);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getDocumentKinds().then(setMeta);
  }, []);

  useEffect(() => {
    getDocuments({
      collection,
      kind: kind === ALL ? undefined : kind,
      q: query || undefined,
      limit: 60,
    }).then(setDocuments);
  }, [collection, kind, query]);

  const open = async (document) => {
    try {
      const result = await registerDownload(document.slug);
      window.open(result.url, "_blank", "noopener,noreferrer");
      if (!result.isHostedHere) {
        toast.info("Opening the original source.", { duration: 4000 });
      }
    } catch {
      toast.error("Could not open that document.");
    }
  };

  const kindsForCollection = meta.kinds.filter((k) => k.collection === collection);

  return (
    <div data-testid="research-page">
      <PageHero
        eyebrow="Research Centre"
        lines={["The documents", "behind the claims."]}
        lede={t("research.lede")}
      />

      <Section>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <Tabs value={collection} onValueChange={(value) => { setCollection(value); setKind(ALL); }}>
            <TabsList>
              <TabsTrigger value="research">{t("research.title")}</TabsTrigger>
              <TabsTrigger value="media">{t("research.media")}</TabsTrigger>
            </TabsList>
          </Tabs>
          <p className="text-meta text-foreground/60">{documents.total} items</p>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:w-2/3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by title, author or summary"
              className="pl-9"
              aria-label="Search the repository"
            />
          </div>
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger aria-label="Filter by type">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All types</SelectItem>
              {kindsForCollection.map((k) => (
                <SelectItem key={k.key} value={k.key}>
                  {k.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="mt-8">
          {documents.items.length === 0 ? (
            <EmptyState
              title="Nothing here yet"
              body="The repository is built as research happens: judgments, affidavits, committee reports and datasets are added with their original source and a licence, so anyone can check what we relied on."
            />
          ) : (
            <StaggerGroup className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {documents.items.map((document) => (
                <StaggerItem key={document.id}>
                  <article className="flex h-full flex-col rounded border border-border bg-card p-5">
                    <div className="flex flex-wrap gap-2">
                      <Pill tone="muted">{document.kindLabel}</Pill>
                      {document.isHostedHere ? null : <Pill tone="muted">linked</Pill>}
                    </div>
                    <h3 className="mt-3 font-heading text-body font-semibold leading-snug tracking-tight">
                      {document.title}
                    </h3>
                    {document.authors || document.publisher ? (
                      <p className="mt-1 text-meta text-foreground/60">
                        {[document.authors, document.publisher].filter(Boolean).join(" · ")}
                        {document.publishedOn ? ` · ${document.publishedOn.slice(0, 4)}` : ""}
                      </p>
                    ) : null}
                    {document.summary ? (
                      <p className="mt-2 flex-1 text-meta text-foreground/70">{document.summary}</p>
                    ) : (
                      <div className="flex-1" />
                    )}

                    <p className="mt-3 text-meta text-foreground/50">
                      {t("research.licence")}: {document.licenceLabel}
                    </p>

                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <DynamicButton size="sm" variant="outline" onClick={() => open(document)}>
                        {document.isHostedHere ? (
                          <>
                            <Download className="h-4 w-4" aria-hidden="true" />
                            {t("research.download")}
                          </>
                        ) : (
                          <>
                            <ExternalLink className="h-4 w-4" aria-hidden="true" />
                            {t("research.hostedElsewhere")}
                          </>
                        )}
                      </DynamicButton>
                      <span className="text-meta text-foreground/50">
                        {document.downloadCount} opens
                      </span>
                    </div>

                    <SourceLink
                      citation={{ url: document.sourceUrl, title: "Original source" }}
                      className="mt-3"
                    />
                  </article>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>

      <Section muted>
        <SectionHeading
          eyebrow="Method"
          title="Why some documents are linked rather than hosted"
          lede="A Supreme Court judgment stays on the Court's own site. Rehosting adds nothing, and the canonical link is the citation — which is the whole point of a research repository. Where we do host a copy, the licence that permits it is recorded next to the file."
        />
      </Section>
    </div>
  );
}
