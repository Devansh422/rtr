import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { StaggerGroup, StaggerItem, Reveal } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { PageHero, Section, SectionHeading, EmptyState, Pill, StatTile } from "@/components/platform/Primitives";
import { getReportServices, getReports, getScorecard, getStates } from "@/lib/platformApi";
import { fileReport } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { MessageSquarePlus } from "lucide-react";

const ALL = "__all__";

/*
 * Citizen Report Cards.
 *
 * The page leads with the scorecard rather than the individual reports, because the
 * aggregate is the finding and a single report is an anecdote. Scores below the
 * platform's sample-size floor are withheld by the API and the page says so, which is
 * the honest way to publish crowd-sourced data.
 */
export default function Reports() {
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [services, setServices] = useState([]);
  const [states, setStates] = useState([]);
  const [reports, setReports] = useState({ items: [], total: 0 });
  const [scorecard, setScorecard] = useState(null);
  const [stateFilter, setStateFilter] = useState(ALL);
  const [serviceFilter, setServiceFilter] = useState(ALL);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: "",
    body: "",
    service: "",
    state_code: "",
    locality: "",
    rating: "3",
    show_my_name: false,
  });

  useEffect(() => {
    getReportServices().then(setServices);
    getStates().then(setStates);
  }, []);

  useEffect(() => {
    getReports({
      state: stateFilter === ALL ? undefined : stateFilter,
      service: serviceFilter === ALL ? undefined : serviceFilter,
      limit: 48,
    }).then(setReports);
    if (stateFilter !== ALL) getScorecard({ state: stateFilter }).then(setScorecard);
    else setScorecard(null);
  }, [stateFilter, serviceFilter]);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await fileReport({
        ...form,
        rating: Number(form.rating),
        state_code: form.state_code,
      });
      toast.success(result.message, { duration: 12000 });
      setShowForm(false);
      setForm({ title: "", body: "", service: "", state_code: "", locality: "", rating: "3", show_my_name: false });
    } catch (error) {
      const detail = error?.response?.data?.detail;
      toast.error(
        detail?.flags?.[0]?.explanation ??
          (typeof detail === "string" ? detail : "Could not file that report.")
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="reports-page">
      <PageHero
        eyebrow="Citizen report cards"
        lines={["What services", "actually look like", "where you live."]}
        lede={t("reports.lede")}
      >
        {memberStatus === "in" ? (
          <DynamicButton size="lg" onClick={() => setShowForm((v) => !v)} data-testid="toggle-report-form">
            <MessageSquarePlus className="h-5 w-5" aria-hidden="true" />
            {t("reports.file")}
          </DynamicButton>
        ) : (
          <LinkButton to="/login" size="lg">
            Sign in to file a report
          </LinkButton>
        )}
      </PageHero>

      {showForm ? (
        <Section testId="report-form">
          <form onSubmit={submit} className="mx-auto max-w-2xl rounded border border-border bg-card p-7">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              {t("reports.file")}
            </h2>
            <p className="mt-2 text-meta text-foreground/60">
              Report about a SERVICE and a PLACE, not about a person. Do not include phone numbers,
              email addresses or ID numbers &mdash; the form will refuse them.
            </p>

            <div className="mt-6 space-y-4">
              <div>
                <Label htmlFor="report-title">What is the problem?</Label>
                <Input
                  id="report-title"
                  required
                  minLength={10}
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="e.g. Primary health centre has had no doctor since June"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="report-service">Which service?</Label>
                  <Select
                    value={form.service}
                    onValueChange={(v) => setForm((p) => ({ ...p, service: v }))}
                  >
                    <SelectTrigger id="report-service">
                      <SelectValue placeholder="Choose a service" />
                    </SelectTrigger>
                    <SelectContent>
                      {services.map((service) => (
                        <SelectItem key={service.key} value={service.key}>
                          {service.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="report-state">State</Label>
                  <Select
                    value={form.state_code}
                    onValueChange={(v) => setForm((p) => ({ ...p, state_code: v }))}
                  >
                    <SelectTrigger id="report-state">
                      <SelectValue placeholder="Choose a state" />
                    </SelectTrigger>
                    <SelectContent>
                      {states.map((state) => (
                        <SelectItem key={state.code} value={state.code}>
                          {state.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label htmlFor="report-locality">Locality (ward, village, block)</Label>
                <Input
                  id="report-locality"
                  value={form.locality}
                  onChange={(e) => setForm((p) => ({ ...p, locality: e.target.value }))}
                  placeholder="As specific as you can be without identifying yourself"
                />
              </div>

              <div>
                <Label htmlFor="report-body">What is happening, since when, and who it affects</Label>
                <Textarea
                  id="report-body"
                  required
                  minLength={60}
                  rows={6}
                  value={form.body}
                  onChange={(e) => setForm((p) => ({ ...p, body: e.target.value }))}
                  placeholder="Facts rather than adjectives. If you have filed a complaint, include its number and date."
                />
              </div>

              <div>
                <Label htmlFor="report-rating">
                  How well is this service working here? (1 = not at all, 5 = well)
                </Label>
                <Select value={form.rating} onValueChange={(v) => setForm((p) => ({ ...p, rating: v }))}>
                  <SelectTrigger id="report-rating">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <label htmlFor="report-name" className="flex cursor-pointer items-start gap-3">
                <Checkbox
                  id="report-name"
                  checked={form.show_my_name}
                  onCheckedChange={(v) => setForm((p) => ({ ...p, show_my_name: v === true }))}
                />
                <span className="text-meta text-foreground/80">
                  Publish my display name with this report. Off by default &mdash; you should not
                  have to make yourself findable to report on your own ward.
                </span>
              </label>

              <DynamicButton type="submit" disabled={busy} className="w-full">
                {busy ? "Sending..." : "Submit for review"}
              </DynamicButton>
            </div>
          </form>
        </Section>
      ) : null}

      {/* Scorecard first: the aggregate is the finding. */}
      <Section muted testId="report-scorecard">
        <SectionHeading
          eyebrow={t("reports.scorecard")}
          title="Choose a state to see its service scores"
          lede="Scores appear only where enough residents have rated a service. Below that threshold the report count is shown instead."
        />
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:w-2/3">
          <Select value={stateFilter} onValueChange={setStateFilter}>
            <SelectTrigger aria-label="Filter by state">
              <SelectValue placeholder="All states" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All states</SelectItem>
              {states.map((state) => (
                <SelectItem key={state.code} value={state.code}>
                  {state.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={serviceFilter} onValueChange={setServiceFilter}>
            <SelectTrigger aria-label="Filter by service">
              <SelectValue placeholder="All services" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All services</SelectItem>
              {services.map((service) => (
                <SelectItem key={service.key} value={service.key}>
                  {service.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {scorecard?.services?.length ? (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Reports published" value={scorecard.totalReports} />
              <StatTile
                label="Services reported on"
                value={scorecard.services.length}
                sub={`of ${services.length} tracked`}
              />
              <StatTile
                label="Resolved"
                value={scorecard.services.reduce((sum, s) => sum + s.resolvedCount, 0)}
                sub="Fixed after being reported"
                tone="primary"
              />
              <StatTile label="Minimum for a score" value={scorecard.minimumForScore} sub="ratings" />
            </div>
            <div className="mt-6 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {scorecard.services.map((service) => (
                <div key={service.service} className="rounded border border-border bg-card p-5">
                  <p className="font-heading text-body font-semibold tracking-tight">
                    {service.label}
                  </p>
                  <p className="mt-2 font-heading text-title-3 font-semibold tracking-tight">
                    {service.averageRating != null ? `${service.averageRating}/5` : "—"}
                  </p>
                  <p className="mt-1 text-meta text-foreground/60">
                    {service.reportCount} report{service.reportCount === 1 ? "" : "s"}
                    {service.resolvedCount ? `, ${service.resolvedCount} resolved` : ""}
                  </p>
                  {service.scoreWithheld ? (
                    <p className="mt-2 text-meta text-foreground/50">
                      Too few ratings to publish a score.
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
            <p className="mt-6 max-w-3xl text-meta text-foreground/60">{scorecard.note}</p>
          </>
        ) : (
          <p className="mt-8 text-body text-foreground/60">
            {stateFilter === ALL
              ? "Pick a state above to see its scorecard."
              : "No published reports for this state yet."}
          </p>
        )}
      </Section>

      <Section testId="report-list">
        <SectionHeading title="Published reports" lede={`${reports.total} total`} />
        <div className="mt-8">
          {reports.items.length === 0 ? (
            <EmptyState
              title="No published reports for this filter"
              body="Every report is read by a moderator before publication, so there is a lag between filing and appearing. Nothing auto-publishes."
            />
          ) : (
            <StaggerGroup className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {reports.items.map((report) => (
                <StaggerItem key={report.id}>
                  <Link
                    to={report.url}
                    className="group flex h-full flex-col rounded border border-border bg-card p-5 hover:border-primary/40"
                  >
                    <div className="flex flex-wrap gap-2">
                      <Pill tone="muted">{report.serviceLabel}</Pill>
                      {report.status === "resolved" ? <Pill tone="primary">Resolved</Pill> : null}
                    </div>
                    <p className="mt-3 font-heading text-body font-semibold leading-snug tracking-tight group-hover:text-primary">
                      {report.title}
                    </p>
                    <p className="mt-2 flex-1 text-meta text-foreground/70">
                      {report.body.slice(0, 140)}
                      {report.body.length > 140 ? "..." : ""}
                    </p>
                    <p className="mt-3 text-meta text-foreground/50">
                      {[report.locality, report.state].filter(Boolean).join(", ")}
                      {report.confirmations ? ` · ${report.confirmations} others confirm` : ""}
                    </p>
                  </Link>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>

      <Section muted>
        <Reveal>
          <div className="rounded border border-border bg-card p-8">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              Why we record the department&rsquo;s reply too
            </h2>
            <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/70">
              A system that only records complaints looks like a campaign. One that publishes
              &ldquo;the municipality repaired it in eleven days&rdquo; next to the complaint is doing
              accountability. Where an office responds, or fixes the problem, that goes on the record
              with the same prominence as the original report.
            </p>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
