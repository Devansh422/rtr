import { useEffect, useState } from "react";
import { Search } from "lucide-react";

import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHero, Section, EmptyState, Disclaimer } from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import { DocumentCard } from "@/components/manifesto/DocumentPreview";
import { getManifestoDocuments, getManifestoVocabulary } from "@/lib/platformApi";

/*
 * The document register (§11, §18).
 *
 * Every official record obtained about a manifesto promise -- orders,
 * notifications, sanction orders, department reports, budget documents,
 * correspondence -- listed on its own rather than only inside the promise it
 * belongs to. A researcher looking for "every sanction order the PWD issued in
 * 2023" is asking a question no promise page answers.
 *
 * NOTHING HERE IS EDITED. The platform stores metadata beside each file and never
 * over it: what you open is the document as the department issued it. Where the
 * record is still live on an official domain, the card says so -- a copy on
 * uk.gov.in and a copy someone re-hosted are not equally good evidence, and the
 * reader is told which one they have.
 */

const ALL = "__all__";

export default function ManifestoDocuments() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [kinds, setKinds] = useState([]);
  const [kind, setKind] = useState(ALL);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getManifestoVocabulary().then((vocabulary) => setKinds(vocabulary?.documentKinds ?? []));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setLoading(true);
    getManifestoDocuments({
      kind: kind === ALL ? undefined : kind,
      q: search || undefined,
      limit: 200,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [kind, search]);

  return (
    <div data-testid="manifesto-documents-page">
      <PageHero
        eyebrow="Evidence"
        lines={["The government's", "own records."]}
        lede="Orders, notifications, sanction orders and reports obtained about Uttarakhand manifesto promises. Each is published as issued, with a note saying where the copy came from."
      />

      <ModuleNav />

      <Section>
        <div className="grid gap-3 sm:grid-cols-2 lg:w-2/3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by title, authority or reference number"
              aria-label="Search documents"
              className="pl-9"
            />
          </div>
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger aria-label="Filter by document type">
              <SelectValue placeholder="All document types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All document types</SelectItem>
              {kinds.map((item) => (
                <SelectItem key={item.key} value={item.key}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <p className="mt-4 text-meta text-foreground/60">
          {loading ? "Loading…" : `${data.total} document${data.total === 1 ? "" : "s"} published`}
        </p>

        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">Loading…</p>
          ) : data.items.length === 0 ? (
            <EmptyState
              title="No documents match this filter"
              body="Documents are published as they are obtained, most of them attached to RTI replies. A promise with no documents on file says so on its own page."
            />
          ) : (
            <StaggerGroup className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {data.items.map((document) => (
                <StaggerItem key={document.id}>
                  <DocumentCard document={document} />
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>

        <div className="mt-10">
          <Disclaimer
            title="About these documents"
            text="Files are preserved exactly as received and are never edited, re-typeset or annotated. Where a document is still published on an official government domain, that link is given as the primary source; a copy held here is marked as a secondary copy."
          />
        </div>
      </Section>
    </div>
  );
}
