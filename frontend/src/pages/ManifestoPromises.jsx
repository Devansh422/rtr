import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Search } from "lucide-react";

import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHero, Section, EmptyState, Pill } from "@/components/platform/Primitives";
import ModuleNav from "@/components/manifesto/ModuleNav";
import { PromiseStatusBadge, RtiStatusPill } from "@/components/manifesto/StatusBadge";
import LinkButton from "@/components/LinkButton";
import DynamicButton from "@/components/DynamicButton";
import { getManifestoFilters, getManifestoPromises } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";

/*
 * Every published promise, searchable (§6, §15).
 *
 * FILTER OPTIONS COME FROM THE DATA. `/manifesto/filters` returns only
 * departments and categories that actually have promises behind them, with
 * counts, so the page cannot offer a filter that returns an empty list. A filter
 * that yields nothing reads as a broken site, and on this module it would read as
 * a missing record.
 *
 * SEARCH COVERS THE PROMISE TEXT, not just the title. Somebody looking for
 * "Gairsain" is looking for a word the party printed in its manifesto, not for
 * the heading a volunteer later wrote above it.
 *
 * THE CARD SHOWS THREE SEPARATE THINGS -- RTI status, whether evidence is on
 * file, and the assessed status -- because they answer different questions and
 * routinely disagree. "Reply received / no evidence published / status not
 * established" is a real and common combination, and collapsing it into one
 * badge would hide the state of the research.
 */

const ALL = "__all__";
const DEBOUNCE_MS = 300;

export default function ManifestoPromises() {
  const { locale } = useLocale();
  const hi = locale === "hi";

  const [data, setData] = useState({ items: [], total: 0 });
  const [options, setOptions] = useState({
    departments: [],
    categories: [],
    statuses: [],
    rtiStatuses: [],
  });
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({
    department: ALL,
    category: ALL,
    status: ALL,
    rtiStatus: ALL,
    sort: "code",
  });
  const [loading, setLoading] = useState(true);
  const [shown, setShown] = useState(24);

  useEffect(() => {
    getManifestoFilters().then(setOptions);
  }, []);

  // Debounced so typing a promise code does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setLoading(true);
    getManifestoPromises({
      q: search || undefined,
      department: filters.department === ALL ? undefined : filters.department,
      category: filters.category === ALL ? undefined : filters.category,
      status: filters.status === ALL ? undefined : filters.status,
      rti_status: filters.rtiStatus === ALL ? undefined : filters.rtiStatus,
      sort: filters.sort,
      limit: 100,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [search, filters]);

  const set = useCallback((key, value) => {
    setShown(24);
    setFilters((previous) => ({ ...previous, [key]: value }));
  }, []);

  const clear = () => {
    setQuery("");
    setFilters({ department: ALL, category: ALL, status: ALL, rtiStatus: ALL, sort: "code" });
  };

  const filtered =
    search ||
    filters.department !== ALL ||
    filters.category !== ALL ||
    filters.status !== ALL ||
    filters.rtiStatus !== ALL;

  return (
    <div data-testid="manifesto-promises-page">
      <PageHero
        eyebrow="Uttarakhand 2022"
        lines={["All promises."]}
        lede="Each entry quotes the manifesto as printed, and carries the RTI trail filed against it. Search by keyword, by promise ID, or filter by department."
      />

      <ModuleNav />

      <Section>
        {/* ---- Search and filters (§15) ---- */}
        <div className="grid gap-3 lg:grid-cols-12">
          <div className="relative lg:col-span-4">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Keyword or promise ID (UK-2022-P001)"
              aria-label="Search promises"
              className="pl-9"
              data-testid="promise-search"
            />
          </div>

          <div className="lg:col-span-2">
            <Select value={filters.department} onValueChange={(v) => set("department", v)}>
              <SelectTrigger aria-label="Filter by department">
                <SelectValue placeholder="Department" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All departments</SelectItem>
                {options.departments.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.value} ({item.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-2">
            <Select value={filters.category} onValueChange={(v) => set("category", v)}>
              <SelectTrigger aria-label="Filter by category">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All categories</SelectItem>
                {options.categories.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.value} ({item.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-2">
            <Select value={filters.rtiStatus} onValueChange={(v) => set("rtiStatus", v)}>
              <SelectTrigger aria-label="Filter by RTI status">
                <SelectValue placeholder="RTI status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Any RTI status</SelectItem>
                {options.rtiStatuses.map((item) => (
                  <SelectItem key={item.key} value={item.key}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-2">
            <Select value={filters.status} onValueChange={(v) => set("status", v)}>
              <SelectTrigger aria-label="Filter by promise status">
                <SelectValue placeholder="Promise status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Any status</SelectItem>
                {options.statuses.map((item) => (
                  <SelectItem key={item.key} value={item.key}>
                    {item.label} ({item.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <p className="text-meta text-foreground/60" data-testid="promise-count">
            {loading ? "Loading…" : `${data.total} promise${data.total === 1 ? "" : "s"}`}
            {filtered ? " matching these filters" : " published"}
          </p>
          <div className="flex items-center gap-3">
            <Select value={filters.sort} onValueChange={(v) => set("sort", v)}>
              <SelectTrigger className="w-44" aria-label="Sort promises">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="code">Promise ID</SelectItem>
                <SelectItem value="updated">Recently updated</SelectItem>
                <SelectItem value="status">Status</SelectItem>
                <SelectItem value="department">Department</SelectItem>
              </SelectContent>
            </Select>
            {filtered ? (
              <DynamicButton variant="ghost" size="sm" onClick={clear}>
                Clear filters
              </DynamicButton>
            ) : null}
          </div>
        </div>

        {/* ---- Listing (§6) ---- */}
        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">Loading…</p>
          ) : data.items.length === 0 ? (
            <EmptyState
              title={filtered ? "No promises match these filters" : "No promises published yet"}
              body={
                filtered
                  ? "Try a broader search, or clear the filters to see everything published so far."
                  : "Promises are entered from the published manifesto one at a time, each quoted with its page number and carrying the RTI trail filed against it."
              }
              action={
                filtered ? (
                  <DynamicButton variant="outline" onClick={clear}>
                    Clear filters
                  </DynamicButton>
                ) : null
              }
            />
          ) : (
            <>
              <StaggerGroup className="grid gap-4">
                {data.items.slice(0, shown).map((promise) => (
                  <StaggerItem key={promise.code}>
                    <article
                      className="rounded border border-border bg-card p-6"
                      data-testid={`promise-card-${promise.code}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <span className="rounded border border-border bg-muted/50 px-2 py-0.5 font-mono text-meta font-medium text-foreground/70">
                          {promise.code}
                        </span>
                        <PromiseStatusBadge status={promise.status} />
                      </div>

                      <h2 className="mt-3 font-heading text-lead font-semibold leading-snug tracking-tight">
                        {hi && promise.titleHi ? promise.titleHi : promise.title}
                      </h2>

                      {/* The manifesto's own words, marked as a quotation so it
                          cannot be read as this platform's description of it. */}
                      <blockquote className="mt-3 border-l-2 border-secondary/40 pl-4 text-body leading-relaxed text-foreground/75">
                        {promise.promiseText}
                      </blockquote>

                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        {promise.department ? <Pill>{promise.department}</Pill> : null}
                        {promise.category ? <Pill tone="muted">{promise.category}</Pill> : null}
                        {promise.manifestoPage ? (
                          <Pill tone="muted">Manifesto p. {promise.manifestoPage}</Pill>
                        ) : null}
                      </div>

                      <dl className="mt-5 grid gap-4 border-t border-border pt-4 sm:grid-cols-3">
                        <div>
                          <dt className="text-label font-bold uppercase text-muted-foreground">
                            RTI
                          </dt>
                          <dd className="mt-1">
                            <RtiStatusPill
                              status={promise.rti?.status}
                              label={promise.rti?.statusLabel}
                            />
                          </dd>
                        </div>
                        <div>
                          <dt className="text-label font-bold uppercase text-muted-foreground">
                            Evidence
                          </dt>
                          <dd className="mt-1 text-meta text-foreground/70">
                            {promise.hasEvidence
                              ? `${promise.documentCount} document(s), ${promise.evidenceCount} statement(s)`
                              : "None published yet"}
                          </dd>
                        </div>
                        <div className="sm:text-right">
                          <LinkButton to={promise.url} variant="outline" size="sm">
                            View complete record
                            <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
                          </LinkButton>
                        </div>
                      </dl>
                    </article>
                  </StaggerItem>
                ))}
              </StaggerGroup>

              {data.items.length > shown ? (
                <div className="mt-8 flex justify-center">
                  <DynamicButton variant="outline" onClick={() => setShown((n) => n + 24)}>
                    Show more ({data.items.length - shown} remaining)
                  </DynamicButton>
                </div>
              ) : null}
            </>
          )}
        </div>
      </Section>
    </div>
  );
}
