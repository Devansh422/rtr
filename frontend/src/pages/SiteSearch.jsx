import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { PageHero, Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { getSearchCoverage, searchSite } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { Search as SearchIcon } from "lucide-react";

/*
 * Site-wide search.
 *
 * Publishes its own coverage. A visitor searching for their MLA and finding nothing
 * deserves to see that twelve representative profiles exist rather than four thousand,
 * instead of concluding the search is broken.
 */
export default function SiteSearch() {
  const { t } = useLocale();
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const [input, setInput] = useState(query);
  const [results, setResults] = useState({ total: 0, groups: [], items: [] });
  const [coverage, setCoverage] = useState({ types: [], total: 0 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSearchCoverage().then(setCoverage);
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults({ total: 0, groups: [], items: [] });
      return;
    }
    setLoading(true);
    searchSite(query, { limit: 40 })
      .then(setResults)
      .finally(() => setLoading(false));
  }, [query]);

  return (
    <div data-testid="search-page">
      <PageHero eyebrow="Search" lines={["Find it."]} lede="Across the Constitution Library, representative profiles, promises, petitions, research documents, courses and citizen reports.">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setParams(input.trim() ? { q: input.trim() } : {});
          }}
          className="relative max-w-xl"
        >
          <SearchIcon
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={t("common.searchPlaceholder")}
            className="pl-9"
            aria-label="Search the site"
            data-testid="site-search-input"
          />
        </form>
      </PageHero>

      <Section>
        {loading ? (
          <p className="text-body text-foreground/60">{t("common.loading")}</p>
        ) : query.trim().length < 2 ? (
          <div>
            <p className="text-label font-bold uppercase text-muted-foreground">
              What is searchable right now
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {coverage.types.map((type) => (
                <div key={type.type} className="rounded border border-border bg-card p-5">
                  <p className="font-heading text-title-3 font-semibold tracking-tight">
                    {type.count}
                  </p>
                  <p className="mt-1 text-meta text-foreground/60">{type.label}</p>
                </div>
              ))}
            </div>
            <p className="mt-6 max-w-2xl text-meta text-foreground/60">
              {coverage.total} pages indexed in total. The platform is built content by content, and
              this is the honest picture of how much of it exists so far.
            </p>
          </div>
        ) : results.total === 0 ? (
          <EmptyState
            title={`Nothing found for "${query}"`}
            body="Try an article number, a representative's name, or a subject like 'attendance' or 'panchayat'. The library does not yet cover the whole Constitution."
          />
        ) : (
          <div className="space-y-10">
            <p className="text-meta text-foreground/60">
              {results.total} result{results.total === 1 ? "" : "s"}
            </p>
            {results.groups.map((group) => (
              <div key={group.type}>
                <h2 className="font-heading text-title-4 font-semibold tracking-tight">
                  {group.label}
                  <span className="ml-2 text-body font-normal text-foreground/50">
                    {group.items.length}
                  </span>
                </h2>
                <ul className="mt-4 space-y-3">
                  {group.items.map((item) => (
                    <li key={`${item.entityType}-${item.entityId}`}>
                      <Link
                        to={item.url}
                        className="block rounded border border-border bg-card p-5 hover:border-primary/40"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-heading text-lead font-semibold tracking-tight">
                            {item.title}
                          </p>
                          {item.state ? <Pill tone="muted">{item.state}</Pill> : null}
                        </div>
                        {item.subtitle ? (
                          <p className="mt-1 text-meta text-foreground/60">{item.subtitle}</p>
                        ) : null}
                        {item.snippet ? (
                          <p className="mt-2 text-body text-foreground/75">{item.snippet}</p>
                        ) : null}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
