import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  Eye,
  Fingerprint,
  Loader2,
  Mail,
  MessageSquare,
  RefreshCw,
  Table2,
  Users,
} from "lucide-react";
import { gsap, prefersReducedMotion } from "@/lib/motion";
import { listSubmissions, getPageviewAnalytics } from "@/lib/adminApi";
import { formatCount } from "@/lib/content";
import DynamicButton from "@/components/DynamicButton";

/*
 * Admin analytics, computed from real submission records.
 *
 * Every figure here derives from the `created_at` / `state` / `profession` fields
 * on actual documents returned by /api/admin/submissions/*. There is no synthetic
 * data -- if a series is empty it renders an empty state rather than filler, so
 * the numbers can be trusted.
 *
 * Palette note: the two categorical series colours and the sequential bar ramp
 * below were validated with the data-viz palette checker (lightness band, chroma
 * floor, CVD separation across protan/deutan/tritan, normal-vision floor, and
 * contrast against the real card surface) in both light and dark mode. Do not
 * swap in raw brand tokens: the site's saffron (#ff9933) fails the lightness band
 * and sits at 2.13:1 on white, below the 3:1 floor for a data mark.
 */

// Categorical slots, validated as a pair in each mode.
const SERIES = {
  light: { supporters: "#2a5ad6", volunteers: "#cf7010" },
  dark: { supporters: "#6788e9", volunteers: "#c9781d" },
};

// Single-hue sequential ramp for the magnitude bars, light -> dark. Validated
// --ordinal: monotone lightness, >=0.06 adjacent step, light end clears 2:1.
const RAMP = {
  light: ["#8fadea", "#6b91e0", "#4674d9", "#2a5ad6", "#1e429c"],
  dark: ["#c2d3f8", "#9db4f0", "#7793e9", "#5872d4", "#3f52a8"],
};

const RANGES = [
  { key: 30, label: "30 days" },
  { key: 90, label: "90 days" },
  { key: 365, label: "12 months" },
];

/** Tracks the theme via the class next-themes stamps on <html>. */
function useIsDark() {
  const [dark, setDark] = useState(
    () => typeof document !== "undefined" && document.documentElement.classList.contains("dark")
  );

  useEffect(() => {
    const el = document.documentElement;
    const observer = new MutationObserver(() => setDark(el.classList.contains("dark")));
    observer.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return dark;
}

/** Buckets records by day or month, pre-seeding gaps so the line has no holes. */
function buildTimeSeries(datasets, days) {
  const now = new Date();
  const start = new Date(now);
  start.setDate(start.getDate() - days);

  // Past ~120 days a daily axis is unreadable, so switch to monthly buckets.
  const monthly = days > 120;
  const keyOf = (d) =>
    monthly
      ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
      : d.toISOString().slice(0, 10);

  // Seed every bucket at zero so a quiet day plots as 0 instead of vanishing.
  const buckets = new Map();
  if (monthly) {
    const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
    while (cursor <= now) {
      buckets.set(keyOf(cursor), { supporters: 0, volunteers: 0 });
      cursor.setMonth(cursor.getMonth() + 1);
    }
  } else {
    const cursor = new Date(start);
    while (cursor <= now) {
      buckets.set(keyOf(cursor), { supporters: 0, volunteers: 0 });
      cursor.setDate(cursor.getDate() + 1);
    }
  }

  for (const [seriesKey, rows] of Object.entries(datasets)) {
    for (const row of rows) {
      if (!row?.created_at) continue;
      const d = new Date(row.created_at);
      if (Number.isNaN(d.getTime()) || d < start) continue;
      const bucket = buckets.get(keyOf(d));
      if (bucket) bucket[seriesKey] += 1;
    }
  }

  return Array.from(buckets.entries()).map(([key, counts]) => {
    const d = monthly ? new Date(`${key}-01T00:00:00`) : new Date(`${key}T00:00:00`);
    return {
      key,
      label: monthly
        ? d.toLocaleDateString("en-IN", { month: "short", year: "2-digit" })
        : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
      ...counts,
    };
  });
}

/** Counts occurrences of a field, returning the top N descending. */
function topBy(rows, field, limit = 6) {
  const counts = new Map();
  for (const row of rows) {
    const raw = row?.[field];
    if (!raw || typeof raw !== "string") continue;
    const key = raw.trim();
    if (!key) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}

/** Picks a ramp step by magnitude so darker always means larger. */
function rampStep(ramp, value, max) {
  if (!max) return ramp[ramp.length - 1];
  const idx = Math.round((value / max) * (ramp.length - 1));
  return ramp[Math.max(0, Math.min(ramp.length - 1, idx))];
}

function StatTile({ icon: Icon, label, value, subtext }) {
  const valueRef = useRef(null);

  // Count up to the real figure. GSAP animates a proxy number rather than
  // textContent directly, so the printed value keeps its thousands separators.
  useEffect(() => {
    const el = valueRef.current;
    if (!el) return;

    if (prefersReducedMotion() || value === 0) {
      el.textContent = formatCount(value);
      return;
    }

    const proxy = { n: 0 };
    const tween = gsap.to(proxy, {
      n: value,
      duration: 0.9,
      ease: "power2.out",
      onUpdate: () => {
        el.textContent = formatCount(Math.round(proxy.n));
      },
    });

    return () => tween.kill();
  }, [value]);

  return (
    <div className="rounded border border-border bg-card p-5">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-4 w-4" aria-hidden="true" />
        <p className="text-label font-semibold uppercase">{label}</p>
      </div>
      {/* Proportional figures: tabular-nums reads loose at display size. */}
      <p ref={valueRef} className="mt-3 font-heading text-title-2 font-extrabold">
        0
      </p>
      {subtext && <p className="mt-1 text-meta text-muted-foreground">{subtext}</p>}
    </div>
  );
}

function ChartCard({ title, subtitle, children, isEmpty, emptyNote }) {
  return (
    <div className="rounded border border-border bg-card p-6">
      <h3 className="font-heading text-lead font-bold">{title}</h3>
      {subtitle && <p className="mt-1 text-meta text-muted-foreground">{subtitle}</p>}
      <div className="mt-6">
        {isEmpty ? (
          <p className="py-16 text-center text-body text-muted-foreground">{emptyNote}</p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/** Recharts tooltip restyled to the design system: hairline border, 2px radius. */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-border bg-popover px-3 py-2 text-meta">
      <p className="font-semibold text-popover-foreground">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey ?? entry.name} className="mt-1 flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 shrink-0 rounded"
            style={{ background: entry.color || entry.payload?.fill }}
            aria-hidden="true"
          />
          <span className="text-muted-foreground">{entry.name}</span>
          <span className="ml-auto font-semibold tabular-nums text-popover-foreground">
            {formatCount(entry.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

export default function Analytics() {
  const isDark = useIsDark();
  const series = isDark ? SERIES.dark : SERIES.light;
  const ramp = isDark ? RAMP.dark : RAMP.light;

  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [days, setDays] = useState(30);
  const [showTable, setShowTable] = useState(false);

  const [pvData, setPvData] = useState(null);
  const [pvStatus, setPvStatus] = useState("loading"); // loading | ready | error

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const [supporters, volunteers, contacts, newsletter] = await Promise.all([
        listSubmissions("supporters"),
        listSubmissions("volunteers"),
        listSubmissions("contacts"),
        listSubmissions("newsletter"),
      ]);
      setData({ supporters, volunteers, contacts, newsletter });
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  // Pageviews are pre-aggregated server-side per range, unlike the submission
  // records above (fetched once, bucketed client-side) -- so this refetches
  // whenever the range filter changes rather than only on mount.
  const loadPageviews = useCallback(async (range) => {
    setPvStatus("loading");
    try {
      const res = await getPageviewAnalytics(range);
      setPvData(res);
      setPvStatus("ready");
    } catch {
      setPvStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadPageviews(days);
  }, [days, loadPageviews]);

  const refreshAll = () => {
    load();
    loadPageviews(days);
  };

  const timeSeries = useMemo(
    () =>
      data
        ? buildTimeSeries({ supporters: data.supporters, volunteers: data.volunteers }, days)
        : [],
    [data, days]
  );

  const topStates = useMemo(() => (data ? topBy(data.supporters, "state") : []), [data]);
  const topProfessions = useMemo(() => (data ? topBy(data.volunteers, "profession") : []), [data]);

  const inRange = useMemo(
    () => timeSeries.reduce((sum, d) => sum + d.supporters + d.volunteers, 0),
    [timeSeries]
  );

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center py-24" data-testid="analytics-loading">
        <Loader2 className="h-6 w-6 animate-spin text-secondary" aria-label="Loading analytics" />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div data-testid="analytics-error" className="rounded border border-border bg-card p-10">
        <div className="flex items-center gap-3 text-destructive">
          <AlertCircle className="h-5 w-5" aria-hidden="true" />
          <p className="font-heading font-bold">Couldn't load analytics</p>
        </div>
        <p className="mt-2 text-body text-muted-foreground">
          The submissions API didn't respond. Your session may have expired.
        </p>
        <DynamicButton variant="outline" size="sm" className="mt-6" onClick={load}>
          <RefreshCw className="h-4 w-4" /> Retry
        </DynamicButton>
      </div>
    );
  }

  const axisTick = { fill: "hsl(var(--muted-foreground))", fontSize: 11 };
  const gridStroke = "hsl(var(--border))";
  const maxState = topStates.length ? topStates[0].value : 0;
  const maxProfession = topProfessions.length ? topProfessions[0].value : 0;
  const topPages = pvData?.topPages || [];
  const topFlows = pvData?.topFlows || [];
  const maxPage = topPages.length ? topPages[0].views : 0;

  return (
    <div data-testid="analytics-section">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-heading text-title-3 font-extrabold">Analytics</h2>
          <p className="mt-1 text-body text-muted-foreground">
            Computed live from supporter, volunteer, message and newsletter records.
          </p>
        </div>
        <DynamicButton
          variant="outline"
          size="sm"
          onClick={refreshAll}
          data-testid="analytics-refresh"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </DynamicButton>
      </div>

      {/* KPI row */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <StatTile
          icon={Users}
          label="Supporters"
          value={data.supporters.length}
          subtext="Joined the movement"
        />
        <StatTile
          icon={BarChart3}
          label="Volunteers"
          value={data.volunteers.length}
          subtext="Signed up to help"
        />
        <StatTile
          icon={MessageSquare}
          label="Messages"
          value={data.contacts.length}
          subtext="Via the contact form"
        />
        <StatTile
          icon={Mail}
          label="Newsletter"
          value={data.newsletter.length}
          subtext="Email subscribers"
        />
        <StatTile
          icon={Eye}
          label="Page views"
          value={pvData?.total ?? 0}
          subtext={`Last ${days === 365 ? "12 months" : `${days} days`}`}
        />
        <StatTile
          icon={Fingerprint}
          label="Sessions"
          value={pvData?.uniqueSessions ?? 0}
          subtext="Unique visits"
        />
      </div>

      {/* Filters in one row above the charts */}
      <div className="mt-10 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-label font-semibold uppercase text-muted-foreground">Range</span>
        {RANGES.map((r) => (
          <button
            key={r.key}
            onClick={() => setDays(r.key)}
            data-testid={`analytics-range-${r.key}`}
            aria-pressed={days === r.key}
            className={`rounded px-3 py-1.5 text-meta font-semibold transition-colors ${
              days === r.key
                ? "bg-foreground text-background"
                : "border border-border bg-card text-foreground/70 hover:bg-muted"
            }`}
          >
            {r.label}
          </button>
        ))}
        <button
          onClick={() => setShowTable((v) => !v)}
          aria-pressed={showTable}
          data-testid="analytics-table-toggle"
          className="ml-auto inline-flex items-center gap-1.5 rounded border border-border bg-card px-3 py-1.5 text-meta font-semibold text-foreground/70 transition-colors hover:bg-muted"
        >
          <Table2 className="h-3.5 w-3.5" /> {showTable ? "Hide" : "Show"} data table
        </button>
      </div>

      {/* Trend over time -- two series, so a legend is mandatory */}
      <div className="mt-6">
        <ChartCard
          title="Signups over time"
          subtitle={`${formatCount(inRange)} in the last ${
            days === 365 ? "12 months" : `${days} days`
          }`}
          isEmpty={inRange === 0}
          emptyNote="No signups recorded in this range yet."
        >
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={timeSeries} margin={{ top: 4, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid stroke={gridStroke} vertical={false} />
              <XAxis
                dataKey="label"
                tick={axisTick}
                tickLine={false}
                axisLine={{ stroke: gridStroke }}
                minTickGap={24}
              />
              <YAxis
                tick={axisTick}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
                width={44}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend
                iconType="plainline"
                wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                formatter={(value) => <span className="text-muted-foreground">{value}</span>}
              />
              <Line
                type="monotone"
                dataKey="supporters"
                name="Supporters"
                stroke={series.supporters}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "hsl(var(--card))" }}
              />
              <Line
                type="monotone"
                dataKey="volunteers"
                name="Volunteers"
                stroke={series.volunteers}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "hsl(var(--card))" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Site traffic -- top pages (magnitude, one hue) + page flow (ranked list, not a chart) */}
      <div className="mt-10">
        <h3 className="font-heading text-lead font-bold">Site traffic</h3>
        <p className="mt-1 text-meta text-muted-foreground">
          From anonymous page-visit beacons, not tied to any individual.
        </p>
      </div>
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="Top pages"
          subtitle="Most-viewed paths"
          isEmpty={pvStatus !== "loading" && topPages.length === 0}
          emptyNote={
            pvStatus === "error"
              ? "Couldn't load page views."
              : "No page views recorded in this range yet."
          }
        >
          {pvStatus === "loading" ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-secondary" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(200, topPages.length * 40)}>
              <BarChart
                data={topPages}
                layout="vertical"
                margin={{ top: 0, right: 36, bottom: 0, left: 8 }}
                barCategoryGap="28%"
              >
                <CartesianGrid stroke={gridStroke} horizontal={false} />
                <XAxis type="number" allowDecimals={false} hide />
                <YAxis
                  type="category"
                  dataKey="path"
                  tick={axisTick}
                  tickLine={false}
                  axisLine={false}
                  width={128}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "hsl(var(--muted))" }} />
                <Bar
                  dataKey="views"
                  name="Views"
                  maxBarSize={24}
                  radius={[0, 2, 2, 0]}
                  label={{
                    position: "right",
                    fill: "hsl(var(--foreground))",
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  {topPages.map((d) => (
                    <Cell key={d.path} fill={rampStep(ramp, d.views, maxPage)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Page flow"
          subtitle="Where visitors go next"
          isEmpty={pvStatus !== "loading" && topFlows.length === 0}
          emptyNote={
            pvStatus === "error"
              ? "Couldn't load page flow."
              : "No page-to-page navigation recorded in this range yet."
          }
        >
          {pvStatus === "loading" ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-secondary" />
            </div>
          ) : (
            <ul className="max-h-[300px] space-y-1 overflow-y-auto" data-testid="page-flow-list">
              {topFlows.map((f, i) => (
                <li
                  key={`${f.from}->${f.to}-${i}`}
                  className="flex items-center gap-2 rounded px-2 py-2 text-meta odd:bg-muted/30"
                >
                  <span className="min-w-0 flex-1 truncate text-right text-foreground/80">
                    {f.from}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 truncate text-foreground/80">{f.to}</span>
                  <span className="shrink-0 rounded bg-muted px-2 py-0.5 text-micro font-bold tabular-nums text-foreground">
                    {formatCount(f.count)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </ChartCard>
      </div>

      {/* Magnitude breakdowns: one hue, darker = larger, so no legend is needed */}
      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="Where supporters are"
          subtitle="Top states by supporter count"
          isEmpty={topStates.length === 0}
          emptyNote="No state recorded on supporter records yet."
        >
          <ResponsiveContainer width="100%" height={Math.max(200, topStates.length * 44)}>
            <BarChart
              data={topStates}
              layout="vertical"
              margin={{ top: 0, right: 36, bottom: 0, left: 8 }}
              barCategoryGap="28%"
            >
              <CartesianGrid stroke={gridStroke} horizontal={false} />
              <XAxis type="number" allowDecimals={false} hide />
              <YAxis
                type="category"
                dataKey="name"
                tick={axisTick}
                tickLine={false}
                axisLine={false}
                width={104}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "hsl(var(--muted))" }} />
              <Bar
                dataKey="value"
                name="Supporters"
                maxBarSize={24}
                radius={[0, 2, 2, 0]}
                label={{
                  position: "right",
                  fill: "hsl(var(--foreground))",
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                {topStates.map((d) => (
                  <Cell key={d.name} fill={rampStep(ramp, d.value, maxState)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/*
         * Charts the `profession` field, which is what the volunteer form
         * currently collects. When the nine volunteer skill areas from the
         * campaign brief are added as their own field, add a second card for
         * them rather than relabelling this one.
         */}
        <ChartCard
          title="Volunteer professions"
          subtitle="Top professions by volunteer count"
          isEmpty={topProfessions.length === 0}
          emptyNote="No volunteer has recorded a profession yet."
        >
          <ResponsiveContainer width="100%" height={Math.max(200, topProfessions.length * 44)}>
            <BarChart
              data={topProfessions}
              layout="vertical"
              margin={{ top: 0, right: 36, bottom: 0, left: 8 }}
              barCategoryGap="28%"
            >
              <CartesianGrid stroke={gridStroke} horizontal={false} />
              <XAxis type="number" allowDecimals={false} hide />
              <YAxis
                type="category"
                dataKey="name"
                tick={axisTick}
                tickLine={false}
                axisLine={false}
                width={128}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "hsl(var(--muted))" }} />
              <Bar
                dataKey="value"
                name="Volunteers"
                maxBarSize={24}
                radius={[0, 2, 2, 0]}
                label={{
                  position: "right",
                  fill: "hsl(var(--foreground))",
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                {topProfessions.map((d) => (
                  <Cell key={d.name} fill={rampStep(ramp, d.value, maxProfession)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Table view -- the non-visual path to the same numbers. */}
      {showTable && (
        <div
          className="mt-6 overflow-x-auto rounded border border-border bg-card"
          data-testid="analytics-table"
        >
          <table className="w-full text-left text-body">
            <caption className="px-4 pt-4 text-left text-meta text-muted-foreground">
              Signups per period for the selected range.
            </caption>
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-label font-bold uppercase text-muted-foreground">
                  Period
                </th>
                <th className="px-4 py-3 text-right text-label font-bold uppercase text-muted-foreground">
                  Supporters
                </th>
                <th className="px-4 py-3 text-right text-label font-bold uppercase text-muted-foreground">
                  Volunteers
                </th>
              </tr>
            </thead>
            <tbody>
              {timeSeries.map((row) => (
                <tr key={row.key} className="border-b border-border last:border-0">
                  <td className="px-4 py-2">{row.label}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{row.supporters}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{row.volunteers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
