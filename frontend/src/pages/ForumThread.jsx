import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { getThread } from "@/lib/platformApi";
import { replyToThread, upvote } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, ThumbsUp } from "lucide-react";

export default function ForumThread() {
  const { slug } = useParams();
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [thread, setThread] = useState(null);
  const [state, setState] = useState("loading");
  const [body, setBody] = useState("");
  const [parentId, setParentId] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    getThread(slug)
      .then((data) => {
        setThread(data);
        setState("ready");
      })
      .catch(() => setState("missing"));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const postReply = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await replyToThread(slug, { body, parent_id: parentId });
      setBody("");
      setParentId(null);
      toast.success(
        result.held
          ? "Your reply is waiting for a moderator. You can see it in your dashboard."
          : "Posted."
      );
      load();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      toast.error(
        detail?.flags?.[0]?.explanation ??
          (typeof detail === "string" ? detail : "Could not post that reply.")
      );
    } finally {
      setBusy(false);
    }
  };

  const vote = async (targetType, targetId) => {
    try {
      await upvote(targetType, targetId);
      load();
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not record that.");
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
          title="Discussion not found"
          body="It may have been removed by a moderator, or it may still be held for review."
          action={<LinkButton to="/forum">Back to the forum</LinkButton>}
        />
      </Section>
    );
  }

  const topLevel = thread.replies.filter((reply) => !reply.parentId);
  const childrenOf = (id) => thread.replies.filter((reply) => reply.parentId === id);

  return (
    <div data-testid={`thread-page-${thread.slug}`}>
      <Section>
        <div className="mx-auto w-full max-w-3xl">
          <Link
            to="/forum"
            className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {t("nav.forum")}
          </Link>

          <div className="mt-6 flex flex-wrap gap-2">
            <Pill tone="muted">{thread.category}</Pill>
            {thread.isLocked ? <Pill tone="muted">Closed to new replies</Pill> : null}
            {thread.state ? <Pill tone="muted">{thread.state}</Pill> : null}
          </div>

          <h1 className="mt-5 font-heading text-title-2 font-semibold leading-[1.15] tracking-tight">
            {thread.title}
          </h1>
          <p className="mt-3 text-meta text-foreground/60">
            {thread.author?.displayName ?? "A member"}
            {thread.createdAt ? ` · ${new Date(thread.createdAt).toLocaleDateString()}` : ""}
          </p>

          <div className="mt-6 space-y-4">
            {thread.body
              .split("\n\n")
              .filter(Boolean)
              .map((paragraph, index) => (
                <p key={index} className="text-body leading-relaxed text-foreground/85">
                  {paragraph}
                </p>
              ))}
          </div>

          <div className="mt-6 flex items-center gap-3">
            <DynamicButton
              variant="outline"
              size="sm"
              onClick={() => vote("thread", thread.id)}
              disabled={memberStatus !== "in"}
            >
              <ThumbsUp className="h-4 w-4" aria-hidden="true" />
              {t("forum.helpful")} ({thread.upvotes})
            </DynamicButton>
            <a
              href="/content-policy"
              className="text-meta text-foreground/60 underline-offset-4 hover:text-primary hover:underline"
            >
              {t("forum.readPolicy")}
            </a>
          </div>

          {/* Replies. One level of nesting only -- deeper trees become argument
              threads nobody reads to the bottom of. */}
          <div className="mt-12">
            <h2 className="font-heading text-title-4 font-semibold tracking-tight">
              {thread.replyCount} {thread.replyCount === 1 ? "reply" : "replies"}
            </h2>

            <ul className="mt-6 space-y-5">
              {topLevel.map((reply) => (
                <li key={reply.id}>
                  <div className="rounded border border-border bg-card p-5">
                    <p className="text-meta text-foreground/60">
                      {reply.author?.displayName ?? "A member"}
                      {reply.createdAt ? ` · ${new Date(reply.createdAt).toLocaleDateString()}` : ""}
                    </p>
                    <p className="mt-2 whitespace-pre-line text-body leading-relaxed text-foreground/85">
                      {reply.body}
                    </p>
                    <div className="mt-3 flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => vote("reply", reply.id)}
                        disabled={memberStatus !== "in"}
                        className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary disabled:opacity-50"
                      >
                        <ThumbsUp className="h-3.5 w-3.5" aria-hidden="true" />
                        {reply.upvotes}
                      </button>
                      {memberStatus === "in" && !thread.isLocked ? (
                        <button
                          type="button"
                          onClick={() => setParentId(reply.id)}
                          className="text-meta text-foreground/60 hover:text-primary"
                        >
                          {t("forum.reply")}
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {childrenOf(reply.id).length ? (
                    <ul className="ml-6 mt-3 space-y-3 border-l border-border pl-5">
                      {childrenOf(reply.id).map((child) => (
                        <li key={child.id} className="rounded border border-border bg-card/60 p-4">
                          <p className="text-meta text-foreground/60">
                            {child.author?.displayName ?? "A member"}
                          </p>
                          <p className="mt-1.5 whitespace-pre-line text-body text-foreground/85">
                            {child.body}
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>

            {thread.isLocked ? (
              <p className="mt-8 rounded border border-border bg-muted/40 p-5 text-body text-foreground/70">
                This discussion is closed to new replies.
              </p>
            ) : memberStatus === "in" ? (
              <form onSubmit={postReply} className="mt-8 rounded border border-border bg-card p-6">
                <Label htmlFor="reply-body">
                  {parentId ? "Your reply to that comment" : t("forum.reply")}
                </Label>
                <Textarea
                  id="reply-body"
                  required
                  rows={4}
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  placeholder="Criticise the decision, not the person."
                />
                <div className="mt-3 flex items-center gap-3">
                  <DynamicButton type="submit" disabled={busy}>
                    {busy ? "Posting..." : "Post reply"}
                  </DynamicButton>
                  {parentId ? (
                    <DynamicButton variant="ghost" type="button" onClick={() => setParentId(null)}>
                      Reply to the thread instead
                    </DynamicButton>
                  ) : null}
                </div>
              </form>
            ) : (
              <div className="mt-8 rounded border border-border bg-muted/40 p-6">
                <p className="text-body text-foreground/70">{t("common.signInPrompt")}</p>
                <LinkButton to="/login" className="mt-4">
                  Sign in
                </LinkButton>
              </div>
            )}
          </div>
        </div>
      </Section>
    </div>
  );
}
