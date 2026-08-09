import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { getLesson } from "@/lib/platformApi";
import { completeLesson } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";

export default function LessonPage() {
  const { slug, lessonSlug } = useParams();
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [marked, setMarked] = useState(false);

  useEffect(() => {
    setMarked(false);
    getLesson(slug, lessonSlug)
      .then((result) => {
        setData(result);
        setState("ready");
      })
      .catch(() => setState("missing"));
  }, [slug, lessonSlug]);

  const markDone = async () => {
    try {
      const result = await completeLesson(data.lesson.id);
      setMarked(true);
      toast.success(
        result.allLessonsDone
          ? "That is the last lesson. The quiz is now the only thing between you and the certificate."
          : `${result.completed} of ${result.total} lessons read.`
      );
      if (data.next) navigate(`/academy/${slug}/${data.next.slug}`);
    } catch {
      toast.error("Could not save that just now.");
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
          title="Lesson not found"
          action={<LinkButton to="/academy">All courses</LinkButton>}
        />
      </Section>
    );
  }

  const { course, lesson, previous, next, position, total } = data;

  return (
    <div data-testid={`lesson-${lesson.slug}`}>
      <Section>
        <div className="mx-auto w-full max-w-3xl">
          <Link
            to={`/academy/${course.slug}`}
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {course.title}
          </Link>

          <p className="mt-6 text-label font-bold uppercase text-secondary">
            Lesson {position} {t("common.of")} {total}
          </p>
          <h1 className="mt-3 font-heading text-title-2 font-semibold leading-[1.15] tracking-tight">
            {lesson.title}
          </h1>

          {lesson.articleRefs?.length ? (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <span className="text-meta text-foreground/60">Read alongside:</span>
              {lesson.articleRefs.map((article) => (
                <Link key={article} to={`/constitution/${article}`}>
                  <Pill tone="primary">Article {article}</Pill>
                </Link>
              ))}
            </div>
          ) : null}

          <div className="mt-8 space-y-5">
            {lesson.body
              .split("\n\n")
              .filter(Boolean)
              .map((paragraph, index) => (
                <p key={index} className="text-body leading-relaxed text-foreground/85">
                  {paragraph}
                </p>
              ))}
          </div>

          {lesson.videoIds?.length ? (
            <div className="mt-8 space-y-4">
              {lesson.videoIds.map((videoId) => (
                <div key={videoId} className="aspect-video overflow-hidden rounded border border-border">
                  <iframe
                    src={`https://www.youtube-nocookie.com/embed/${videoId}`}
                    title="Lesson video"
                    allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    className="h-full w-full"
                  />
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
            {previous ? (
              <LinkButton to={`/academy/${course.slug}/${previous.slug}`} variant="ghost">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                {previous.title}
              </LinkButton>
            ) : (
              <span />
            )}

            <div className="flex flex-wrap gap-3">
              {memberStatus === "in" ? (
                <DynamicButton onClick={markDone} disabled={marked}>
                  <Check className="h-4 w-4" aria-hidden="true" />
                  {marked ? "Saved" : t("academy.markDone")}
                </DynamicButton>
              ) : null}
              {next ? (
                <LinkButton to={`/academy/${course.slug}/${next.slug}`} variant="outline">
                  {next.title}
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </LinkButton>
              ) : (
                <LinkButton to={`/academy/${course.slug}/quiz`}>{t("academy.takeQuiz")}</LinkButton>
              )}
            </div>
          </div>
        </div>
      </Section>
    </div>
  );
}
