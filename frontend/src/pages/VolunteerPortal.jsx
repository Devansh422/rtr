import { useEffect, useState } from "react";
import { toast } from "sonner";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
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
import { getStates, getVolunteerSkills, getVolunteerTasks } from "@/lib/platformApi";
import {
  claimTask,
  getMyVolunteerDashboard,
  requestVolunteerCertificate,
  saveVolunteerProfile,
  submitTaskWork,
} from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { Award, Clock } from "lucide-react";

const ALL = "__all__";

/*
 * Volunteer Portal: the task board, plus the signed-in member's own assignments.
 *
 * Hours claimed and hours verified are shown separately throughout, matching the
 * data model. A certificate is issued on VERIFIED hours only, which is why the
 * difference is visible rather than collapsed into one number.
 */
export default function VolunteerPortal() {
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [skills, setSkills] = useState([]);
  const [states, setStates] = useState([]);
  const [tasks, setTasks] = useState({ items: [], total: 0 });
  const [skillFilter, setSkillFilter] = useState(ALL);
  const [dashboard, setDashboard] = useState(null);
  const [profileForm, setProfileForm] = useState({ skills: [], state_code: "", city: "", hours_per_week: "" });
  const [submission, setSubmission] = useState({ id: null, note: "", url: "", hours: "" });

  const loadDashboard = () => {
    if (memberStatus !== "in") return;
    getMyVolunteerDashboard()
      .then((data) => {
        setDashboard(data);
        if (data.hasProfile) {
          setProfileForm({
            skills: data.profile.skills ?? [],
            state_code: data.profile.state ?? "",
            city: data.profile.city ?? "",
            hours_per_week: data.profile.hoursPerWeek ? String(data.profile.hoursPerWeek) : "",
          });
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    getVolunteerSkills().then(setSkills);
    getStates().then(setStates);
  }, []);

  useEffect(() => {
    getVolunteerTasks({ skill: skillFilter === ALL ? undefined : skillFilter, limit: 60 }).then(setTasks);
  }, [skillFilter]);

  useEffect(loadDashboard, [memberStatus]);

  const saveProfile = async (event) => {
    event.preventDefault();
    try {
      await saveVolunteerProfile({
        skills: profileForm.skills,
        state_code: profileForm.state_code || null,
        city: profileForm.city,
        hours_per_week: profileForm.hours_per_week ? Number(profileForm.hours_per_week) : null,
        languages: [],
        bio: "",
      });
      toast.success("Saved. Tasks matching your skills are highlighted on the board.");
      loadDashboard();
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not save that.");
    }
  };

  const take = async (slug) => {
    try {
      const result = await claimTask(slug);
      toast.success(result.message, { duration: 9000 });
      loadDashboard();
      getVolunteerTasks({ skill: skillFilter === ALL ? undefined : skillFilter, limit: 60 }).then(setTasks);
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not take that task.");
    }
  };

  const submitWork = async (event) => {
    event.preventDefault();
    try {
      await submitTaskWork(submission.id, {
        note: submission.note,
        url: submission.url,
        hours_claimed: Number(submission.hours),
      });
      toast.success("Submitted. A volunteer manager confirms the hours before they count.");
      setSubmission({ id: null, note: "", url: "", hours: "" });
      loadDashboard();
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not submit that.");
    }
  };

  const getCertificate = async () => {
    try {
      const certificate = await requestVolunteerCertificate();
      toast.success(`Certificate issued: ${certificate.code}`, { duration: 12000 });
      loadDashboard();
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Not eligible yet.");
    }
  };

  return (
    <div data-testid="volunteer-portal">
      <PageHero
        eyebrow="Volunteer portal"
        lines={["Real work,", "with verified hours."]}
        lede={t("volunteer.lede")}
      >
        {memberStatus !== "in" ? (
          <LinkButton to="/login" size="lg">
            Sign in to take a task
          </LinkButton>
        ) : null}
      </PageHero>

      {/* The member's own state, first, when signed in. */}
      {memberStatus === "in" && dashboard ? (
        <Section testId="volunteer-dashboard">
          {dashboard.hasProfile ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label={t("volunteer.verifiedHours")}
                  value={dashboard.profile.verifiedHours}
                  tone="primary"
                />
                <StatTile label="Tasks completed" value={dashboard.profile.completedTasks} />
                <StatTile
                  label="Certificate at"
                  value={`${dashboard.certificate.threshold}h`}
                  sub={
                    dashboard.certificate.eligible
                      ? "You qualify"
                      : `${dashboard.certificate.hoursNeeded} more hours`
                  }
                />
                <div className="rounded border border-border bg-card p-5">
                  <p className="text-label font-bold uppercase text-muted-foreground">
                    {t("academy.certificate")}
                  </p>
                  {dashboard.certificate.issued.length ? (
                    <p className="mt-2 font-mono text-body">
                      {dashboard.certificate.issued[0].code}
                    </p>
                  ) : (
                    <DynamicButton
                      size="sm"
                      className="mt-3"
                      disabled={!dashboard.certificate.eligible}
                      onClick={getCertificate}
                    >
                      <Award className="h-4 w-4" aria-hidden="true" />
                      Get it
                    </DynamicButton>
                  )}
                </div>
              </div>

              {dashboard.assignments.length ? (
                <div className="mt-10">
                  <SectionHeading title="Your tasks" />
                  <div className="mt-6 space-y-3">
                    {dashboard.assignments.map((assignment) => (
                      <div key={assignment.id} className="rounded border border-border bg-card p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="font-heading text-lead font-semibold tracking-tight">
                              {assignment.task?.title}
                            </p>
                            <p className="mt-1 text-meta text-foreground/60">
                              {assignment.task?.skillLabel} &middot; est.{" "}
                              {assignment.task?.estimatedHours}h
                            </p>
                          </div>
                          <Pill tone={assignment.status === "verified" ? "primary" : "muted"}>
                            {assignment.statusLabel}
                          </Pill>
                        </div>

                        {assignment.reviewNote ? (
                          <p className="mt-3 rounded border border-border bg-muted/40 p-3 text-meta text-foreground/80">
                            <strong className="font-semibold">Manager: </strong>
                            {assignment.reviewNote}
                          </p>
                        ) : null}

                        {assignment.status === "verified" ? (
                          <p className="mt-3 text-meta text-foreground/70">
                            {assignment.hoursVerified}h verified of {assignment.hoursClaimed}h claimed
                          </p>
                        ) : assignment.status === "submitted" ? (
                          <p className="mt-3 text-meta text-foreground/60">
                            {assignment.hoursClaimed}h claimed, waiting for verification
                          </p>
                        ) : submission.id === assignment.id ? (
                          <form onSubmit={submitWork} className="mt-4 space-y-3">
                            <div>
                              <Label htmlFor={`note-${assignment.id}`}>What you did</Label>
                              <Textarea
                                id={`note-${assignment.id}`}
                                required
                                rows={3}
                                value={submission.note}
                                onChange={(e) =>
                                  setSubmission((p) => ({ ...p, note: e.target.value }))
                                }
                              />
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                              <div>
                                <Label htmlFor={`url-${assignment.id}`}>Link to the work</Label>
                                <Input
                                  id={`url-${assignment.id}`}
                                  value={submission.url}
                                  onChange={(e) =>
                                    setSubmission((p) => ({ ...p, url: e.target.value }))
                                  }
                                />
                              </div>
                              <div>
                                <Label htmlFor={`hours-${assignment.id}`}>Hours spent</Label>
                                <Input
                                  id={`hours-${assignment.id}`}
                                  type="number"
                                  step="0.5"
                                  min="0.5"
                                  required
                                  value={submission.hours}
                                  onChange={(e) =>
                                    setSubmission((p) => ({ ...p, hours: e.target.value }))
                                  }
                                />
                              </div>
                            </div>
                            <DynamicButton type="submit" size="sm">
                              {t("volunteer.submit")}
                            </DynamicButton>
                          </form>
                        ) : (
                          <DynamicButton
                            size="sm"
                            variant="outline"
                            className="mt-3"
                            onClick={() => setSubmission({ id: assignment.id, note: "", url: "", hours: "" })}
                          >
                            {t("volunteer.submit")}
                          </DynamicButton>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : null}

          {/* Profile form. Also the enrolment step -- there is no separate signup. */}
          <form onSubmit={saveProfile} className="mt-10 rounded border border-border bg-card p-7">
            <h2 className="font-heading text-title-4 font-semibold tracking-tight">
              {dashboard.hasProfile ? "Update what you can help with" : "Tell us what you can help with"}
            </h2>
            <div className="mt-5 space-y-5">
              <div>
                <Label>Skills</Label>
                <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {skills.map((skill) => (
                    <label
                      key={skill.key}
                      htmlFor={`skill-${skill.key}`}
                      className="flex cursor-pointer items-start gap-2 text-meta"
                    >
                      <Checkbox
                        id={`skill-${skill.key}`}
                        checked={profileForm.skills.includes(skill.key)}
                        onCheckedChange={(checked) =>
                          setProfileForm((prev) => ({
                            ...prev,
                            skills: checked
                              ? [...prev.skills, skill.key]
                              : prev.skills.filter((s) => s !== skill.key),
                          }))
                        }
                      />
                      {skill.label}
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <Label htmlFor="volunteer-state">State</Label>
                  <Select
                    value={profileForm.state_code}
                    onValueChange={(v) => setProfileForm((p) => ({ ...p, state_code: v }))}
                  >
                    <SelectTrigger id="volunteer-state">
                      <SelectValue placeholder="Choose" />
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
                <div>
                  <Label htmlFor="volunteer-city">City or town</Label>
                  <Input
                    id="volunteer-city"
                    value={profileForm.city}
                    onChange={(e) => setProfileForm((p) => ({ ...p, city: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="volunteer-hours">Hours a week</Label>
                  <Input
                    id="volunteer-hours"
                    type="number"
                    min="1"
                    max="60"
                    value={profileForm.hours_per_week}
                    onChange={(e) => setProfileForm((p) => ({ ...p, hours_per_week: e.target.value }))}
                  />
                </div>
              </div>

              <DynamicButton type="submit">Save</DynamicButton>
            </div>
          </form>
        </Section>
      ) : null}

      <Section muted testId="task-board">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <SectionHeading title={t("volunteer.title")} lede={`${tasks.total} open`} />
          <Select value={skillFilter} onValueChange={setSkillFilter}>
            <SelectTrigger className="w-64" aria-label="Filter tasks by skill">
              <SelectValue placeholder="All skills" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All skills</SelectItem>
              {skills.map((skill) => (
                <SelectItem key={skill.key} value={skill.key}>
                  {skill.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="mt-8">
          {tasks.items.length === 0 ? (
            <EmptyState
              title="No open tasks right now"
              body="Tasks are posted with a defined outcome and an estimate, so that verifying the work afterwards is possible. Check back, or tell us what you can do above."
            />
          ) : (
            <StaggerGroup className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {tasks.items.map((task) => (
                <StaggerItem key={task.id}>
                  <article className="flex h-full flex-col rounded border border-border bg-card p-5">
                    <div className="flex flex-wrap gap-2">
                      <Pill tone="muted">{task.skillLabel}</Pill>
                      {task.isRemote ? <Pill tone="muted">Remote</Pill> : null}
                      {task.state ? <Pill tone="muted">{task.state}</Pill> : null}
                    </div>
                    <h3 className="mt-3 font-heading text-lead font-semibold leading-snug tracking-tight">
                      {task.title}
                    </h3>
                    <p className="mt-2 flex-1 text-meta text-foreground/70">{task.description}</p>
                    {task.acceptanceCriteria ? (
                      <p className="mt-3 rounded border border-border bg-muted/30 p-3 text-meta text-foreground/70">
                        <strong className="font-semibold">Done means: </strong>
                        {task.acceptanceCriteria}
                      </p>
                    ) : null}
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-1.5 text-meta text-foreground/60">
                        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                        ~{task.estimatedHours}h &middot; {task.slotsLeft} slot
                        {task.slotsLeft === 1 ? "" : "s"} left
                      </span>
                      {memberStatus === "in" ? (
                        <DynamicButton size="sm" onClick={() => take(task.slug)}>
                          {t("volunteer.claim")}
                        </DynamicButton>
                      ) : (
                        <LinkButton to="/login" size="sm" variant="outline">
                          Sign in
                        </LinkButton>
                      )}
                    </div>
                  </article>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>
    </div>
  );
}
