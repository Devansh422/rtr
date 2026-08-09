"""Academy: browsing courses, learning, quizzes, completion certificates."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, certificates, limits, search
from backend.core.deps import get_session, require_permission, require_speaking_citizen
from backend.core.models import Certificate, Citizen, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.academy.models import (
    DEFAULT_PASS_PERCENT,
    LEVELS,
    Course,
    Enrollment,
    Lesson,
    Quiz,
    QuizAttempt,
)

router = APIRouter(tags=["academy"])


class CourseIn(BaseModel):
    title: str = Field(..., min_length=6, max_length=240)
    summary: str = Field(default="", max_length=600)
    title_hi: str = ""
    summary_hi: str = ""
    level: str = "beginner"
    estimated_minutes: int = Field(default=30, ge=1, le=1200)
    cover_url: str = ""
    tags: list[str] = Field(default_factory=list)
    sort_order: int = 0


class LessonIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=240)
    body: str = Field(..., min_length=20)
    title_hi: str = ""
    body_hi: str = ""
    article_refs: list[str] = Field(default_factory=list)
    video_ids: list[str] = Field(default_factory=list)
    sort_order: int = 0
    minutes: int = Field(default=5, ge=1, le=240)


class QuizIn(BaseModel):
    title: str = "Check your understanding"
    pass_percent: int = Field(default=DEFAULT_PASS_PERCENT, ge=30, le=100)
    questions: list[dict] = Field(..., min_length=1)


class AttemptIn(BaseModel):
    # One index per question, in order. -1 means "left blank".
    answers: list[int]


def _course_dict(course: Course, *, lesson_count: int = 0, has_quiz: bool = False) -> dict:
    return {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "titleHi": course.title_hi,
        "summary": course.summary,
        "summaryHi": course.summary_hi,
        "level": course.level,
        "levelLabel": LEVELS.get(course.level, course.level),
        "estimatedMinutes": course.estimated_minutes,
        "coverUrl": course.cover_url or None,
        "tags": course.tags,
        "lessonCount": lesson_count,
        "hasQuiz": has_quiz,
        "isPublished": course.is_published,
        "url": f"/academy/{course.slug}",
    }


def _lesson_dict(lesson: Lesson, *, include_body: bool = False) -> dict:
    payload = {
        "id": lesson.id,
        "slug": lesson.slug,
        "title": lesson.title,
        "titleHi": lesson.title_hi,
        "minutes": lesson.minutes,
        "sortOrder": lesson.sort_order,
        # Rendered as links into the Constitution Library.
        "articleRefs": lesson.article_refs,
    }
    if include_body:
        payload.update(
            {"body": lesson.body, "bodyHi": lesson.body_hi, "videoIds": lesson.video_ids}
        )
    return payload


def _public_questions(quiz: Quiz) -> list[dict]:
    """Questions WITHOUT the answers. One of only two readers of quiz.questions."""
    return [
        {
            "index": i,
            "question": q.get("q", ""),
            "questionHi": q.get("q_hi", ""),
            "options": q.get("options", []),
            "optionsHi": q.get("options_hi", []),
        }
        for i, q in enumerate(quiz.questions or [])
    ]


def _grade(quiz: Quiz, answers: list[int]) -> tuple[float, list[dict]]:
    """Score an attempt server-side. The other reader of quiz.questions."""
    questions = quiz.questions or []
    correct = 0
    review = []
    for i, question in enumerate(questions):
        given = answers[i] if i < len(answers) else -1
        expected = question.get("answer", -1)
        is_right = given == expected
        correct += 1 if is_right else 0
        review.append(
            {
                "index": i,
                "question": question.get("q", ""),
                "yourAnswer": given,
                "correctAnswer": expected,
                "isCorrect": is_right,
                # Released only inside a graded result, never from the questions
                # endpoint.
                "explanation": question.get("explanation", ""),
            }
        )
    score = (correct / len(questions) * 100) if questions else 0.0
    return round(score, 1), review


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/academy/levels")
async def list_levels():
    return [{"key": key, "label": label} for key, label in LEVELS.items()]


@router.get("/academy/courses")
async def list_courses(level: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    stmt = (
        select(Course)
        .where(Course.is_published.is_(True))
        .order_by(Course.sort_order, Course.title)
    )
    if level:
        stmt = stmt.where(Course.level == level)
    courses = list((await session.execute(stmt)).scalars())

    counts = dict(
        (
            await session.execute(
                select(Lesson.course_id, func.count())
                .where(Lesson.course_id.in_([c.id for c in courses] or [""]))
                .group_by(Lesson.course_id)
            )
        ).all()
    )
    quiz_ids = set(
        (
            await session.execute(
                select(Quiz.course_id).where(Quiz.course_id.in_([c.id for c in courses] or [""]))
            )
        ).scalars()
    )
    return [
        _course_dict(c, lesson_count=counts.get(c.id, 0), has_quiz=c.id in quiz_ids)
        for c in courses
    ]


@router.get("/academy/courses/{slug}")
async def get_course(slug: str, session: AsyncSession = Depends(get_session)):
    course = (
        await session.execute(
            select(Course).where(Course.slug == slug, Course.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = list(
        (
            await session.execute(
                select(Lesson).where(Lesson.course_id == course.id).order_by(Lesson.sort_order)
            )
        ).scalars()
    )
    quiz = (
        await session.execute(select(Quiz).where(Quiz.course_id == course.id))
    ).scalar_one_or_none()
    return {
        **_course_dict(course, lesson_count=len(lessons), has_quiz=quiz is not None),
        "lessons": [_lesson_dict(lesson) for lesson in lessons],
        "quiz": (
            {"id": quiz.id, "title": quiz.title, "passPercent": quiz.pass_percent, "questionCount": len(quiz.questions or [])}
            if quiz
            else None
        ),
    }


@router.get("/academy/courses/{slug}/lessons/{lesson_slug}")
async def get_lesson(
    slug: str, lesson_slug: str, session: AsyncSession = Depends(get_session)
):
    course = (
        await session.execute(
            select(Course).where(Course.slug == slug, Course.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = list(
        (
            await session.execute(
                select(Lesson).where(Lesson.course_id == course.id).order_by(Lesson.sort_order)
            )
        ).scalars()
    )
    current = next((lesson for lesson in lessons if lesson.slug == lesson_slug), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    position = lessons.index(current)
    return {
        "course": {"slug": course.slug, "title": course.title},
        "lesson": _lesson_dict(current, include_body=True),
        "previous": _lesson_dict(lessons[position - 1]) if position > 0 else None,
        "next": _lesson_dict(lessons[position + 1]) if position + 1 < len(lessons) else None,
        "position": position + 1,
        "total": len(lessons),
    }


# --------------------------------------------------------------------------
# Learner
# --------------------------------------------------------------------------
@router.post("/academy/courses/{slug}/enroll")
async def enroll(
    slug: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    course = (
        await session.execute(
            select(Course).where(Course.slug == slug, Course.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = (
        await session.execute(
            select(Enrollment).where(
                Enrollment.course_id == course.id, Enrollment.citizen_id == citizen.id
            )
        )
    ).scalar_one_or_none()
    if enrollment is None:
        enrollment = Enrollment(course_id=course.id, citizen_id=citizen.id, completed_lessons=[])
        session.add(enrollment)
        await session.flush()
    return {"ok": True, "enrollmentId": enrollment.id, "completedLessons": enrollment.completed_lessons}


@router.post("/academy/lessons/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    lesson = (await session.execute(select(Lesson).where(Lesson.id == lesson_id))).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    enrollment = (
        await session.execute(
            select(Enrollment).where(
                Enrollment.course_id == lesson.course_id, Enrollment.citizen_id == citizen.id
            )
        )
    ).scalar_one_or_none()
    if enrollment is None:
        # Marking a lesson done is itself an enrolment signal; making the learner
        # go back and press "enrol" first would be pure ceremony.
        enrollment = Enrollment(
            course_id=lesson.course_id, citizen_id=citizen.id, completed_lessons=[]
        )
        session.add(enrollment)
        await session.flush()

    done = list(enrollment.completed_lessons or [])
    if lesson_id not in done:
        done.append(lesson_id)
        enrollment.completed_lessons = done

    total = (
        await session.execute(
            select(func.count()).select_from(Lesson).where(Lesson.course_id == lesson.course_id)
        )
    ).scalar_one()
    return {
        "ok": True,
        "completed": len(done),
        "total": total,
        "allLessonsDone": len(done) >= total,
    }


@router.get("/academy/courses/{slug}/quiz")
async def get_quiz(
    slug: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Quiz questions, answers stripped. Requires sign-in so attempts can be recorded."""
    course = (
        await session.execute(
            select(Course).where(Course.slug == slug, Course.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = (
        await session.execute(select(Quiz).where(Quiz.course_id == course.id))
    ).scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=404, detail="This course has no quiz")

    best = (
        await session.execute(
            select(func.max(QuizAttempt.score_percent)).where(
                QuizAttempt.quiz_id == quiz.id, QuizAttempt.citizen_id == citizen.id
            )
        )
    ).scalar_one()
    return {
        "quizId": quiz.id,
        "title": quiz.title,
        "passPercent": quiz.pass_percent,
        "questions": _public_questions(quiz),
        "yourBestScore": best,
    }


@router.post("/academy/courses/{slug}/quiz")
async def submit_quiz(
    slug: str,
    payload: AttemptIn,
    request: Request,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Grade an attempt and, on a pass with all lessons read, issue the certificate.

    Both conditions are required. Passing the quiz without reading the course is
    possible for anyone who already knows the material -- fine -- but the
    certificate says "completed", so completing the lessons is part of earning it.
    """
    course = (
        await session.execute(
            select(Course).where(Course.slug == slug, Course.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz = (
        await session.execute(select(Quiz).where(Quiz.course_id == course.id))
    ).scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=404, detail="This course has no quiz")

    await limits.check("quiz.attempt", f"m:{citizen.email}")

    score, review = _grade(quiz, payload.answers)
    passed = score >= quiz.pass_percent
    session.add(
        QuizAttempt(
            quiz_id=quiz.id,
            citizen_id=citizen.id,
            score_percent=score,
            passed=passed,
            answers=payload.answers,
        )
    )

    enrollment = (
        await session.execute(
            select(Enrollment).where(
                Enrollment.course_id == course.id, Enrollment.citizen_id == citizen.id
            )
        )
    ).scalar_one_or_none()
    total_lessons = (
        await session.execute(
            select(func.count()).select_from(Lesson).where(Lesson.course_id == course.id)
        )
    ).scalar_one()
    lessons_done = len((enrollment.completed_lessons if enrollment else []) or [])
    all_lessons_done = lessons_done >= total_lessons

    certificate = None
    if passed and all_lessons_done:
        existing = [
            c
            for c in (
                await session.execute(
                    select(Certificate).where(
                        Certificate.citizen_id == citizen.id,
                        Certificate.kind == "course_completion",
                    )
                )
            ).scalars()
            if c.detail.get("courseSlug") == course.slug
        ]
        if existing:
            certificate = certificates.to_dict(existing[0])
        else:
            issued = await certificates.issue(
                session,
                kind="course_completion",
                holder_name=citizen.display_name or citizen.email.split("@")[0],
                title=f"For completing {course.title}",
                detail={
                    "Course": course.title,
                    "Level": LEVELS.get(course.level, course.level),
                    "Score": f"{score:g}%",
                    "courseSlug": course.slug,
                },
                citizen_id=citizen.id,
                holder_email=citizen.email,
            )
            certificate = certificates.to_dict(issued)
        if enrollment is not None and enrollment.completed_at is None:
            enrollment.completed_at = utcnow()

    return {
        "score": score,
        "passPercent": quiz.pass_percent,
        "passed": passed,
        "allLessonsDone": all_lessons_done,
        "lessonsDone": lessons_done,
        "totalLessons": total_lessons,
        "review": review,
        "certificate": certificate,
        "nextStep": (
            None
            if certificate
            else (
                "Finish the remaining lessons to earn your certificate."
                if passed
                else f"You need {quiz.pass_percent}% to pass. Review the lessons and try again -- "
                "there is no limit on attempts."
            )
        ),
    }


@router.get("/me/academy")
async def my_academy(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Enrollment, Course)
            .join(Course, Course.id == Enrollment.course_id)
            .where(Enrollment.citizen_id == citizen.id)
        )
    ).all()
    lesson_counts = dict(
        (
            await session.execute(
                select(Lesson.course_id, func.count())
                .where(Lesson.course_id.in_([c.id for _, c in rows] or [""]))
                .group_by(Lesson.course_id)
            )
        ).all()
    )
    issued = {
        c.detail.get("courseSlug"): certificates.to_dict(c)
        for c in (
            await session.execute(
                select(Certificate).where(
                    Certificate.citizen_id == citizen.id,
                    Certificate.kind == "course_completion",
                )
            )
        ).scalars()
    }
    return [
        {
            **_course_dict(course, lesson_count=lesson_counts.get(course.id, 0)),
            "completedLessons": len(enrollment.completed_lessons or []),
            "completedAt": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "certificate": issued.get(course.slug),
        }
        for enrollment, course in rows
    ]


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.get("/admin/academy/courses")
async def admin_list_courses(
    admin: Principal = Depends(require_permission("academy.manage")),
    session: AsyncSession = Depends(get_session),
):
    courses = list((await session.execute(select(Course).order_by(Course.sort_order))).scalars())
    counts = dict(
        (
            await session.execute(
                select(Lesson.course_id, func.count())
                .where(Lesson.course_id.in_([c.id for c in courses] or [""]))
                .group_by(Lesson.course_id)
            )
        ).all()
    )
    enrolments = dict(
        (
            await session.execute(
                select(Enrollment.course_id, func.count())
                .where(Enrollment.course_id.in_([c.id for c in courses] or [""]))
                .group_by(Enrollment.course_id)
            )
        ).all()
    )
    return [
        {
            **_course_dict(c, lesson_count=counts.get(c.id, 0)),
            "enrolments": enrolments.get(c.id, 0),
        }
        for c in courses
    ]


@router.post("/admin/academy/courses")
async def create_course(
    payload: CourseIn,
    request: Request,
    admin: Principal = Depends(require_permission("academy.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.level not in LEVELS:
        raise HTTPException(status_code=400, detail=f"level must be one of {list(LEVELS)}")
    slug = slugify(payload.title)
    if (await session.execute(select(Course).where(Course.slug == slug))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A course with that title already exists")

    course = Course(
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        summary=payload.summary.strip(),
        summary_hi=payload.summary_hi.strip(),
        level=payload.level,
        estimated_minutes=payload.estimated_minutes,
        cover_url=payload.cover_url,
        tags=payload.tags,
        sort_order=payload.sort_order,
    )
    session.add(course)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="course",
        entity_id=slug,
        summary=f"Created course: {course.title}",
        is_public=False,
        request=request,
    )
    return _course_dict(course)


@router.post("/admin/academy/courses/{course_id}/lessons")
async def create_lesson(
    course_id: str,
    payload: LessonIn,
    admin: Principal = Depends(require_permission("academy.manage")),
    session: AsyncSession = Depends(get_session),
):
    course = (await session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    slug = slugify(payload.title)
    existing = (
        await session.execute(
            select(Lesson).where(Lesson.course_id == course_id, Lesson.slug == slug)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A lesson with that title already exists in this course")

    lesson = Lesson(
        course_id=course_id,
        slug=slug,
        title=payload.title.strip(),
        title_hi=payload.title_hi.strip(),
        body=payload.body,
        body_hi=payload.body_hi,
        article_refs=[str(a).upper() for a in payload.article_refs],
        video_ids=payload.video_ids,
        sort_order=payload.sort_order,
        minutes=payload.minutes,
    )
    session.add(lesson)
    await session.flush()
    return _lesson_dict(lesson, include_body=True)


@router.put("/admin/academy/courses/{course_id}/quiz")
async def upsert_quiz(
    course_id: str,
    payload: QuizIn,
    admin: Principal = Depends(require_permission("academy.manage")),
    session: AsyncSession = Depends(get_session),
):
    course = (await session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    for i, question in enumerate(payload.questions):
        options = question.get("options") or []
        if len(options) < 2:
            raise HTTPException(status_code=400, detail=f"Question {i + 1} needs at least two options")
        answer = question.get("answer")
        if not isinstance(answer, int) or not (0 <= answer < len(options)):
            raise HTTPException(
                status_code=400,
                detail=f"Question {i + 1}: 'answer' must be the index of one of its options",
            )
        if not (question.get("explanation") or "").strip():
            # A quiz that says "wrong" without saying why teaches nothing, and
            # teaching is the entire point of the module.
            raise HTTPException(
                status_code=400,
                detail=f"Question {i + 1} needs an explanation -- learners are shown it after grading",
            )

    quiz = (
        await session.execute(select(Quiz).where(Quiz.course_id == course_id))
    ).scalar_one_or_none()
    if quiz is None:
        quiz = Quiz(course_id=course_id)
        session.add(quiz)

    quiz.title = payload.title
    quiz.pass_percent = payload.pass_percent
    quiz.questions = payload.questions
    await session.flush()
    return {"quizId": quiz.id, "questionCount": len(quiz.questions), "passPercent": quiz.pass_percent}


@router.post("/admin/academy/courses/{course_id}/publish")
async def publish_course(
    course_id: str,
    request: Request,
    publish: bool = True,
    admin: Principal = Depends(require_permission("academy.manage")),
    session: AsyncSession = Depends(get_session),
):
    course = (await session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lesson_count = (
        await session.execute(
            select(func.count()).select_from(Lesson).where(Lesson.course_id == course_id)
        )
    ).scalar_one()
    if publish and lesson_count == 0:
        raise HTTPException(status_code=400, detail="Add at least one lesson before publishing")

    course.is_published = publish
    await audit.record(
        session,
        actor=admin,
        action="publish" if publish else "unpublish",
        entity_type="course",
        entity_id=course.slug,
        summary=f"{'Published' if publish else 'Unpublished'} course: {course.title}",
        is_public=False,
        request=request,
    )
    await search.index(
        session,
        entity_type="course",
        entity_id=course.slug,
        title=course.title,
        subtitle=f"Course - {LEVELS.get(course.level, course.level)}",
        body=course.summary,
        keywords=course.tags,
        is_published=publish,
        url_path=f"/academy/{course.slug}",
    )
    return _course_dict(course, lesson_count=lesson_count)
