import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem, Reveal } from "@/components/motion/Reveal";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import LinkButton from "@/components/LinkButton";
import { PageHero, Section, SectionHeading, EmptyState, Pill } from "@/components/platform/Primitives";
import { getPetitions } from "@/lib/platformApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { ShieldCheck } from "lucide-react";

export default function Petitions() {
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [data, setData] = useState({ items: [], total: 0 });
  const [sort, setSort] = useState("trending");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getPetitions({ sort, limit: 48 })
      .then(setData)
      .finally(() => setLoading(false));
  }, [sort]);

  return (
    <div data-testid="petitions-page">
      <PageHero eyebrow="Petitions" lines={["Signatures that", "survive scrutiny."]} lede={t("petitions.lede")}>
        <div className="flex flex-wrap gap-3">
          <LinkButton to="/petition" size="lg">
            {t("commonCause.sign")}
          </LinkButton>
          {memberStatus === "in" ? (
            <LinkButton to="/dashboard" variant="outline" size="lg">
              {t("petitions.start")}
            </LinkButton>
          ) : (
            <LinkButton to="/login" variant="outline" size="lg">
              Sign in to start a petition
            </LinkButton>
          )}
          <LinkButton to="/states" variant="ghost" size="lg">
            {t("nav.states")}
          </LinkButton>
        </div>
      </PageHero>

      <Section>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <SectionHeading title="Open petitions" lede={`${data.total} published`} />
          <Tabs value={sort} onValueChange={setSort}>
            <TabsList>
              <TabsTrigger value="trending">Trending</TabsTrigger>
              <TabsTrigger value="signatures">Most signed</TabsTrigger>
              <TabsTrigger value="newest">Newest</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="mt-8">
          {loading ? (
            <p className="text-body text-foreground/60">{t("common.loading")}</p>
          ) : data.items.length === 0 ? (
            <EmptyState
              title="No petitions are open yet"
              body="Petitions started by members are checked against the content policy before they open for signatures. Once the first one clears review it appears here."
              action={
                memberStatus === "in" ? null : (
                  <LinkButton to="/login" variant="outline">
                    Sign in to start one
                  </LinkButton>
                )
              }
            />
          ) : (
            <StaggerGroup className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {data.items.map((petition) => (
                <StaggerItem key={petition.id}>
                  <Link
                    to={petition.url}
                    className="group flex h-full flex-col rounded border border-border bg-card p-6 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40"
                    data-testid={`petition-${petition.slug}`}
                  >
                    <div className="flex flex-wrap gap-2">
                      {petition.isOfficial ? <Pill tone="secondary">Official</Pill> : null}
                      {petition.state ? <Pill tone="muted">{petition.state}</Pill> : null}
                      <Pill tone="muted">{petition.statusLabel}</Pill>
                    </div>

                    <h3 className="mt-4 font-heading text-lead font-semibold leading-snug tracking-tight group-hover:text-primary">
                      {petition.title}
                    </h3>
                    <p className="mt-2 flex-1 text-body text-foreground/70">{petition.summary}</p>

                    <p className="mt-4 text-meta text-foreground/60">
                      To: <span className="font-medium text-foreground/80">{petition.addressedTo}</span>
                    </p>

                    <div className="mt-4">
                      <div className="flex items-baseline justify-between">
                        <span className="font-heading text-title-4 font-semibold tracking-tight">
                          {petition.signatureCount.toLocaleString("en-IN")}
                        </span>
                        <span className="text-meta text-foreground/60">
                          {t("petitions.target")} {petition.targetSignatures.toLocaleString("en-IN")}
                        </span>
                      </div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded bg-muted" aria-hidden="true">
                        <div
                          className="h-full rounded bg-primary transition-all"
                          style={{ width: `${petition.progressPercent}%` }}
                        />
                      </div>
                      {petition.nextMilestone ? (
                        <p className="mt-1.5 text-meta text-foreground/50">
                          {(petition.nextMilestone - petition.signatureCount).toLocaleString("en-IN")}{" "}
                          more to reach {petition.nextMilestone.toLocaleString("en-IN")}
                        </p>
                      ) : null}
                    </div>
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
            <h2 className="flex items-center gap-2 font-heading text-title-3 font-semibold tracking-tight">
              <ShieldCheck className="h-6 w-6 text-secondary" aria-hidden="true" />
              Why signing requires an account
            </h2>
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              <p className="text-body leading-relaxed text-foreground/70">
                A petition with fifty thousand signatures that anyone can inflate with a script is
                worth less than one with five hundred that cannot &mdash; because the first can be
                dismissed in a sentence by the office it is addressed to. So every signature is tied
                to a verified member account, and uniqueness is enforced by the database rather than
                by a check the code might skip.
              </p>
              <p className="text-body leading-relaxed text-foreground/70">
                That costs us signups, and we accept it. Your name is <strong>not</strong> published
                unless you choose to be listed &mdash; the count includes everyone, the public list
                includes only those who opted in. You can withdraw a signature at any time, and
                withdrawing really deletes it.
              </p>
            </div>
          </div>
        </Reveal>
      </Section>
    </div>
  );
}
