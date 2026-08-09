import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Reveal } from "@/components/motion/Reveal";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import LinkButton from "@/components/LinkButton";
import {
  Section,
  Disclaimer,
  HistoryList,
  Pill,
  SourceLink,
  EmptyState,
} from "@/components/platform/Primitives";
import CorrectionDialog from "@/components/platform/CorrectionDialog";
import { getArticle, getArticleHistory, getCorrections } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, ExternalLink, Scale, Target } from "lucide-react";

export default function ConstitutionArticle() {
  const { number } = useParams();
  const { t, locale } = useLocale();
  const [article, setArticle] = useState(null);
  const [history, setHistory] = useState([]);
  const [corrections, setCorrections] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    setStatus("loading");
    getArticle(number, locale)
      .then((data) => {
        setArticle(data);
        setStatus("ready");
      })
      .catch(() => setStatus("missing"));
    getArticleHistory(number).then(setHistory);
    getCorrections("constitution_article", String(number).toUpperCase()).then(setCorrections);
  }, [number, locale]);

  if (status === "loading") {
    return (
      <Section>
        <p className="text-body text-foreground/60">{t("common.loading")}</p>
      </Section>
    );
  }

  if (status === "missing") {
    return (
      <Section>
        <EmptyState
          title={`Article ${number} is not in the library yet`}
          body="The library is built article by article, each one explained and reviewed before it is published. You can read the original text on India Code in the meantime, or ask a researcher to prioritise this one."
          action={
            <div className="flex flex-wrap justify-center gap-3">
              <LinkButton to="/constitution" variant="outline">
                Browse the library
              </LinkButton>
              <LinkButton to="/forum?category=research" variant="ghost">
                Ask in the research forum
              </LinkButton>
            </div>
          }
        />
      </Section>
    );
  }

  return (
    <div data-testid={`article-page-${article.number}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-4xl">
          <Link
            to="/constitution"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.constitution")}
          </Link>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <span className="flex h-11 items-center justify-center rounded bg-secondary px-3.5 font-heading text-lead font-bold text-secondary-foreground">
              Article {article.number}
            </span>
            {article.part ? (
              <Pill tone="muted">
                Part {article.part} &middot; {article.partTitle}
              </Pill>
            ) : null}
          </div>

          <h1 className="mt-6 font-heading text-title-1 font-semibold leading-[1.05] tracking-tighter">
            {article.title}
          </h1>
          {article.titleHi && locale !== "hi" ? (
            <p className="mt-3 text-lead text-foreground/60" lang="hi">
              {article.titleHi}
            </p>
          ) : null}

          <div className="mt-8 flex flex-wrap gap-3">
            <CorrectionDialog
              entityType="constitution_article"
              entityId={article.number}
              fieldLabel={`Article ${article.number}`}
            />
            {article.tags?.map((tag) => (
              <Pill key={tag} tone="muted">
                {tag}
              </Pill>
            ))}
          </div>
        </div>
      </section>

      <section className="full-section px-6 md:px-12">
        <div className="mx-auto w-full max-w-4xl space-y-12">
          {/* The verbatim text comes first. The paraphrase must never be mistaken
              for the law, and ordering is half of how that is communicated. */}
          <Reveal>
            <div>
              <h2 className="flex items-center gap-2 font-heading text-title-3 font-semibold tracking-tight">
                {t("constitution.originalText")}
              </h2>
              {article.originalTextPending ? (
                <div className="mt-4 rounded border border-dashed border-border bg-muted/30 p-6">
                  <p className="text-body text-foreground/70">{t("constitution.textPending")}</p>
                  <a
                    href={article.originalSourceUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="mt-3 inline-flex items-center gap-1.5 text-body text-primary underline-offset-4 hover:underline"
                  >
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    Read Article {article.number} on India Code
                  </a>
                </div>
              ) : (
                <blockquote className="mt-4 border-l-4 border-secondary bg-muted/30 p-6">
                  <p className="whitespace-pre-line font-heading text-lead leading-relaxed">
                    {article.originalText}
                  </p>
                  <footer className="mt-4">
                    <SourceLink
                      citation={{
                        url: article.originalSourceUrl,
                        title: "Constitution of India, India Code",
                        isPrimary: true,
                      }}
                    />
                  </footer>
                </blockquote>
              )}
            </div>
          </Reveal>

          {/* Plain language, clearly labelled as a paraphrase. */}
          <Reveal>
            <div>
              <h2 className="font-heading text-title-3 font-semibold tracking-tight">
                {t("constitution.plainEnglish")}
              </h2>
              <p className="mt-2 text-meta text-foreground/60">
                {t("constitution.paraphraseNotice")}
              </p>
              <div className="mt-4 space-y-4">
                {article.plainEnglish
                  .split("\n\n")
                  .filter(Boolean)
                  .map((paragraph, index) => (
                    <p key={index} className="text-body leading-relaxed text-foreground/85">
                      {paragraph}
                    </p>
                  ))}
              </div>
            </div>
          </Reveal>

          {article.plainHindi ? (
            <Reveal>
              <div>
                <h2 className="font-heading text-title-3 font-semibold tracking-tight" lang="hi">
                  {t("constitution.plainHindi")}
                </h2>
                <div className="mt-4 space-y-4" lang="hi">
                  {article.plainHindi
                    .split("\n\n")
                    .filter(Boolean)
                    .map((paragraph, index) => (
                      <p key={index} className="text-body leading-relaxed text-foreground/85">
                        {paragraph}
                      </p>
                    ))}
                </div>
              </div>
            </Reveal>
          ) : null}

          {/* Why it matters here. The reason this article is in THIS library. */}
          {article.recallRelevance ? (
            <Reveal>
              <div className="rounded border border-primary/30 bg-primary/5 p-7">
                <h2 className="flex items-center gap-2 font-heading text-title-4 font-semibold tracking-tight text-primary">
                  <Target className="h-5 w-5" aria-hidden="true" />
                  {t("constitution.recallRelevance")}
                </h2>
                <p className="mt-3 text-body leading-relaxed text-foreground/85">
                  {article.recallRelevance}
                </p>
              </div>
            </Reveal>
          ) : null}

          {/* Case law, kept visually separate from the text of the article: what a
              court HELD is a different kind of statement from what the Constitution
              SAYS. */}
          {article.caseLaw?.length ? (
            <Reveal>
              <div>
                <h2 className="flex items-center gap-2 font-heading text-title-3 font-semibold tracking-tight">
                  <Scale className="h-5 w-5" aria-hidden="true" />
                  {t("constitution.caseLaw")}
                </h2>
                <ul className="mt-4 space-y-4">
                  {article.caseLaw.map((entry) => (
                    <li key={entry.case} className="rounded border border-border bg-card p-5">
                      <p className="font-heading text-lead font-semibold tracking-tight">
                        {entry.case}
                        {entry.year ? (
                          <span className="ml-2 font-normal text-foreground/60">({entry.year})</span>
                        ) : null}
                      </p>
                      {entry.citation ? (
                        <p className="mt-1 text-meta font-medium text-secondary">{entry.citation}</p>
                      ) : null}
                      <p className="mt-2 text-body text-foreground/80">{entry.held}</p>
                      {entry.url ? (
                        <SourceLink
                          citation={{ url: entry.url, title: "Read the judgment" }}
                          className="mt-3"
                        />
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ) : null}

          {article.related?.length ? (
            <Reveal>
              <div>
                <h2 className="font-heading text-title-4 font-semibold tracking-tight">
                  {t("constitution.related")}
                </h2>
                <div className="mt-4 flex flex-wrap gap-2">
                  {article.related.map((related) => (
                    <Link key={related} to={`/constitution/${related}`}>
                      <Pill tone="primary">Article {related}</Pill>
                    </Link>
                  ))}
                </div>
              </div>
            </Reveal>
          ) : null}

          {/* History and corrections: the Wikipedia-History and dispute pillars. */}
          <Reveal>
            <Tabs defaultValue="history" className="rounded border border-border bg-card p-6">
              <TabsList>
                <TabsTrigger value="history" data-testid="tab-history">
                  {t("common.history")} ({history.length})
                </TabsTrigger>
                <TabsTrigger value="corrections" data-testid="tab-corrections">
                  Corrections ({corrections?.total ?? 0})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="history" className="mt-5">
                <p className="mb-4 text-meta text-foreground/60">
                  Every edit to this page, when it happened and the source behind it. Contributor
                  names are not shown.
                </p>
                <HistoryList entries={history} />
              </TabsContent>

              <TabsContent value="corrections" className="mt-5">
                {corrections?.items?.length ? (
                  <ul className="space-y-3">
                    {corrections.items.map((item) => (
                      <li key={item.id} className="rounded border border-border p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <Pill tone={item.status === "accepted" ? "primary" : "muted"}>
                            {item.statusLabel}
                          </Pill>
                          <span className="text-meta text-muted-foreground">{item.filedOn}</span>
                        </div>
                        <p className="mt-2 text-body text-foreground/80">{item.summary}</p>
                        {item.resolutionNote ? (
                          <p className="mt-2 text-meta text-foreground/70">
                            <strong className="font-semibold">Reviewer: </strong>
                            {item.resolutionNote}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-body text-foreground/60">
                    No corrections have been filed about this page. If something here is wrong, say
                    so &mdash; it is how the library gets better.
                  </p>
                )}
              </TabsContent>
            </Tabs>
          </Reveal>

          <Disclaimer text={article.disclaimer} />
        </div>
      </section>
    </div>
  );
}
