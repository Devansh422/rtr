"""Volunteer Portal endpoints: profile, task board, submissions, verified hours."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import audit, certificates, notify
from backend.core.deps import (
    get_session,
    require_permission,
    require_speaking_citizen,
    require_state_scope,
)
from backend.core.documents import DOCX_MEDIA_TYPE
from backend.core.models import Certificate, Citizen, utcnow
from backend.core.rbac import Principal
from backend.core.security import slugify
from backend.modules.volunteers.models import (
    ASSIGNMENT_LABELS,
    CERTIFICATE_HOURS_THRESHOLD,
    SKILLS,
    AssignmentStatus,
    TaskAssignment,
    TaskStatus,
    VolunteerProfile,
    VolunteerTask,
)

router = APIRouter(tags=["volunteers"])


class ProfileIn(BaseModel):
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    hours_per_week: Optional[int] = Field(default=None, ge=1, le=60)
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    city: str = ""
    bio: str = Field(default="", max_length=1000)


class TaskIn(BaseModel):
    title: str = Field(..., min_length=8, max_length=240)
    description: str = Field(..., min_length=30)
    skill: str
    acceptance_criteria: str = Field(default="", max_length=2000)
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    is_remote: bool = True
    estimated_hours: float = Field(default=1.0, gt=0, le=200)
    capacity: int = Field(default=1, ge=1, le=200)
    due_on: Optional[date] = None


class SubmissionIn(BaseModel):
    note: str = Field(..., min_length=10)
    url: str = ""
    hours_claimed: float = Field(..., gt=0, le=200)


class VerifyIn(BaseModel):
    approve: bool
    hours_verified: Optional[float] = Field(default=None, ge=0, le=200)
    note: str = ""


def _task_dict(task: VolunteerTask) -> dict:
    return {
        "id": task.id,
        "slug": task.slug,
        "title": task.title,
        "description": task.description,
        "skill": task.skill,
        "skillLabel": SKILLS.get(task.skill, task.skill),
        "acceptanceCriteria": task.acceptance_criteria or None,
        "state": task.state_code,
        "district": task.district_code,
        "isRemote": task.is_remote,
        "estimatedHours": task.estimated_hours,
        "capacity": task.capacity,
        "claimedCount": task.claimed_count,
        "slotsLeft": max(0, task.capacity - task.claimed_count),
        "status": task.status,
        "dueOn": task.due_on.isoformat() if task.due_on else None,
        "url": f"/volunteer/tasks/{task.slug}",
    }


def _assignment_dict(assignment: TaskAssignment, task: Optional[VolunteerTask]) -> dict:
    return {
        "id": assignment.id,
        "status": assignment.status,
        "statusLabel": ASSIGNMENT_LABELS.get(assignment.status, assignment.status),
        "task": _task_dict(task) if task else None,
        "submissionNote": assignment.submission_note or None,
        "submissionUrl": assignment.submission_url or None,
        "hoursClaimed": assignment.hours_claimed,
        "hoursVerified": assignment.hours_verified,
        "reviewNote": assignment.review_note or None,
        "claimedOn": assignment.created_at.date().isoformat() if assignment.created_at else None,
        "verifiedOn": assignment.verified_at.date().isoformat() if assignment.verified_at else None,
    }


async def _profile_for(session: AsyncSession, citizen: Citizen) -> VolunteerProfile:
    profile = (
        await session.execute(
            select(VolunteerProfile).where(VolunteerProfile.citizen_id == citizen.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Tell us what you can help with first -- create your volunteer profile.",
        )
    return profile


async def _recount_profile(session: AsyncSession, profile: VolunteerProfile) -> None:
    """Recompute verified hours from the assignment rows.

    Recomputed rather than incremented, for the same reason petition counts are:
    the number appears on a certificate, and an increment that runs twice or not at
    all is a certificate that overstates or understates someone's service.
    """
    rows = (
        await session.execute(
            select(func.coalesce(func.sum(TaskAssignment.hours_verified), 0.0), func.count())
            .select_from(TaskAssignment)
            .where(
                TaskAssignment.profile_id == profile.id,
                TaskAssignment.status == AssignmentStatus.VERIFIED,
            )
        )
    ).one()
    profile.verified_hours = float(rows[0] or 0.0)
    profile.completed_tasks = int(rows[1] or 0)


async def _sync_task_counts(session: AsyncSession, task: VolunteerTask) -> None:
    task.claimed_count = (
        await session.execute(
            select(func.count())
            .select_from(TaskAssignment)
            .where(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status.in_(
                    [
                        AssignmentStatus.CLAIMED,
                        AssignmentStatus.SUBMITTED,
                        AssignmentStatus.VERIFIED,
                        AssignmentStatus.RETURNED,
                    ]
                ),
            )
        )
    ).scalar_one()
    if task.status != TaskStatus.CLOSED:
        task.status = TaskStatus.FULL if task.claimed_count >= task.capacity else TaskStatus.OPEN


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------
@router.get("/volunteer/skills")
async def list_skills():
    return [{"key": key, "label": label} for key, label in SKILLS.items()]


@router.get("/volunteer/tasks")
async def list_tasks(
    skill: Optional[str] = None,
    state: Optional[str] = None,
    remote_only: bool = False,
    limit: int = Query(default=40, ge=1, le=120),
    session: AsyncSession = Depends(get_session),
):
    """The task board. Open tasks only, soonest deadline first."""
    stmt = select(VolunteerTask).where(VolunteerTask.status == TaskStatus.OPEN)
    if skill:
        stmt = stmt.where(VolunteerTask.skill == skill)
    if state:
        # A national task (state_code NULL) is relevant to every state, so it is
        # included rather than filtered out -- otherwise choosing a state hides
        # most of the board.
        stmt = stmt.where(
            (VolunteerTask.state_code == state.upper()) | (VolunteerTask.state_code.is_(None))
        )
    if remote_only:
        stmt = stmt.where(VolunteerTask.is_remote.is_(True))

    rows = list((await session.execute(stmt.limit(limit))).scalars())
    rows.sort(key=lambda t: (t.due_on or date.max, -t.estimated_hours))
    return {"total": len(rows), "items": [_task_dict(t) for t in rows]}


@router.get("/volunteer/tasks/{slug}")
async def get_task(slug: str, session: AsyncSession = Depends(get_session)):
    task = (
        await session.execute(select(VolunteerTask).where(VolunteerTask.slug == slug))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_dict(task)


# --------------------------------------------------------------------------
# Volunteer's own portal
# --------------------------------------------------------------------------
@router.put("/me/volunteer/profile")
async def upsert_profile(
    payload: ProfileIn,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    unknown = [s for s in payload.skills if s not in SKILLS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown skills: {unknown}")

    profile = (
        await session.execute(
            select(VolunteerProfile).where(VolunteerProfile.citizen_id == citizen.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        profile = VolunteerProfile(citizen_id=citizen.id)
        session.add(profile)

    profile.skills = payload.skills
    profile.languages = payload.languages[:12]
    profile.hours_per_week = payload.hours_per_week
    profile.state_code = payload.state_code.upper() if payload.state_code else profile.state_code
    profile.district_code = payload.district_code.upper() if payload.district_code else None
    profile.city = payload.city.strip()
    profile.bio = payload.bio.strip()
    profile.is_active = True
    await session.flush()

    if payload.state_code and not citizen.state_code:
        citizen.state_code = payload.state_code.upper()

    return {
        "id": profile.id,
        "skills": profile.skills,
        "languages": profile.languages,
        "hoursPerWeek": profile.hours_per_week,
        "state": profile.state_code,
        "city": profile.city,
        "verifiedHours": profile.verified_hours,
    }


@router.get("/me/volunteer")
async def my_volunteer_dashboard(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    profile = (
        await session.execute(
            select(VolunteerProfile).where(VolunteerProfile.citizen_id == citizen.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        return {
            "hasProfile": False,
            "skills": [{"key": k, "label": v} for k, v in SKILLS.items()],
        }

    rows = (
        await session.execute(
            select(TaskAssignment, VolunteerTask)
            .join(VolunteerTask, VolunteerTask.id == TaskAssignment.task_id)
            .where(TaskAssignment.profile_id == profile.id)
            .order_by(TaskAssignment.created_at.desc())
        )
    ).all()

    issued = list(
        (
            await session.execute(
                select(Certificate).where(
                    Certificate.citizen_id == citizen.id,
                    Certificate.kind == "volunteer_hours",
                )
            )
        ).scalars()
    )

    return {
        "hasProfile": True,
        "profile": {
            "id": profile.id,
            "skills": profile.skills,
            "languages": profile.languages,
            "hoursPerWeek": profile.hours_per_week,
            "state": profile.state_code,
            "city": profile.city,
            "bio": profile.bio,
            "verifiedHours": profile.verified_hours,
            "completedTasks": profile.completed_tasks,
        },
        "assignments": [_assignment_dict(a, t) for a, t in rows],
        "certificate": {
            "eligible": profile.verified_hours >= CERTIFICATE_HOURS_THRESHOLD,
            "hoursNeeded": max(0.0, CERTIFICATE_HOURS_THRESHOLD - profile.verified_hours),
            "threshold": CERTIFICATE_HOURS_THRESHOLD,
            "issued": [certificates.to_dict(c) for c in issued],
        },
    }


@router.post("/volunteer/tasks/{slug}/claim")
async def claim_task(
    slug: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    task = (
        await session.execute(select(VolunteerTask).where(VolunteerTask.slug == slug))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.OPEN:
        raise HTTPException(status_code=400, detail="This task is no longer taking volunteers")

    profile = await _profile_for(session, citizen)
    if task.skill not in (profile.skills or []):
        # A warning, not a refusal: someone who wants to try something outside
        # their listed skills should be allowed to, and the manager sees the
        # mismatch at verification time.
        pass

    existing = (
        await session.execute(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task.id, TaskAssignment.profile_id == profile.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already taken this task")

    session.add(TaskAssignment(task_id=task.id, profile_id=profile.id))
    await session.flush()
    await _sync_task_counts(session, task)

    return {
        "ok": True,
        "task": _task_dict(task),
        "message": (
            "Task claimed. When you are done, submit it with a note on what you did and how long "
            "it took -- a Volunteer Manager confirms the hours before they count."
        ),
    }


@router.post("/me/volunteer/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: str,
    payload: SubmissionIn,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    profile = await _profile_for(session, citizen)
    assignment = (
        await session.execute(
            select(TaskAssignment).where(
                TaskAssignment.id == assignment_id, TaskAssignment.profile_id == profile.id
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status == AssignmentStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="This work has already been verified")

    assignment.submission_note = payload.note.strip()
    assignment.submission_url = payload.url.strip()
    assignment.hours_claimed = payload.hours_claimed
    assignment.status = AssignmentStatus.SUBMITTED
    assignment.review_note = ""

    task = (
        await session.execute(select(VolunteerTask).where(VolunteerTask.id == assignment.task_id))
    ).scalar_one_or_none()
    return _assignment_dict(assignment, task)


@router.delete("/me/volunteer/assignments/{assignment_id}")
async def abandon_assignment(
    assignment_id: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Give a task back so someone else can take it. No penalty."""
    profile = await _profile_for(session, citizen)
    assignment = (
        await session.execute(
            select(TaskAssignment).where(
                TaskAssignment.id == assignment_id, TaskAssignment.profile_id == profile.id
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status == AssignmentStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Verified work cannot be withdrawn")

    task = (
        await session.execute(select(VolunteerTask).where(VolunteerTask.id == assignment.task_id))
    ).scalar_one_or_none()
    await session.delete(assignment)
    await session.flush()
    if task is not None:
        await _sync_task_counts(session, task)
    return {"ok": True}


@router.post("/me/volunteer/certificate")
async def request_certificate(
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    """Issue a service certificate once verified hours clear the threshold.

    Self-service, because the gate is verified hours -- a number no volunteer can
    set themselves. Making a manager click again would add a queue without adding
    a check.
    """
    profile = await _profile_for(session, citizen)
    if profile.verified_hours < CERTIFICATE_HOURS_THRESHOLD:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Certificates are issued at {CERTIFICATE_HOURS_THRESHOLD} verified hours. "
                f"You have {profile.verified_hours:g}."
            ),
        )

    certificate = await certificates.issue(
        session,
        kind="volunteer_hours",
        holder_name=citizen.display_name or citizen.email.split("@")[0],
        title="For volunteer service to the Right to Recall Movement",
        detail={
            "Verified hours": f"{profile.verified_hours:g}",
            "Tasks completed": profile.completed_tasks,
            "Skills": ", ".join(SKILLS.get(s, s) for s in (profile.skills or [])) or "General",
        },
        citizen_id=citizen.id,
        holder_email=citizen.email,
    )

    await notify.send_email(
        to=citizen.email,
        subject="Your Right to Recall volunteer certificate",
        html=notify.render(
            "Thank you for your service",
            notify.paragraph(
                f"Your certificate for {profile.verified_hours:g} verified volunteer hours is ready."
            )
            + notify.paragraph(f"Certificate code: <strong>{certificate.code}</strong>")
            + notify.button("Download your certificate", "/dashboard"),
        ),
    )
    return certificates.to_dict(certificate)


@router.get("/me/volunteer/certificate/{code}.docx")
async def download_certificate(
    code: str,
    citizen: Citizen = Depends(require_speaking_citizen),
    session: AsyncSession = Depends(get_session),
):
    certificate = (
        await session.execute(
            select(Certificate).where(
                Certificate.code == code.upper(), Certificate.citizen_id == citizen.id
            )
        )
    ).scalar_one_or_none()
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")

    draft = certificates.render(certificate, site_url=notify.SITE_URL)
    return Response(
        content=draft.docx(),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{draft.filename}"'},
    )


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@router.post("/admin/volunteer/tasks")
async def create_task(
    payload: TaskIn,
    request: Request,
    admin: Principal = Depends(require_permission("volunteers.manage")),
    session: AsyncSession = Depends(get_session),
):
    if payload.skill not in SKILLS:
        raise HTTPException(status_code=400, detail=f"skill must be one of {list(SKILLS)}")
    state_code = payload.state_code.upper() if payload.state_code else None
    if state_code:
        require_state_scope(admin, state_code)
    elif not admin.is_platform_wide():
        raise HTTPException(
            status_code=403,
            detail="Your account is scoped to a state, so tasks you create must name that state.",
        )

    slug = slugify(payload.title)
    if (await session.execute(select(VolunteerTask).where(VolunteerTask.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{utcnow().strftime('%m%d%H%M')}"

    task = VolunteerTask(
        slug=slug,
        title=payload.title.strip(),
        description=payload.description.strip(),
        skill=payload.skill,
        acceptance_criteria=payload.acceptance_criteria.strip(),
        state_code=state_code,
        district_code=payload.district_code.upper() if payload.district_code else None,
        is_remote=payload.is_remote,
        estimated_hours=payload.estimated_hours,
        capacity=payload.capacity,
        due_on=payload.due_on,
        created_by=admin.id,
    )
    session.add(task)
    await audit.record(
        session,
        actor=admin,
        action="create",
        entity_type="volunteer_task",
        entity_id=slug,
        summary=f"Created volunteer task: {task.title}",
        is_public=False,
        request=request,
    )
    return _task_dict(task)


@router.post("/admin/volunteer/tasks/{task_id}/close")
async def close_task(
    task_id: str,
    request: Request,
    admin: Principal = Depends(require_permission("volunteers.manage")),
    session: AsyncSession = Depends(get_session),
):
    task = (
        await session.execute(select(VolunteerTask).where(VolunteerTask.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.CLOSED
    await audit.record(
        session,
        actor=admin,
        action="close",
        entity_type="volunteer_task",
        entity_id=task.slug,
        summary=f"Closed volunteer task: {task.title}",
        is_public=False,
        request=request,
    )
    return _task_dict(task)


@router.get("/admin/volunteer/submissions")
async def submission_queue(
    admin: Principal = Depends(require_permission("volunteers.manage")),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(TaskAssignment, VolunteerTask, VolunteerProfile, Citizen)
            .join(VolunteerTask, VolunteerTask.id == TaskAssignment.task_id)
            .join(VolunteerProfile, VolunteerProfile.id == TaskAssignment.profile_id)
            .join(Citizen, Citizen.id == VolunteerProfile.citizen_id)
            .where(TaskAssignment.status == AssignmentStatus.SUBMITTED)
            .order_by(TaskAssignment.updated_at)
        )
    ).all()

    return [
        {
            **_assignment_dict(assignment, task),
            "volunteer": {
                "profileId": profile.id,
                "displayName": citizen.display_name,
                "email": citizen.email,
                "verifiedHours": profile.verified_hours,
                "skills": profile.skills,
                # Flagged so a manager can see the volunteer took work outside
                # their listed skills -- context for reviewing it, not a problem.
                "skillMatch": task.skill in (profile.skills or []),
            },
        }
        for assignment, task, profile, citizen in rows
        if admin.is_platform_wide() or (task.state_code and admin.can_in_state(task.state_code))
    ]


@router.post("/admin/volunteer/submissions/{assignment_id}/verify")
async def verify_submission(
    assignment_id: str,
    payload: VerifyIn,
    request: Request,
    admin: Principal = Depends(require_permission("volunteers.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Confirm or return submitted work.

    A manager may verify FEWER hours than were claimed, with a note. That is not a
    slight on the volunteer -- estimating your own hours is genuinely hard -- but
    the number that ends up on a certificate has to be one the platform can stand
    behind.
    """
    assignment = (
        await session.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id))
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    task = (
        await session.execute(select(VolunteerTask).where(VolunteerTask.id == assignment.task_id))
    ).scalar_one()
    if task.state_code:
        require_state_scope(admin, task.state_code)

    profile = (
        await session.execute(
            select(VolunteerProfile).where(VolunteerProfile.id == assignment.profile_id)
        )
    ).scalar_one()

    if payload.approve:
        hours = payload.hours_verified if payload.hours_verified is not None else assignment.hours_claimed
        assignment.hours_verified = hours
        assignment.status = AssignmentStatus.VERIFIED
        if payload.hours_verified is not None and payload.hours_verified != assignment.hours_claimed:
            if not payload.note.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Explain the adjustment -- the volunteer is shown this note.",
                )
    else:
        if len(payload.note.strip()) < 10:
            raise HTTPException(
                status_code=400, detail="Say what needs changing -- the volunteer is shown this note."
            )
        assignment.status = AssignmentStatus.RETURNED
        assignment.hours_verified = 0.0

    assignment.review_note = payload.note.strip()
    assignment.verified_by = admin.id
    assignment.verified_at = utcnow()
    await session.flush()
    await _recount_profile(session, profile)

    await audit.record(
        session,
        actor=admin,
        action="verify_hours" if payload.approve else "return_work",
        entity_type="task_assignment",
        entity_id=assignment.id,
        summary=(
            f"{task.title}: {'verified' if payload.approve else 'returned'} "
            f"({assignment.hours_verified:g}h of {assignment.hours_claimed:g}h claimed)"
        ),
        is_public=False,
        request=request,
    )
    return {**_assignment_dict(assignment, task), "volunteerVerifiedHours": profile.verified_hours}


@router.get("/admin/volunteer/directory")
async def volunteer_directory(
    skill: Optional[str] = None,
    state: Optional[str] = None,
    admin: Principal = Depends(require_permission("volunteers.manage")),
    session: AsyncSession = Depends(get_session),
):
    """Who is available, for matching a task to people.

    Contact details are included because assigning work requires contacting
    someone -- and this endpoint sits behind `volunteers.manage`, which is the
    control on that.
    """
    stmt = (
        select(VolunteerProfile, Citizen)
        .join(Citizen, Citizen.id == VolunteerProfile.citizen_id)
        .where(VolunteerProfile.is_active.is_(True))
    )
    if state:
        stmt = stmt.where(VolunteerProfile.state_code == state.upper())

    rows = (await session.execute(stmt.limit(500))).all()
    return [
        {
            "profileId": profile.id,
            "displayName": citizen.display_name,
            "email": citizen.email,
            "skills": profile.skills,
            "languages": profile.languages,
            "hoursPerWeek": profile.hours_per_week,
            "state": profile.state_code,
            "city": profile.city,
            "verifiedHours": profile.verified_hours,
            "completedTasks": profile.completed_tasks,
        }
        for profile, citizen in rows
        if (not skill or skill in (profile.skills or []))
        and (admin.is_platform_wide() or (profile.state_code and admin.can_in_state(profile.state_code)))
    ]
