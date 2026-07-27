import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Calendar, Clock, Loader2, User } from "lucide-react";
import { Reveal, MaskedLines } from "@/components/motion/Reveal";
import ShareButtons from "@/components/ShareButtons";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { useJoin } from "@/context/JoinContext";
import { getBlog, getBlogs } from "@/lib/api";
import { toParagraphs, formatDate } from "@/lib/content";

function Meta({ icon: Icon, children }) {
  if (!children) return null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {children}
    </span>
  );
}

export default function BlogPost() {
  const { id } = useParams();
  const { openJoin } = useJoin();
  const [post, setPost] = useState(null);
  const [related, setRelated] = useState([]);
  const [state, setState] = useState("loading"); // loading | ready | missing

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setPost(null);

    getBlog(id)
      .then((data) => {
        if (cancelled) return;
        setPost(data);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("missing");
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  // Related posts are chosen by shared category, excluding the current post.
  // Fetched separately so a failure here never blocks the article itself.
  useEffect(() => {
    if (!post) return;
    let cancelled = false;

    getBlogs()
      .then((all) => {
        if (cancelled) return;
        const sameCategory = all.filter((p) => p.id !== post.id && p.category === post.category);
        const others = all.filter((p) => p.id !== post.id && p.category !== post.category);
        setRelated([...sameCategory, ...others].slice(0, 3));
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [post]);

  if (state === "loading") {
    return (
      <div className="full-section-hero px-6 md:px-12" data-testid="blog-post-loading">
        <div className="mx-auto flex w-full max-w-3xl justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-secondary" aria-label="Loading article" />
        </div>
      </div>
    );
  }

  if (state === "missing" || !post) {
    return (
      <div className="full-section-hero px-6 md:px-12" data-testid="blog-post-missing">
        <div className="mx-auto w-full max-w-3xl text-center">
          <p className="text-label font-bold uppercase text-secondary">404</p>
          <h1 className="mt-4 font-heading text-title-1 font-extrabold">
            We couldn't find that article.
          </h1>
          <p className="mt-4 text-foreground/70">
            It may have been moved or renamed. The full library is still there.
          </p>
          <LinkButton to="/blog" variant="outline" className="mt-8">
            <ArrowLeft className="h-4 w-4" /> Back to all articles
          </LinkButton>
        </div>
      </div>
    );
  }

  const paragraphs = toParagraphs(post.content);

  return (
    <article data-testid="blog-post-page">
      {/* HEADER */}
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-3xl">
          <Link
            to="/blog"
            className="inline-flex items-center gap-2 text-label font-bold uppercase text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> All articles
          </Link>

          {post.category && (
            <p className="mt-8 text-label font-bold uppercase text-secondary">{post.category}</p>
          )}

          <h1 className="mt-4 font-heading text-title-1 font-extrabold leading-[0.95]">
            <MaskedLines lines={[post.title]} start={0.1} />
          </h1>

          <div className="tricolor-bar mt-8 h-1.5 w-24 rounded" aria-hidden="true" />

          {post.excerpt && <p className="mt-8 text-title-4 text-foreground/70">{post.excerpt}</p>}

          <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-label font-semibold uppercase text-muted-foreground">
            <Meta icon={User}>{post.author}</Meta>
            <Meta icon={Calendar}>{formatDate(post.date)}</Meta>
            <Meta icon={Clock}>{post.readTime}</Meta>
          </div>
        </div>
      </section>

      {/* COVER */}
      {post.image && (
        <section className="px-6 md:px-12">
          <div className="mx-auto w-full max-w-5xl">
            <div className="overflow-hidden rounded border border-border">
              <img
                src={post.image}
                alt=""
                className="h-[38vh] w-full object-cover md:h-[52vh]"
                loading="lazy"
              />
            </div>
          </div>
        </section>
      )}

      {/* BODY */}
      <section className="full-section px-6 md:px-12">
        <div className="mx-auto w-full max-w-3xl">
          {paragraphs.length > 0 ? (
            <div className="space-y-6">
              {paragraphs.map((para, i) => (
                <Reveal key={i} delay={i === 0 ? 0 : 0.05}>
                  {/*
                   * First paragraph is set larger as a lede. Content arrives as
                   * plain text from the admin panel, so paragraph breaks are the
                   * only structure available -- no markdown parsing involved.
                   */}
                  <p
                    className={
                      i === 0 ? "text-lead text-foreground/90" : "text-body text-foreground/80"
                    }
                  >
                    {para}
                  </p>
                </Reveal>
              ))}
            </div>
          ) : (
            <p className="text-foreground/60">This article has no body content yet.</p>
          )}

          <div className="mt-14 border-t border-border pt-8">
            <p className="mb-4 text-label font-bold uppercase text-muted-foreground">
              Share this article
            </p>
            <ShareButtons title={post.title} />
          </div>
        </div>
      </section>

      {/* RELATED + CTA */}
      <section className="full-section border-t border-border bg-muted/30 px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          {related.length > 0 && (
            <>
              <Reveal>
                <h2 className="font-heading text-title-1 font-extrabold">Keep reading.</h2>
              </Reveal>
              <div className="mt-10 grid gap-6 md:grid-cols-3">
                {related.map((r, i) => (
                  <Reveal key={r.id} delay={i * 0.08}>
                    <Link
                      to={`/blog/${r.id}`}
                      data-testid={`related-post-${r.id}`}
                      className="group flex h-full flex-col overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-1"
                    >
                      {r.image && (
                        <div className="h-40 overflow-hidden">
                          <img
                            src={r.image}
                            alt=""
                            loading="lazy"
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                          />
                        </div>
                      )}
                      <div className="flex flex-1 flex-col p-6">
                        <p className="text-label font-bold uppercase text-secondary">
                          {r.category}
                        </p>
                        <h3 className="mt-2 font-heading text-lead font-bold leading-snug">
                          {r.title}
                        </h3>
                        <p className="mt-2 line-clamp-3 flex-1 text-body text-foreground/70">
                          {r.excerpt}
                        </p>
                        <span className="mt-4 inline-flex items-center gap-1.5 text-label font-bold uppercase text-foreground">
                          Read <ArrowRight className="h-3.5 w-3.5" />
                        </span>
                      </div>
                    </Link>
                  </Reveal>
                ))}
              </div>
            </>
          )}

          <Reveal delay={0.1}>
            <div className="mt-16 rounded border border-border bg-card p-8 md:p-12">
              <h3 className="font-heading text-title-2 font-extrabold">
                Convinced? Add your name.
              </h3>
              <p className="mt-3 max-w-xl text-foreground/70">
                One nation, one demand: enact the Right to Recall Law in India. Joining takes under
                a minute and you'll get a supporter ID and certificate.
              </p>
              <DynamicButton
                onClick={openJoin}
                size="lg"
                className="mt-8"
                data-testid="blog-post-join"
              >
                Join the Movement <ArrowRight className="h-5 w-5" />
              </DynamicButton>
            </div>
          </Reveal>
        </div>
      </section>
    </article>
  );
}
