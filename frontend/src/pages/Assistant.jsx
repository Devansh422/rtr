import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Input } from "@/components/ui/input";
import DynamicButton from "@/components/DynamicButton";
import { PageHero, Section, Pill } from "@/components/platform/Primitives";
import { askAssistant, getAssistantStatus, rateAnswer } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { ExternalLink, Send, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";

/*
 * AI Constitution Assistant.
 *
 * Sources are shown for every answer, and the engine is named ("generated from the
 * library" vs "these are the sources"). Both are deliberate: an answer whose
 * provenance is invisible cannot be checked, and a reader deserves to know whether a
 * model wrote the prose or whether they are looking at a ranked list.
 */
export default function Assistant() {
  const { t, locale } = useLocale();
  const [status, setStatus] = useState(null);
  const [question, setQuestion] = useState("");
  const [thread, setThread] = useState([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    getAssistantStatus().then(setStatus);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [thread]);

  const ask = async (text) => {
    const asked = (text ?? question).trim();
    if (asked.length < 8) return;
    setBusy(true);
    setQuestion("");
    try {
      const answer = await askAssistant(asked, locale);
      setThread((prev) => [...prev, answer]);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      setThread((prev) => [
        ...prev,
        {
          question: asked,
          answer:
            typeof detail === "string"
              ? detail
              : "Something went wrong reaching the assistant. Try again in a moment.",
          sources: [],
          links: [],
          engine: "error",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="assistant-page">
      <PageHero eyebrow="Ask" lines={["Ask about", "the Constitution."]} lede={t("assistant.lede")}>
        {status ? (
          <div className="flex flex-wrap gap-2">
            <Pill tone={status.engine === "gemini" ? "primary" : "muted"}>
              {status.engine === "gemini" ? "Generated answers" : "Source lookup only"}
            </Pill>
            <Pill tone="muted">{status.indexedSources} sources indexed</Pill>
          </div>
        ) : null}
      </PageHero>

      <Section>
        <div className="mx-auto w-full max-w-3xl">
          {status?.note ? (
            <p className="rounded border border-border bg-muted/40 p-4 text-meta leading-relaxed text-foreground/75">
              {status.note}
            </p>
          ) : null}

          {/* Example questions, from the API so they stay in step with what the
              library can actually answer. */}
          {thread.length === 0 && status?.examples ? (
            <div className="mt-8">
              <p className="text-label font-bold uppercase text-muted-foreground">Try asking</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {status.examples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => ask(example)}
                    className="rounded border border-border bg-card px-3 py-1.5 text-meta transition-colors hover:border-primary/40 hover:text-primary"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-8 space-y-8">
            {thread.map((entry, index) => (
              <div key={index} data-testid={`answer-${index}`}>
                <p className="font-heading text-lead font-semibold tracking-tight">
                  {entry.question}
                </p>

                <div className="mt-3 rounded border border-border bg-card p-6">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-secondary" aria-hidden="true" />
                    <span className="text-label font-bold uppercase text-muted-foreground">
                      {entry.refusal
                        ? "Not something I can answer"
                        : entry.engine === "gemini"
                          ? "Answer, grounded in the library"
                          : "From the library"}
                    </span>
                    {entry.cached ? <Pill tone="muted">cached</Pill> : null}
                    {entry.humanReviewed ? <Pill tone="primary">reviewed by staff</Pill> : null}
                  </div>

                  <div className="mt-3 space-y-3">
                    {entry.answer
                      .split("\n")
                      .filter(Boolean)
                      .map((line, lineIndex) => (
                        <p key={lineIndex} className="text-body leading-relaxed text-foreground/85">
                          {line}
                        </p>
                      ))}
                  </div>

                  {entry.sources?.length ? (
                    <div className="mt-5 border-t border-border pt-4">
                      <p className="text-label font-bold uppercase text-muted-foreground">
                        {t("common.sources")}
                      </p>
                      <ul className="mt-2 space-y-1.5">
                        {entry.sources.map((source) => (
                          <li key={source.url}>
                            <Link
                              to={source.url}
                              className="text-meta text-primary underline-offset-4 hover:underline"
                            >
                              {source.title}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {entry.links?.length ? (
                    <div className="mt-4 flex flex-wrap gap-3">
                      {entry.links.map((link) =>
                        link.url.startsWith("http") ? (
                          <a
                            key={link.url}
                            href={link.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="inline-flex items-center gap-1.5 text-meta text-primary underline-offset-4 hover:underline"
                          >
                            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                            {link.label}
                          </a>
                        ) : (
                          <Link
                            key={link.url}
                            to={link.url}
                            className="text-meta text-primary underline-offset-4 hover:underline"
                          >
                            {link.label}
                          </Link>
                        )
                      )}
                    </div>
                  ) : null}

                  {entry.disclaimer ? (
                    <p className="mt-5 border-t border-border pt-4 text-meta leading-relaxed text-foreground/60">
                      {entry.disclaimer}
                    </p>
                  ) : null}

                  {!entry.refusal && entry.engine !== "error" ? (
                    <div className="mt-4 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => rateAnswer(entry.question, true)}
                        className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
                      >
                        <ThumbsUp className="h-3.5 w-3.5" aria-hidden="true" />
                        {t("assistant.helpful")}
                      </button>
                      <button
                        type="button"
                        onClick={() => rateAnswer(entry.question, false)}
                        className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
                      >
                        <ThumbsDown className="h-3.5 w-3.5" aria-hidden="true" />
                        {t("assistant.notHelpful")}
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              ask();
            }}
            className="sticky bottom-6 mt-10 flex gap-2 rounded border border-border bg-card p-2 shadow-sm"
          >
            <Input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={t("assistant.placeholder")}
              maxLength={500}
              aria-label="Your question"
              className="border-0 focus-visible:ring-0"
              data-testid="assistant-input"
            />
            <DynamicButton type="submit" disabled={busy || question.trim().length < 8}>
              <Send className="h-4 w-4" aria-hidden="true" />
              {busy ? t("assistant.thinking") : t("assistant.ask")}
            </DynamicButton>
          </form>

          <p className="mt-4 text-meta leading-relaxed text-foreground/60">
            Do not put personal details, phone numbers or ID numbers in a question. They are stripped
            before the question goes anywhere, but the safest place for them is nowhere.
          </p>
        </div>
      </Section>
    </div>
  );
}
