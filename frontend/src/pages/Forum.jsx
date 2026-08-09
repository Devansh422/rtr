import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { PageHero, Section, SectionHeading, EmptyState, Pill } from "@/components/platform/Primitives";
import { getForumCategories, getThreads } from "@/lib/platformApi";
import { createThread } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { MessageSquare, Shield } from "lucide-react";

export default function Forum() {
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const [categories, setCategories] = useState([]);
  const [threads, setThreads] = useState({ items: [], total: 0 });
  const [sort, setSort] = useState("active");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", category_key: "" });

  useEffect(() => {
    getForumCategories().then(setCategories);
  }, []);

  useEffect(() => {
    getThreads({ category: category || undefined, sort, limit: 50 }).then(setThreads);
  }, [category, sort]);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await createThread(form);
      toast.success(
        result.held
          ? result.message
          : "Posted. Thanks for keeping it about conduct and policy.",
        { duration: 12000 }
      );
      setShowForm(false);
      setForm({ title: "", body: "", category_key: "" });
      getThreads({ category: category || undefined, sort, limit: 50 }).then(setThreads);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      toast.error(
        detail?.flags?.[0]?.explanation ??
          (typeof detail === "string" ? detail : "Could not post that.")
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="forum-page">
      <PageHero eyebrow="Discuss" lines={["Argue about conduct.", "Never about", "a community."]} lede={t("forum.lede")}>
        <div className="flex flex-wrap gap-3">
          {memberStatus === "in" ? (
            <DynamicButton size="lg" onClick={() => setShowForm((v) => !v)}>
              <MessageSquare className="h-5 w-5" aria-hidden="true" />
              {t("forum.newThread")}
            </DynamicButton>
          ) : (
            <LinkButton to="/login" size="lg">
              Sign in to take part
            </LinkButton>
          )}
          <LinkButton to="/content-policy" variant="outline" size="lg">
            <Shield className="h-5 w-5" aria-hidden="true" />
            {t("forum.readPolicy")}
          </LinkButton>
        </div>
      </PageHero>

      {showForm ? (
        <Section>
          <form onSubmit={submit} className="mx-auto max-w-2xl rounded border border-border bg-card p-7">
            <h2 className="font-heading text-title-3 font-semibold tracking-tight">
              {t("forum.newThread")}
            </h2>
            <p className="mt-2 text-meta text-foreground/60">
              Posts that appear to campaign for a party, or to blame a community, are held for a
              moderator rather than deleted &mdash; you will see the reason and can rewrite.
            </p>
            <div className="mt-6 space-y-4">
              <div>
                <Label htmlFor="thread-category">Category</Label>
                <Select
                  value={form.category_key}
                  onValueChange={(v) => setForm((p) => ({ ...p, category_key: v }))}
                >
                  <SelectTrigger id="thread-category">
                    <SelectValue placeholder="Choose a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((c) => (
                      <SelectItem key={c.key} value={c.key}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="thread-title">Title</Label>
                <Input
                  id="thread-title"
                  required
                  minLength={12}
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                />
              </div>
              <div>
                <Label htmlFor="thread-body">Your post</Label>
                <Textarea
                  id="thread-body"
                  required
                  minLength={30}
                  rows={7}
                  value={form.body}
                  onChange={(e) => setForm((p) => ({ ...p, body: e.target.value }))}
                />
              </div>
              <DynamicButton type="submit" disabled={busy} className="w-full">
                {busy ? "Posting..." : "Post"}
              </DynamicButton>
            </div>
          </form>
        </Section>
      ) : null}

      <Section testId="forum-categories">
        <SectionHeading title="Categories" />
        <StaggerGroup className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((c) => (
            <StaggerItem key={c.key}>
              <button
                type="button"
                onClick={() => setParams(category === c.key ? {} : { category: c.key })}
                className={`w-full rounded border p-5 text-left transition-colors ${
                  category === c.key
                    ? "border-primary bg-primary/10"
                    : "border-border bg-card hover:border-primary/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-heading text-lead font-semibold tracking-tight">{c.name}</p>
                  <Pill tone="muted">{c.threadCount}</Pill>
                </div>
                <p className="mt-2 text-meta text-foreground/70">{c.description}</p>
                {c.minReputation ? (
                  <p className="mt-2 text-meta text-foreground/50">
                    Needs {c.minReputation} contribution points to post
                  </p>
                ) : null}
              </button>
            </StaggerItem>
          ))}
        </StaggerGroup>
      </Section>

      <Section muted testId="forum-threads">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <SectionHeading
            title={category ? categories.find((c) => c.key === category)?.name ?? "Discussions" : "All discussions"}
            lede={`${threads.total} thread${threads.total === 1 ? "" : "s"}`}
          />
          <Tabs value={sort} onValueChange={setSort}>
            <TabsList>
              <TabsTrigger value="active">Active</TabsTrigger>
              <TabsTrigger value="new">New</TabsTrigger>
              <TabsTrigger value="top">Useful</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="mt-8">
          {threads.items.length === 0 ? (
            <EmptyState
              title="No discussions here yet"
              body="Be the first. Posts about what a representative did, backed by a source, are the most useful thing you can add."
            />
          ) : (
            <div className="grid gap-3">
              {threads.items.map((thread) => (
                <Link
                  key={thread.id}
                  to={thread.url}
                  className="flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-card p-5 hover:border-primary/40"
                  data-testid={`thread-${thread.slug}`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {thread.isPinned ? <Pill tone="secondary">Pinned</Pill> : null}
                      {thread.isLocked ? <Pill tone="muted">Closed</Pill> : null}
                      <Pill tone="muted">{thread.category}</Pill>
                    </div>
                    <p className="mt-2 font-heading text-lead font-semibold tracking-tight">
                      {thread.title}
                    </p>
                    <p className="mt-1 text-meta text-foreground/60">
                      {thread.author?.displayName ?? "A member"}
                      {thread.author?.reputation ? ` · ${thread.author.reputation} pts` : ""}
                    </p>
                  </div>
                  <div className="text-right text-meta text-foreground/60">
                    <p>{thread.replyCount} replies</p>
                    <p>{thread.upvotes} found useful</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </Section>
    </div>
  );
}
