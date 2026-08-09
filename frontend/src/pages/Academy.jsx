import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { PageHero, Section, SectionHeading, EmptyState, Pill } from "@/components/platform/Primitives";
import { getAcademyLevels, getCourses } from "@/lib/platformApi";
import { useLocale } from "@/context/LocaleContext";
import { Clock, GraduationCap } from "lucide-react";

export default function Academy() {
  const { t } = useLocale();
  const [courses, setCourses] = useState([]);
  const [levels, setLevels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAcademyLevels().then(setLevels);
    getCourses()
      .then(setCourses)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="academy-page">
      <PageHero
        eyebrow="Learning Academy"
        lines={["Understand the system", "you are trying", "to change."]}
        lede={t("academy.lede")}
      />

      <Section>
        {loading ? (
          <p className="text-body text-foreground/60">{t("common.loading")}</p>
        ) : courses.length === 0 ? (
          <EmptyState
            title="No courses published yet"
            body="Courses are written and reviewed before they go live. The first one covers the Right to Recall case end to end."
          />
        ) : (
          levels.map((level) => {
            const inLevel = courses.filter((course) => course.level === level.key);
            if (!inLevel.length) return null;
            return (
              <div key={level.key} className="mb-14 last:mb-0">
                <SectionHeading eyebrow={level.label} title={`${inLevel.length} course${inLevel.length === 1 ? "" : "s"}`} />
                <StaggerGroup className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                  {inLevel.map((course) => (
                    <StaggerItem key={course.id}>
                      <Link
                        to={course.url}
                        className="group flex h-full flex-col rounded border border-border bg-card p-6 transition-transform duration-300 hover:-translate-y-1 hover:border-primary/40"
                        data-testid={`course-${course.slug}`}
                      >
                        <div className="flex h-11 w-11 items-center justify-center rounded bg-secondary">
                          <GraduationCap className="h-5 w-5 text-secondary-foreground" aria-hidden="true" />
                        </div>
                        <h3 className="mt-4 font-heading text-lead font-semibold leading-snug tracking-tight group-hover:text-primary">
                          {course.title}
                        </h3>
                        <p className="mt-2 flex-1 text-body text-foreground/70">{course.summary}</p>
                        <div className="mt-4 flex flex-wrap items-center gap-3 text-meta text-foreground/60">
                          <span className="inline-flex items-center gap-1.5">
                            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                            {course.estimatedMinutes} min
                          </span>
                          <span>{course.lessonCount} lessons</span>
                          {course.hasQuiz ? <Pill tone="muted">Certificate</Pill> : null}
                        </div>
                      </Link>
                    </StaggerItem>
                  ))}
                </StaggerGroup>
              </div>
            );
          })
        )}
      </Section>

      <Section muted>
        <div className="rounded border border-border bg-card p-8">
          <h2 className="font-heading text-title-3 font-semibold tracking-tight">
            Certificates you can actually verify
          </h2>
          <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/70">
            Finish the lessons and pass the quiz and the platform issues a certificate with a short
            code on it. Anyone &mdash; an employer, a university, a fellow organiser &mdash; can
            check that code against this site and see who holds it and what for. A certificate that
            cannot be checked is a decorated image; this one is a record.
          </p>
          <p className="mt-3 max-w-3xl text-body leading-relaxed text-foreground/70">
            The wording is deliberately modest. This is a civic learning record, not an academic
            qualification, and overclaiming would make every certificate we issue worth less.
          </p>
        </div>
      </Section>
    </div>
  );
}
