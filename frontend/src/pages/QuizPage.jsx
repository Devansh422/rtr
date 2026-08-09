import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { getQuiz, submitQuiz } from "@/lib/memberApi";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, Award, Check, X } from "lucide-react";

/*
 * The quiz.
 *
 * Answers are never sent to the browser: the questions endpoint strips them, and
 * grading happens server-side. The explanation for each question arrives only inside
 * a graded result, which is also what makes the quiz teach rather than merely test.
 */
export default function QuizPage() {
  const { slug } = useParams();
  const { t } = useLocale();
  const [quiz, setQuiz] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getQuiz(slug)
      .then((data) => {
        setQuiz(data);
        setState("ready");
      })
      .catch(() => setState("missing"));
  }, [slug]);

  const submit = async () => {
    setBusy(true);
    try {
      const ordered = quiz.questions.map((question) =>
        answers[question.index] === undefined ? -1 : answers[question.index]
      );
      const graded = await submitQuiz(slug, ordered);
      setResult(graded);
      if (graded.certificate) {
        toast.success("Passed, and your certificate has been issued.", { duration: 10000 });
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not submit that.");
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") {
    return (
      <Section>
        <p className="text-body text-foreground/60">{t("common.loading")}</p>
      </Section>
    );
  }
  if (state === "missing") {
    return (
      <Section>
        <EmptyState
          title="Quiz unavailable"
          body="This course may not have a quiz, or you may need to sign in."
          action={<LinkButton to="/login">Sign in</LinkButton>}
        />
      </Section>
    );
  }

  return (
    <div data-testid={`quiz-${slug}`}>
      <Section>
        <div className="mx-auto w-full max-w-3xl">
          <Link
            to={`/academy/${slug}`}
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            Back to the course
          </Link>

          <h1 className="mt-6 font-heading text-title-2 font-semibold tracking-tight">
            {quiz.title}
          </h1>
          <p className="mt-2 text-body text-foreground/70">
            {quiz.questions.length} questions &middot; {quiz.passPercent}% to pass &middot; unlimited
            attempts
            {quiz.yourBestScore != null ? ` · your best so far: ${quiz.yourBestScore}%` : ""}
          </p>

          {result ? (
            <div className="mt-8">
              <div
                className={`rounded border p-6 ${
                  result.passed
                    ? "border-primary/30 bg-primary/5"
                    : "border-amber-600/30 bg-amber-600/10"
                }`}
              >
                <p className="font-heading text-title-2 font-semibold tracking-tight">
                  {result.score}%
                </p>
                <p className="mt-1 text-body text-foreground/80">
                  {result.passed ? "Passed" : `You need ${result.passPercent}% to pass`}
                  {" · "}
                  {result.lessonsDone}/{result.totalLessons} lessons read
                </p>
                {result.nextStep ? (
                  <p className="mt-3 text-body text-foreground/75">{result.nextStep}</p>
                ) : null}

                {result.certificate ? (
                  <div className="mt-5 rounded border border-border bg-card p-5">
                    <p className="flex items-center gap-2 text-label font-bold uppercase text-primary">
                      <Award className="h-4 w-4" aria-hidden="true" />
                      {t("academy.certificate")}
                    </p>
                    <p className="mt-2 font-mono text-lead">{result.certificate.code}</p>
                    <p className="mt-1 text-meta text-foreground/60">
                      Anyone can verify this code at {window.location.origin}
                      {result.certificate.verifyUrl}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <a
                        href={`/api/certificates/${result.certificate.code}/print`}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-meta text-primary underline-offset-4 hover:underline"
                      >
                        Print / Save as PDF
                      </a>
                      <a
                        href={`/api/certificates/${result.certificate.code}/download`}
                        className="text-meta text-primary underline-offset-4 hover:underline"
                      >
                        Download as Word
                      </a>
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Per-question review with explanations -- the part that teaches. */}
              <ul className="mt-8 space-y-4">
                {result.review.map((item) => (
                  <li
                    key={item.index}
                    className="rounded border border-border bg-card p-5"
                  >
                    <p className="flex items-start gap-2 font-heading text-body font-semibold tracking-tight">
                      {item.isCorrect ? (
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                      ) : (
                        <X className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
                      )}
                      {item.question}
                    </p>
                    <p className="mt-2 text-meta leading-relaxed text-foreground/75">
                      {item.explanation}
                    </p>
                  </li>
                ))}
              </ul>

              <DynamicButton
                variant="outline"
                className="mt-6"
                onClick={() => {
                  setResult(null);
                  setAnswers({});
                }}
              >
                Try again
              </DynamicButton>
            </div>
          ) : (
            <>
              <ol className="mt-8 space-y-6">
                {quiz.questions.map((question) => (
                  <li key={question.index} className="rounded border border-border bg-card p-6">
                    <p className="font-heading text-lead font-semibold tracking-tight">
                      {question.index + 1}. {question.question}
                    </p>
                    <div className="mt-4 space-y-2">
                      {question.options.map((option, optionIndex) => {
                        const id = `q${question.index}-o${optionIndex}`;
                        return (
                          <label
                            key={id}
                            htmlFor={id}
                            className={`flex cursor-pointer items-start gap-3 rounded border p-3 transition-colors ${
                              answers[question.index] === optionIndex
                                ? "border-primary bg-primary/10"
                                : "border-border hover:border-primary/40"
                            }`}
                          >
                            <input
                              id={id}
                              type="radio"
                              name={`question-${question.index}`}
                              checked={answers[question.index] === optionIndex}
                              onChange={() =>
                                setAnswers((prev) => ({ ...prev, [question.index]: optionIndex }))
                              }
                              className="mt-1"
                            />
                            <span className="text-body">{option}</span>
                          </label>
                        );
                      })}
                    </div>
                  </li>
                ))}
              </ol>

              <div className="mt-8 flex items-center gap-4">
                <DynamicButton onClick={submit} disabled={busy} data-testid="submit-quiz">
                  {busy ? "Marking..." : "Submit answers"}
                </DynamicButton>
                <Pill tone="muted">
                  {Object.keys(answers).length}/{quiz.questions.length} answered
                </Pill>
              </div>
            </>
          )}
        </div>
      </Section>
    </div>
  );
}
