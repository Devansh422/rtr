import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill, StatTile } from "@/components/platform/Primitives";
import { getCourse } from "@/lib/platformApi";
import { enrollInCourse, getMyAcademy } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, Check, Clock } from "lucide-react";

export default function CoursePage() {
  const { slug } = useParams();
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [course, setCourse] = useState(null);
  const [progress, setProgress] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    getCourse(slug)
      .then((data) => {
        setCourse(data);
        setState("ready");
      })
      .catch(() => setState("missing"));
  }, [slug]);

  useEffect(() => {
    if (memberStatus !== "in") return;
    getMyAcademy()
      .then((mine) => setProgress(mine.find((entry) => entry.slug === slug) ?? null))
      .catch(() => {});
  }, [memberStatus, slug]);

  const enroll = async () => {
    try {
      await enrollInCourse(slug);
      toast.success("Enrolled. Your progress is saved as you go.");
      const mine = await getMyAcademy();
      setProgress(mine.find((entry) => entry.slug === slug) ?? null);
    } catch {
      toast.error("Could not enrol just now.");
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
          title="Course not found"
          body="It may not be published yet."
          action={<LinkButton to="/academy">All courses</LinkButton>}
        />
      </Section>
    );
  }

  const done = progress?.completedLessons ?? 0;

  return (
    <div data-testid={`course-page-${course.slug}`}>
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-4xl">
          <Link
            to="/academy"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.academy")}
          </Link>
          <div className="mt-6 flex flex-wrap gap-2">
            <Pill tone="secondary">{course.levelLabel}</Pill>
            <Pill tone="muted">
              <Clock className="mr-1 h-3 w-3" aria-hidden="true" />
              {course.estimatedMinutes} min
            </Pill>
            <Pill tone="muted">{course.lessonCount} lessons</Pill>
          </div>
          <h1 className="mt-5 font-heading text-title-1 font-semibold leading-[1.05] tracking-tighter">
            {course.title}
          </h1>
          <p className="mt-5 text-lead text-foreground/75">{course.summary}</p>

          <div className="mt-8 flex flex-wrap gap-3">
            {memberStatus === "in" ? (
              progress ? (
                <LinkButton to={`/academy/${course.slug}/${course.lessons[Math.min(done, course.lessons.length - 1)]?.slug}`} size="lg">
                  {done ? t("academy.continue") : t("academy.startCourse")}
                </LinkButton>
              ) : (
                <DynamicButton size="lg" onClick={enroll}>
                  {t("academy.startCourse")}
                </DynamicButton>
              )
            ) : (
              <>
                <LinkButton to={`/academy/${course.slug}/${course.lessons[0]?.slug}`} size="lg">
                  Read the first lesson
                </LinkButton>
                <LinkButton to="/login" variant="outline" size="lg">
                  Sign in to track progress
                </LinkButton>
              </>
            )}
          </div>
        </div>
      </section>

      <Section>
        <div className="mx-auto grid w-full max-w-5xl gap-10 lg:grid-cols-[1fr_300px]">
          <div>
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">Lessons</h2>
            <ol className="mt-6 space-y-3">
              {course.lessons.map((lesson, index) => (
                <li key={lesson.id}>
                  <Link
                    to={`/academy/${course.slug}/${lesson.slug}`}
                    className="flex items-center gap-4 rounded border border-border bg-card p-5 hover:border-primary/40"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border font-heading text-meta font-bold">
                      {index < done ? <Check className="h-4 w-4 text-primary" /> : index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-heading text-body font-semibold tracking-tight">
                        {lesson.title}
                      </p>
                      {lesson.articleRefs?.length ? (
                        <p className="mt-1 text-meta text-foreground/60">
                          Articles {lesson.articleRefs.join(", ")}
                        </p>
                      ) : null}
                    </div>
                    <span className="text-meta text-foreground/50">{lesson.minutes} min</span>
                  </Link>
                </li>
              ))}
            </ol>

            {course.quiz ? (
              <div className="mt-8 rounded border border-primary/30 bg-primary/5 p-6">
                <p className="font-heading text-lead font-semibold tracking-tight">
                  {course.quiz.title}
                </p>
                <p className="mt-2 text-body text-foreground/75">
                  {course.quiz.questionCount} questions, {course.quiz.passPercent}% to pass, no limit
                  on attempts. Pass it with all lessons read and the certificate is issued
                  automatically.
                </p>
                {memberStatus === "in" ? (
                  <LinkButton to={`/academy/${course.slug}/quiz`} className="mt-4">
                    {t("academy.takeQuiz")}
                  </LinkButton>
                ) : (
                  <LinkButton to="/login" variant="outline" className="mt-4">
                    Sign in to take the quiz
                  </LinkButton>
                )}
              </div>
            ) : null}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            {progress ? (
              <>
                <StatTile
                  label="Your progress"
                  value={`${done}/${course.lessonCount}`}
                  sub="lessons read"
                  tone="primary"
                />
                {progress.certificate ? (
                  <div className="rounded border border-primary/30 bg-primary/5 p-5">
                    <p className="text-label font-bold uppercase text-primary">
                      {t("academy.certificate")}
                    </p>
                    <p className="mt-2 font-mono text-body">{progress.certificate.code}</p>
                    <a
                      href={`/api/certificates/${progress.certificate.code}/print`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mt-3 inline-block text-meta text-primary underline-offset-4 hover:underline"
                    >
                      Print or save it
                    </a>
                  </div>
                ) : null}
              </>
            ) : null}

            {course.tags?.length ? (
              <div className="rounded border border-border bg-card p-5">
                <p className="text-label font-bold uppercase text-muted-foreground">Topics</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {course.tags.map((tag) => (
                    <Pill key={tag} tone="muted">
                      {tag}
                    </Pill>
                  ))}
                </div>
              </div>
            ) : null}
          </aside>
        </div>
      </Section>
    </div>
  );
}
