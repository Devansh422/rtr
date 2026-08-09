import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import { Section, EmptyState, Pill } from "@/components/platform/Primitives";
import ShareButtons from "@/components/ShareButtons";
import { getEvent } from "@/lib/platformApi";
import { cancelEventRegistration, listMyEvents, registerForEvent } from "@/lib/memberApi";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { useLocale } from "@/context/LocaleContext";
import { ArrowLeft, Calendar, MapPin, Video } from "lucide-react";

export default function EventDetail() {
  const { slug } = useParams();
  const { t } = useLocale();
  const { status: memberStatus } = useMemberAuth();
  const [event, setEvent] = useState(null);
  const [ticket, setTicket] = useState(null);
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(false);

  const loadTicket = () => {
    if (memberStatus !== "in") return;
    listMyEvents()
      .then((mine) => setTicket(mine.find((entry) => entry.slug === slug) ?? null))
      .catch(() => {});
  };

  useEffect(() => {
    getEvent(slug)
      .then((data) => {
        setEvent(data);
        setState("ready");
      })
      .catch(() => setState("missing"));
  }, [slug]);

  useEffect(loadTicket, [memberStatus, slug]);

  const register = async () => {
    setBusy(true);
    try {
      const result = await registerForEvent(slug);
      toast.success(
        result.already ? "You were already registered." : "Registered. Your ticket is below."
      );
      loadTicket();
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not register.");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    setBusy(true);
    try {
      await cancelEventRegistration(slug);
      setTicket(null);
      toast.success("Registration cancelled.");
    } catch (error) {
      toast.error(error?.response?.data?.detail ?? "Could not cancel.");
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
        <EmptyState title="Event not found" action={<LinkButton to="/events">All events</LinkButton>} />
      </Section>
    );
  }

  return (
    <div data-testid={`event-detail-${event.slug}`}>
      <Section>
        <div className="mx-auto grid w-full max-w-5xl gap-10 lg:grid-cols-[1fr_340px]">
          <div>
            <Link
              to="/events"
              className="inline-flex items-center gap-1.5 text-meta text-foreground/60 hover:text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              {t("events.title")}
            </Link>

            <div className="mt-6 flex flex-wrap gap-2">
              <Pill tone="muted">{event.kindLabel}</Pill>
              {event.status === "cancelled" ? <Pill tone="default">Cancelled</Pill> : null}
            </div>

            <h1 className="mt-4 font-heading text-title-2 font-semibold leading-[1.15] tracking-tight">
              {event.title}
            </h1>

            <div className="mt-5 space-y-2 text-body text-foreground/75">
              <p className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                {new Date(event.startsAt).toLocaleString()}
                {event.endsAt ? ` — ${new Date(event.endsAt).toLocaleTimeString()}` : ""}
              </p>
              <p className="flex items-start gap-2">
                {event.isOnline ? (
                  <>
                    <Video className="mt-0.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    Online
                  </>
                ) : (
                  <>
                    <MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    <span className="whitespace-pre-line">
                      {event.venue}
                      {event.address ? `\n${event.address}` : ""}
                    </span>
                  </>
                )}
              </p>
            </div>

            {event.cancellationReason ? (
              <p className="mt-6 rounded border border-destructive/30 bg-destructive/5 p-4 text-body text-foreground/80">
                {event.cancellationReason}
              </p>
            ) : null}

            <div className="mt-8 space-y-4">
              {event.description
                .split("\n\n")
                .filter(Boolean)
                .map((paragraph, index) => (
                  <p key={index} className="text-body leading-relaxed text-foreground/85">
                    {paragraph}
                  </p>
                ))}
            </div>

            {event.organiser?.name ? (
              <p className="mt-8 text-meta text-foreground/60">
                Organised by {event.organiser.name}
                {event.organiser.contact ? ` · ${event.organiser.contact}` : ""}
              </p>
            ) : null}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
            <div className="rounded border border-border bg-card p-6">
              {ticket ? (
                <>
                  <p className="text-label font-bold uppercase text-primary">{t("events.ticket")}</p>
                  <p className="mt-2 font-mono text-lead">{ticket.ticketCode}</p>
                  <p className="mt-1 text-meta text-foreground/60">{t("events.showQr")}</p>
                  {/* Rendered server-side as SVG: no QR library in the bundle, and it
                      prints sharply from a phone screenshot. */}
                  <img
                    src={ticket.qrUrl}
                    alt={`QR code for ticket ${ticket.ticketCode}`}
                    className="mt-4 w-full rounded border border-border bg-white p-3"
                  />
                  {ticket.attended ? (
                    <Pill tone="primary" className="mt-4">
                      Attendance recorded
                    </Pill>
                  ) : null}
                  {ticket.certificate ? (
                    <a
                      href={`/api/certificates/${ticket.certificate.code}/print`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mt-4 block text-meta text-primary underline-offset-4 hover:underline"
                    >
                      Your participation certificate
                    </a>
                  ) : null}
                  {ticket.meetingUrl ? (
                    <a
                      href={ticket.meetingUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mt-3 block text-meta text-primary underline-offset-4 hover:underline"
                    >
                      Joining link
                    </a>
                  ) : null}
                  {!ticket.attended ? (
                    <DynamicButton
                      variant="ghost"
                      size="sm"
                      className="mt-4 w-full"
                      onClick={cancel}
                      disabled={busy}
                    >
                      Cancel my registration
                    </DynamicButton>
                  ) : null}
                </>
              ) : memberStatus === "in" ? (
                <>
                  <p className="font-heading text-title-4 font-semibold tracking-tight">
                    {event.registrationCount} registered
                  </p>
                  {event.seatsLeft != null ? (
                    <p className="mt-1 text-meta text-foreground/60">
                      {event.seatsLeft} place{event.seatsLeft === 1 ? "" : "s"} left
                    </p>
                  ) : null}
                  <DynamicButton
                    className="mt-5 w-full"
                    onClick={register}
                    disabled={busy || event.status !== "published"}
                  >
                    {t("events.register")}
                  </DynamicButton>
                </>
              ) : (
                <>
                  <p className="text-body text-foreground/70">{t("common.signInPrompt")}</p>
                  <LinkButton to="/login" className="mt-4 w-full">
                    Sign in
                  </LinkButton>
                </>
              )}
            </div>

            <div className="rounded border border-border bg-card p-6">
              <p className="text-label font-bold uppercase text-muted-foreground">
                {t("common.share")}
              </p>
              <div className="mt-3">
                <ShareButtons title={`Join: ${event.title}`} />
              </div>
            </div>
          </aside>
        </div>
      </Section>
    </div>
  );
}
