import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHero, Section, EmptyState, Pill } from "@/components/platform/Primitives";
import { getEvents } from "@/lib/platformApi";
import { Calendar, MapPin, Video } from "lucide-react";

export default function Events() {
  const [events, setEvents] = useState([]);
  const [past, setPast] = useState(false);

  useEffect(() => {
    getEvents({ past, limit: 40 }).then(setEvents);
  }, [past]);

  return (
    <div data-testid="events-page">
      <PageHero
        eyebrow="Events"
        lines={["Workshops, training,", "signature drives."]}
        lede="Register and you get a ticket with a QR code. A volunteer scans it at the door, and attendance earns a participation certificate you can verify afterwards."
      />

      <Section>
        <Tabs value={past ? "past" : "upcoming"} onValueChange={(v) => setPast(v === "past")}>
          <TabsList>
            <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
            <TabsTrigger value="past">Past</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="mt-8">
          {events.length === 0 ? (
            <EmptyState
              title={past ? "No past events on record" : "Nothing scheduled yet"}
              body="Events are organised state by state. If you would like to run one where you live, the volunteer portal is the place to start."
            />
          ) : (
            <StaggerGroup className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {events.map((event) => (
                <StaggerItem key={event.id}>
                  <Link
                    to={event.url}
                    className="group flex h-full flex-col rounded border border-border bg-card p-5 hover:border-primary/40"
                    data-testid={`event-${event.slug}`}
                  >
                    <div className="flex flex-wrap gap-2">
                      <Pill tone="muted">{event.kindLabel}</Pill>
                      {event.status === "cancelled" ? <Pill tone="default">Cancelled</Pill> : null}
                      {event.state ? <Pill tone="muted">{event.state}</Pill> : null}
                    </div>
                    <h3 className="mt-3 font-heading text-lead font-semibold leading-snug tracking-tight group-hover:text-primary">
                      {event.title}
                    </h3>
                    <p className="mt-2 flex-1 text-meta text-foreground/70">{event.description}</p>
                    <div className="mt-4 space-y-1.5 text-meta text-foreground/60">
                      <p className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
                        {new Date(event.startsAt).toLocaleString()}
                      </p>
                      <p className="flex items-center gap-1.5">
                        {event.isOnline ? (
                          <>
                            <Video className="h-3.5 w-3.5" aria-hidden="true" />
                            Online
                          </>
                        ) : (
                          <>
                            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                            {event.venue}
                          </>
                        )}
                      </p>
                      {event.seatsLeft != null ? (
                        <p>{event.seatsLeft} place{event.seatsLeft === 1 ? "" : "s"} left</p>
                      ) : null}
                    </div>
                  </Link>
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>
      </Section>
    </div>
  );
}
