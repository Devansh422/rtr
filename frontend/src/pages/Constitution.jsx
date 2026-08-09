import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem, Reveal } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import DynamicButton from "@/components/DynamicButton";
import { PageHero, Section, SectionHeading, EmptyState, Pill } from "@/components/platform/Primitives";
import { getArticles, getConstitutionParts } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { BookOpen, Search } from "lucide-react";

export default function Constitution() {
  const { t, locale } = useLocale();
  const [parts, setParts] = useState([]);
  const [articles, setArticles] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [part, setPart] = useState(null);
  const [tag, setTag] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getConstitutionParts().then(setParts);
  }, []);

  useEffect(() => {
    setLoading(true);
    getArticles({ q: query || undefined, part: part || undefined, tag: tag || undefined, locale, limit: 400 })
      .then((data) => {
        setArticles(data.items);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
  }, [query, part, tag, locale]);

  // Tags are derived from what is actually in the library rather than hardcoded, so
  // the filter row can never offer a tag with nothing behind it.
  const tags = useMemo(() => {
    const counts = new Map();
    articles.forEach((article) =>
      (article.tags ?? []).forEach((name) => counts.set(name, (counts.get(name) ?? 0) + 1))
    );
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  }, [articles]);

  const corePartNumbers = parts.filter((p) => p.isCore).map((p) => p.number);
  const grouped = useMemo(() => {
    const map = new Map();
    articles.forEach((article) => {
      const key = article.part || "Other";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(article);
    });
    return map;
  }, [articles]);

  return (
    <div data-testid="constitution-page">
      <PageHero
        eyebrow="Constitution Library"
        lines={["The Constitution,", "in plain language."]}
        lede={t("constitution.lede")}
      >
        <div className="relative max-w-xl">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by article number, title or subject"
            className="pl-9"
            aria-label="Search the Constitution Library"
            data-testid="constitution-search"
          />
        </div>
        <p className="mt-3 text-meta text-foreground/60">
          {total} article{total === 1 ? "" : "s"} in the library. The library grows as researchers
          add and review articles &mdash; it is not the full Constitution.
        </p>
      </PageHero>

      {/* Start here: the Parts a first-time reader actually needs. */}
      <Section muted testId="constitution-parts">
        <SectionHeading
          eyebrow="Start here"
          title="The Parts that matter most for accountability"
          lede="Twenty-two Parts and 395 articles is the same as nothing. These six are where the argument lives."
        />
        <StaggerGroup className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {parts
            .filter((p) => p.isCore)
            .map((p) => (
              <StaggerItem key={p.number}>
                <button
                  type="button"
                  onClick={() => setPart(part === p.number ? null : p.number)}
                  className={`w-full rounded border p-5 text-left transition-colors ${
                    part === p.number
                      ? "border-primary bg-primary/10"
                      : "border-border bg-card hover:border-primary/40"
                  }`}
                  data-testid={`part-${p.number}`}
                >
                  <p className="text-label font-bold uppercase text-secondary">Part {p.number}</p>
                  <p className="mt-2 font-heading text-lead font-semibold tracking-tight">{p.title}</p>
                  <p className="mt-1 text-meta text-foreground/60">Articles {p.articles}</p>
                </button>
              </StaggerItem>
            ))}
        </StaggerGroup>

        {/* All parts, including the repealed one -- silently renumbering around a
            repeal misleads anyone cross-referencing an older commentary. */}
        <details className="mt-8">
          <summary className="cursor-pointer text-body font-medium text-primary">
            All {parts.length} Parts of the Constitution
          </summary>
          <div className="mt-4 flex flex-wrap gap-2">
            {parts.map((p) => (
              <button
                key={p.number}
                type="button"
                onClick={() => setPart(part === p.number ? null : p.number)}
                disabled={p.repealed}
                className="disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Pill
                  tone={part === p.number ? "primary" : "default"}
                  className={corePartNumbers.includes(p.number) ? "font-semibold" : ""}
                >
                  {p.number}. {p.title}
                  {p.repealed ? " (repealed)" : ""}
                </Pill>
              </button>
            ))}
          </div>
        </details>
      </Section>

      {/* Filters + results */}
      <Section testId="constitution-articles">
        <SectionHeading
          title={
            part
              ? `Part ${part}: ${parts.find((p) => p.number === part)?.title ?? ""}`
              : "Every article in the library"
          }
          lede={`${articles.length} shown`}
          action={
            part || tag || query ? (
              <DynamicButton
                variant="ghost"
                size="sm"
                onClick={() => {
                  setPart(null);
                  setTag(null);
                  setQuery("");
                }}
              >
                {t("common.clearFilters")}
              </DynamicButton>
            ) : null
          }
        />

        {tags.length ? (
          <div className="mt-6 flex flex-wrap gap-2">
            {tags.map(([name, count]) => (
              <button key={name} type="button" onClick={() => setTag(tag === name ? null : name)}>
                <Pill tone={tag === name ? "primary" : "muted"}>
                  {name} <span className="ml-1 opacity-60">{count}</span>
                </Pill>
              </button>
            ))}
          </div>
        ) : null}

        {loading ? (
          <p className="mt-10 text-body text-foreground/60">{t("common.loading")}</p>
        ) : articles.length === 0 ? (
          <EmptyState
            title={t("common.noResults")}
            body="The library covers the core articles on fundamental rights, elections, the legislature and amendment. If the provision you want is not here yet, the full text is on India Code."
            action={
              <a
                href="https://www.indiacode.nic.in/handle/123456789/1362"
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary underline-offset-4 hover:underline"
              >
                Read the Constitution on India Code
              </a>
            }
          />
        ) : (
          <div className="mt-10 space-y-12">
            {[...grouped.entries()].map(([partNumber, items]) => (
              <div key={partNumber}>
                <h3 className="font-heading text-title-4 font-semibold tracking-tight text-foreground/80">
                  Part {partNumber}
                  <span className="ml-3 text-body font-normal text-foreground/50">
                    {items[0]?.partTitle}
                  </span>
                </h3>
                <StaggerGroup className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {items.map((article) => (
                    <StaggerItem key={article.number}>
                      <Link
                        to={`/constitution/${article.number}`}
                        className="group flex h-full flex-col rounded border border-border bg-card p-5 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40"
                        data-testid={`article-card-${article.number}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="flex h-9 items-center justify-center rounded bg-secondary px-2.5 font-heading text-meta font-bold text-secondary-foreground">
                            {article.number}
                          </span>
                          {article.hasOriginalText ? (
                            <Pill tone="muted">
                              <BookOpen className="mr-1 h-3 w-3" aria-hidden="true" />
                              full text
                            </Pill>
                          ) : null}
                        </div>
                        <p className="mt-3 flex-1 font-heading text-body font-semibold leading-snug tracking-tight group-hover:text-primary">
                          {article.title}
                        </p>
                        {article.tags?.length ? (
                          <p className="mt-3 text-meta text-foreground/50">
                            {article.tags.slice(0, 3).join(" · ")}
                          </p>
                        ) : null}
                      </Link>
                    </StaggerItem>
                  ))}
                </StaggerGroup>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section muted>
        <Reveal>
          <div className="rounded border border-border bg-card p-8">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              These explanations are ours, not the law
            </h2>
            <p className="mt-3 max-w-3xl text-body text-foreground/70">
              Every article page shows the verbatim constitutional text where we have transcribed
              it, and links to India Code where we have not. The plain-language explanation next to
              it is written by this movement to be readable. It is a paraphrase, and where the two
              differ, the original governs. If you think an explanation is wrong, there is a
              &ldquo;{t("common.suggestCorrection")}&rdquo; button on every page.
            </p>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
