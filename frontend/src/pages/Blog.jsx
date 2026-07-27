import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useLenis } from "lenis/react";
import { Reveal, MaskedLines, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import DynamicButton from "@/components/DynamicButton";
import Eyebrow from "@/components/Eyebrow";
import { getBlogs } from "@/lib/api";
import { formatDate } from "@/lib/content";
import { cn } from "@/lib/utils";
import { Search, Clock, ArrowRight } from "lucide-react";

// A 3-column grid of two rows fits one viewport at these card sizes, so the
// collapsed grid shows six cards and everything beyond that hides behind the
// "View all" toggle.
const COLLAPSED_COUNT = 6;

export default function Blog() {
  const [blogs, setBlogs] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [expanded, setExpanded] = useState(false);
  const gridRef = useRef(null);
  const lenis = useLenis();

  useEffect(() => {
    getBlogs()
      .then(setBlogs)
      .catch(() => {});
  }, []);

  // Any change to the search or the category drops back to the collapsed grid,
  // otherwise a narrowed result set would inherit a stale "expanded" view.
  useEffect(() => {
    setExpanded(false);
  }, [query, category]);

  const categories = useMemo(
    () => ["All", ...Array.from(new Set(blogs.map((b) => b.category)))],
    [blogs]
  );

  const filtered = blogs.filter((b) => {
    const matchesCat = category === "All" || b.category === category;
    const q = query.toLowerCase();
    const matchesQuery =
      !q || b.title.toLowerCase().includes(q) || b.excerpt.toLowerCase().includes(q);
    return matchesCat && matchesQuery;
  });

  const visible = expanded ? filtered : filtered.slice(0, COLLAPSED_COUNT);
  const hasMore = filtered.length > COLLAPSED_COUNT;

  const toggleExpanded = () => {
    if (expanded) {
      setExpanded(false);
      // Collapsing removes everything below the fold, so bring the grid back
      // into view instead of leaving the reader stranded down the page. Route
      // it through Lenis so it uses the page's smooth scrolling.
      if (lenis) lenis.scrollTo(gridRef.current, { offset: -80 });
      else gridRef.current?.scrollIntoView({ behavior: "smooth" });
    } else {
      setExpanded(true);
    }
  };

  return (
    <div data-testid="blog-page" className="">
      <section className="full-section-hero mx-auto w-full max-w-7xl px-6 md:px-12">
        <Eyebrow>Blog & News</Eyebrow>
        <h1 className="mt-6 font-heading text-title-1 font-semibold">
          <MaskedLines lines={["Learn. Share.", "Stay informed."]} />
        </h1>

        <div className="mt-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              data-testid="blog-search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search articles…"
              className="h-12 w-full rounded border border-input bg-card pl-11 pr-5 text-body outline-none focus:ring-2 focus:ring-secondary"
            />
          </div>
          <div className="flex flex-wrap gap-2" data-testid="blog-categories">
            {categories.map((c) => (
              <button
                key={c}
                data-testid={`category-${c.toLowerCase()}`}
                onClick={() => setCategory(c)}
                className={`rounded px-4 py-2 text-body font-semibold transition-colors duration-200 ${
                  category === c
                    ? "bg-foreground text-background"
                    : "border border-border bg-card text-foreground/70 hover:bg-muted"
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/*
       * `full-section` only applies while collapsed. Its min-height keeps the
       * two-row grid filling the viewport, but its vertical centring would look
       * wrong once an expanded grid grows several screens tall -- so the
       * expanded state falls back to plain vertical padding.
       */}
      <section
        ref={gridRef}
        className={cn(
          "mx-auto w-full max-w-7xl px-6 md:px-12",
          expanded ? "py-24" : "full-section"
        )}
      >
        <StaggerGroup className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {visible.map((b) => (
            <StaggerItem key={b.id}>
              <Link
                to={`/blog/${b.id}`}
                className="group flex h-full flex-col overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-2"
                data-testid={`blog-card-${b.id}`}
              >
                <div className="h-48 overflow-hidden">
                  <img
                    src={b.image}
                    alt=""
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
                <div className="flex flex-1 flex-col p-6">
                  <div className="flex items-center gap-3 text-label font-bold uppercase">
                    <span className="rounded bg-secondary px-3 py-1 text-secondary-foreground">
                      {b.category}
                    </span>
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="h-3 w-3" /> {b.readTime}
                    </span>
                  </div>
                  <h3 className="mt-4 font-heading text-title-4 font-bold leading-snug">
                    {b.title}
                  </h3>
                  <p className="mt-2 flex-1 text-body text-foreground/70">{b.excerpt}</p>
                  <div className="mt-5 flex items-center justify-between text-meta text-muted-foreground">
                    <span>{b.author}</span>
                    <span>{formatDate(b.date)}</span>
                  </div>
                  <span className="mt-4 inline-flex items-center gap-1.5 text-label font-bold uppercase text-foreground">
                    Read article <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </Link>
            </StaggerItem>
          ))}
        </StaggerGroup>

        {/* The count tracks the filtered set, never the unfiltered total. */}
        {hasMore && (
          <div className="mt-12 flex justify-center">
            <DynamicButton
              data-testid="view-all-toggle"
              variant="outline"
              size="default"
              onClick={toggleExpanded}
              aria-expanded={expanded}
            >
              {expanded ? "Show less" : `View all ${filtered.length} articles`}
            </DynamicButton>
          </div>
        )}

        {filtered.length === 0 && (
          <Reveal>
            <p className="py-16 text-center text-muted-foreground">
              No articles found. Try a different search.
            </p>
          </Reveal>
        )}
      </section>
    </div>
  );
}
