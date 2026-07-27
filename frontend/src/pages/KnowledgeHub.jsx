import { useEffect, useState } from "react";
import { Reveal, MaskedLines, StaggerGroup, StaggerItem } from "@/components/motion/Reveal";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import DynamicButton from "@/components/DynamicButton";
import LinkButton from "@/components/LinkButton";
import Eyebrow from "@/components/Eyebrow";
import { getFaq, getResources, getJurisdictions, getMyths, getBlogs } from "@/lib/api";
import { toast } from "sonner";
import {
  Vote,
  ScrollText,
  RefreshCw,
  Globe,
  X,
  Check,
  FileText,
  Wrench,
  BookOpen,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";

const STEPS = [
  {
    icon: Vote,
    title: "Elect",
    text: "Citizens choose representatives through free and fair elections.",
  },
  {
    icon: ScrollText,
    title: "Review",
    text: "Track performance transparently using public records and RTI tools.",
  },
  {
    icon: RefreshCw,
    title: "Recall",
    text: "Where the constitution allows, citizens can responsibly initiate recall.",
  },
];

/*
 * The generic shape of a recall procedure.
 *
 * Deliberately written without thresholds, timeframes, article numbers or place
 * names: those differ in every jurisdiction that has recall, and the CMS-fed
 * jurisdiction cards further down are where any specifics belong. This list
 * exists so a reader understands the sequence, not so they can quote figures.
 */
const PROCESS = [
  {
    title: "Grounds and initiation",
    text: "A recall begins with constituents formally stating that they want their representative reviewed. Some systems require specific grounds to be alleged and evidenced; others treat a loss of confidence as reason enough on its own.",
  },
  {
    title: "Petition and threshold",
    text: "Support is then gathered from voters in the same constituency, usually as signatures or attestations. A petition has to clear a minimum level of support, within a limited window, before anything further can happen. Both the level and the window vary by jurisdiction.",
  },
  {
    title: "Verification",
    text: "An electoral authority independent of the parties involved checks the petition: that signatories are real people, registered in that constituency, and signed freely. Petitions that fail verification end at this stage, which is the point of having the stage at all.",
  },
  {
    title: "The vote",
    text: "If the petition stands, the question goes to the constituency as a whole rather than to the petitioners. Designs differ on what is being voted on: in some, voters decide only whether to remove; in others, removal and the choice of a successor are settled together.",
  },
  {
    title: "Outcome and succession",
    text: "If removal carries, the seat is filled by whatever route the law already prescribes for a vacancy. If it does not, the representative continues in office, typically with a protected period before a fresh attempt can be started.",
  },
];

/*
 * Safeguards, again as categories rather than numbers. Every real drafting
 * argument is about where these dials get set, so naming the dials is the
 * honest thing this page can do.
 */
const SAFEGUARDS = [
  "A waiting period after an election, so a recall cannot be used to relitigate the result itself.",
  "A support threshold high enough that a petition proves broad discontent rather than a motivated faction.",
  "Verification by an electoral authority that is independent of both the petitioners and the representative.",
  "Limits on how often a recall may be attempted against the same person in the same term.",
  "A minimum participation or majority requirement, so a thinly attended vote cannot unseat someone many more people elected.",
  "Cost, deposit or penalty rules that discourage frivolous, repeated or malicious filings.",
];

const CASE_FOR = [
  {
    title: "Accountability does not pause between elections",
    text: "A term of office runs for years. Recall gives voters a defined, lawful route to act on a serious breakdown of trust instead of waiting for the calendar to come around.",
  },
  {
    title: "The incentives matter more than the removals",
    text: "The value of recall lies less in how often it is used than in how representatives behave when it exists. A standing possibility of review tends to keep constituents in the picture.",
  },
  {
    title: "It fills a gap other remedies leave open",
    text: "Party discipline, the courts and the press each address some kinds of failure. None of them reliably answers the plainest case: a representative who has simply stopped representing.",
  },
  {
    title: "It gives citizens something to do",
    text: "Petitioning, verifying and voting are civic acts with a defined outcome. They turn diffuse public frustration into a procedure, which is generally healthier than leaving it nowhere to go.",
  },
  {
    title: "It is not an imported idea",
    text: "Recall provisions already appear in Indian law at the local level in a number of states. The live question is therefore about extension and design, not about inventing something foreign.",
  },
];

const OBJECTIONS = [
  {
    title: "Permanent campaigning",
    text: "If a recall is cheap to start, representatives may govern with one eye on the next petition. Decisions that are necessary but unpopular in the short term become harder to take.",
  },
  {
    title: "Cost and administrative capacity",
    text: "Verification and a fresh vote consume real public money and real institutional capacity, drawn from the same electoral machinery that has to run scheduled elections.",
  },
  {
    title: "Advantage to the organised and well funded",
    text: "A process that rewards whoever can mobilise support fastest can favour organised money and established networks over the ordinary constituents it is meant to empower.",
  },
  {
    title: "Exposure for representatives from marginalised groups",
    text: "Members from minority or historically excluded backgrounds may face recall attempts driven by prejudice rather than performance. A design that ignores this risk will produce that outcome.",
  },
  {
    title: "Verification is genuinely hard at scale",
    text: "Establishing that support is real, freely given and from the right constituency is difficult and contestable. A recall process that voters do not trust is worse than no recall process.",
  },
  {
    title: "It may not reach the underlying problem",
    text: "Many complaints about representatives trace back to candidate selection, party control and campaign finance. Recall acts on the symptom, and should not be sold as a cure for all of it.",
  },
];

/*
 * The kinds of evidence the movement works from. Named as categories so the
 * CMS-fed articles below can carry the actual citations.
 */
const EVIDENCE = [
  {
    title: "Comparative law and practice",
    text: "How places that already use recall have written it, and what happened afterwards: how often it is triggered, how often it succeeds, and what it did to the way representatives behaved.",
  },
  {
    title: "Indian local-government experience",
    text: "Recall exists in local-government law in some Indian states, largely for municipal and panchayat representatives. That experience is the closest thing to a domestic evidence base and deserves close reading.",
  },
  {
    title: "Public-record and RTI analysis",
    text: "Attendance, questions asked, funds allotted and funds spent are all matters of public record. Accountability arguments are stronger when they rest on documents anyone can request and check.",
  },
  {
    title: "Scholarship and civil-society work",
    text: "Constitutional and political-science writing on accountability, representation and electoral design, including the arguments against recall, which we read as carefully as the arguments for it.",
  },
];

const typeIcon = { Document: FileText, Toolkit: Wrench, Research: BookOpen };

/*
 * The in-page nav. This is the page's only navigation rail: a second sticky
 * "on this page" column would duplicate it, and would have to negotiate with
 * both the fixed navbar and the scroll-progress bar for the same screen edge.
 * One list, in page order, is easier to trust.
 */
const SectionNav = () => (
  <div className="flex flex-wrap gap-2" data-testid="knowledge-nav">
    {[
      ["what", "What is RTR"],
      ["jurisdictions", "Around the World"],
      ["arguments", "For & Against"],
      ["myths", "Myth vs Fact"],
      ["faq", "FAQ"],
      ["research", "Research"],
      ["downloads", "Downloads"],
    ].map(([id, label]) => (
      <a
        key={id}
        href={`#${id}`}
        className="rounded border border-border bg-card px-4 py-2 text-body font-semibold text-foreground/70 transition-colors hover:bg-muted"
      >
        {label}
      </a>
    ))}
  </div>
);

export default function KnowledgeHub() {
  const [faq, setFaq] = useState([]);
  const [resources, setResources] = useState([]);
  const [jurisdictions, setJurisdictions] = useState([]);
  const [myths, setMyths] = useState([]);
  const [research, setResearch] = useState([]);

  useEffect(() => {
    getFaq()
      .then(setFaq)
      .catch(() => {});
    getResources()
      .then(setResources)
      .catch(() => {});
    getJurisdictions()
      .then(setJurisdictions)
      .catch(() => {});
    getMyths()
      .then(setMyths)
      .catch(() => {});
    getBlogs()
      .then((b) =>
        setResearch(
          b.filter((x) => ["Explainer", "Resources", "Basics"].includes(x.category)).slice(0, 3)
        )
      )
      .catch(() => {});
  }, []);

  const handleDownload = async (r) => {
    // The resource file field is not yet wired to real storage, so this
    // acknowledges the request rather than fetching bytes.
    await new Promise((resolve) => setTimeout(resolve, 600));
    toast.success(`${r.title} is coming to your inbox soon!`);
  };

  return (
    <div data-testid="knowledge-page">
      <section className="full-section-hero px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          <div className="mb-6 h-1.5 w-24 rounded tricolor-bar" aria-hidden="true" />
          <Eyebrow>Knowledge Hub</Eyebrow>
          <h1 className="mt-4 font-heading text-title-1 font-semibold">
            <MaskedLines lines={["Learn it.", "Question it.", "Share it."]} />
          </h1>
          <p className="mt-8 max-w-2xl text-lead text-foreground/70">
            Everything you need to understand the Right to Recall, explained simply, backed by
            facts, free to share. Read it straight through and you will finish knowing what recall
            is, how it works, what already exists in India, and what the strongest objections to it
            are.
          </p>
          <div className="mt-8">
            <SectionNav />
          </div>
        </div>
      </section>

      {/*
       * WHAT IS RTR.
       *
       * Content-height, not full-section: this is now the longest reading block
       * on the page (lede, two prose paragraphs, three cards, a five step
       * sequence and a safeguards list), so pinning it to 100vh would only push
       * the fold into the middle of a paragraph.
       *
       * The prose column is capped at max-w-2xl for line length. The card grid
       * and nothing else is allowed the full max-w-7xl.
       */}
      <section id="what" className="scroll-mt-28 px-6 py-20 md:px-12 md:py-28">
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="max-w-2xl">
              <h2 className="font-heading text-title-1 font-semibold">What is Right to Recall?</h2>
              <p className="mt-gap-title text-lead text-foreground/70">
                Right to Recall is a democratic mechanism that lets citizens formally review and,
                where the law allows, remove an elected representative before their term ends. It
                works as an accountability tool{" "}
                <span className="font-semibold text-foreground">between</span> elections, a feedback
                loop for democracy.
              </p>
              <div className="mt-6 space-y-4 text-body text-foreground/70">
                <p>
                  The principle underneath it is simple. An election is a single moment of consent,
                  given once and then held for years. Everything a representative does after polling
                  day rests on a mandate the voters can no longer speak to. Recall treats that
                  consent as something continuing rather than something spent: if it collapses in a
                  serious and demonstrable way, the people who granted it get a lawful route to
                  revisit the question.
                </p>
                <p>
                  It is worth being clear about what recall is not. It is not a way of overturning a
                  result because your side lost, and it is not a substitute for elections, courts, a
                  free press or an active opposition. It is one narrow instrument aimed at one
                  narrow failure: a representative who has stopped representing, in a way their
                  constituents can evidence and are willing to put their names to. Everything else
                  in a recall law exists to keep it to that.
                </p>
              </div>
            </div>
          </Reveal>

          <StaggerGroup className="mt-gap-block grid gap-6 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <StaggerItem key={s.title}>
                <div className="h-full rounded border border-border bg-card p-8">
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded ${["bg-primary", "bg-secondary", "bg-chakra"][i]}`}
                  >
                    <s.icon
                      className={`h-6 w-6 ${i === 0 ? "text-primary-foreground" : "text-white"}`}
                    />
                  </div>
                  <h3 className="mt-5 font-heading text-title-4 font-semibold">
                    {i + 1}. {s.title}
                  </h3>
                  <p className="mt-2 text-body text-foreground/70">{s.text}</p>
                </div>
              </StaggerItem>
            ))}
          </StaggerGroup>

          {/*
           * The procedure is a sequence, so it reads as a numbered list divided
           * by hairlines rather than as five more cards. Cards would imply the
           * steps are independent and interchangeable, which they are not.
           */}
          <div className="mt-gap-section max-w-2xl">
            <Reveal>
              <Eyebrow>The mechanism</Eyebrow>
              <h3 className="mt-gap-title font-heading text-title-2 font-semibold">
                How a recall process usually works.
              </h3>
              <p className="mt-4 text-lead text-foreground/70">
                Recall laws differ a great deal in their detail, but almost all of them move through
                the same five stages. The thresholds and timeframes attached to each stage are where
                jurisdictions part company.
              </p>
            </Reveal>
            <Reveal delay={0.1}>
              <ol className="mt-8 divide-y divide-border border-y border-border">
                {PROCESS.map((p, i) => (
                  <li key={p.title} className="flex gap-5 py-6">
                    <span
                      className="font-heading text-title-4 font-semibold text-primary"
                      aria-hidden="true"
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h4 className="font-heading text-title-4 font-semibold">{p.title}</h4>
                      <p className="mt-2 text-body text-foreground/70">{p.text}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Reveal>
          </div>

          <div className="mt-gap-section max-w-2xl">
            <Reveal>
              <Eyebrow>Guardrails</Eyebrow>
              <h3 className="mt-gap-title font-heading text-title-2 font-semibold">
                What stops it being misused.
              </h3>
              <div className="mt-4 space-y-4 text-body text-foreground/70">
                <p>
                  A well drafted recall law spends most of its length on restraint rather than on
                  removal. That is the correct emphasis: an instrument that is trivially easy to
                  trigger would be used as a routine tactic, and would quickly stop meaning
                  anything. The safeguards below recur, in one form or another, almost everywhere
                  recall is practised.
                </p>
              </div>
              <ul className="mt-6 space-y-3 border-l border-border pl-5 text-body text-foreground/70">
                {SAFEGUARDS.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
              <p className="mt-6 text-body text-foreground/70">
                The exact settings, how long the protected period runs, how much support a petition
                needs, what counts as sufficient participation in the vote, differ from place to
                place. They are also the entire substance of any serious drafting debate, which is
                why we would rather point you at primary sources than quote a number at you here.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/*
       * JURISDICTIONS. Content-height: framing prose plus a variable-length card
       * grid, so a fixed 100vh would either crop or strand it.
       */}
      <section
        id="jurisdictions"
        className="scroll-mt-28 border-y border-border bg-muted/30 px-6 py-20 md:px-12 md:py-28"
      >
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="max-w-2xl">
              <Eyebrow>Around the world</Eyebrow>
              <h2 className="mt-gap-title font-heading text-title-1 font-semibold">
                How recall works across jurisdictions.
              </h2>
              <p className="mt-gap-title text-lead text-foreground/70">
                Recall is not an experimental idea. Versions of it are used in democracies across
                several continents, at levels of government ranging from a local council to a
                national legislature, and in some cases against directly elected executives.
              </p>
              <div className="mt-6 space-y-4 text-body text-foreground/70">
                <p>
                  What varies is almost everything else. Some systems allow a recall only where
                  specific misconduct is alleged; others let a loss of confidence stand on its own.
                  Some require support from a large share of the constituency before a petition
                  proceeds, others a much smaller one. Some put removal to a straight yes or no
                  vote, others fold it into a contest for the seat. Some cover every elected office,
                  others only the most local. Comparing two recall laws is often less like comparing
                  two versions of the same rule and more like comparing two different instruments
                  that happen to share a name.
                </p>
                <p>
                  India already sits inside this picture rather than outside it. Recall provisions
                  exist in the local-government law of several Indian states, generally reaching
                  municipal or panchayat representatives rather than state or national legislators.
                  So the practical question this movement puts is not whether recall is possible
                  here. It is at which levels it should reach, and with which safeguards attached.
                </p>
                <p className="text-foreground">
                  Read the examples below as design choices, each shaped by its own constitutional
                  and political setting, rather than as templates to be copied.
                </p>
              </div>
            </div>
          </Reveal>
          <StaggerGroup className="mt-gap-block grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {jurisdictions.map((j) => (
              <StaggerItem key={j.id}>
                <div
                  className="h-full rounded border border-border bg-card p-7"
                  data-testid={`jurisdiction-${j.id}`}
                >
                  <div className="flex items-center gap-2 text-label font-bold uppercase text-muted-foreground">
                    <Globe className="h-4 w-4 text-secondary" /> {j.region}
                  </div>
                  <h3 className="mt-3 font-heading text-title-4 font-semibold">{j.place}</h3>
                  <p className="mt-2 text-body text-foreground/70">{j.summary}</p>
                </div>
              </StaggerItem>
            ))}
          </StaggerGroup>
        </div>
      </section>

      {/*
       * ARGUMENTS AND COUNTER-ARGUMENTS. New section.
       *
       * Two columns of equal construction, drawn with a `gap-px` grid over
       * `bg-border` so the divider between "for" and "against" is a single
       * hairline and neither side is visually weighted above the other. A
       * non-partisan movement has to be able to state the objections in their
       * strongest form, so they get the same space and the same styling.
       *
       * Content-height: the two lists are long, and equal-height columns already
       * give the section presence without forcing 100vh.
       */}
      <section
        id="arguments"
        className="scroll-mt-28 border-b border-border px-6 py-20 md:px-12 md:py-28"
      >
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="max-w-2xl">
              <Eyebrow>For &amp; against</Eyebrow>
              <h2 className="mt-gap-title font-heading text-title-1 font-semibold">
                Arguments and counter-arguments.
              </h2>
              <p className="mt-gap-title text-lead text-foreground/70">
                Recall is a real proposal with real trade-offs, and the objections to it are not
                merely obstruction. Some of the most careful arguments against recall come from
                people who care as much about accountability as we do.
              </p>
              <p className="mt-6 text-body text-foreground/70">
                We publish both sides because a mechanism designed only by its own enthusiasts gets
                designed badly. If you are going to argue for a recall law, you should be able to
                state the case against it without flinching first.
              </p>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="mt-gap-block overflow-hidden rounded border border-border">
              <div className="grid gap-px bg-border lg:grid-cols-2">
                <div className="bg-card p-7 md:p-9">
                  <div className="flex items-center gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-secondary text-secondary-foreground">
                      <Check className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <h3 className="font-heading text-title-3 font-semibold">The case for recall</h3>
                  </div>
                  <ul className="mt-7 space-y-6">
                    {CASE_FOR.map((a) => (
                      <li key={a.title}>
                        <h4 className="font-heading text-title-4 font-semibold">{a.title}</h4>
                        <p className="mt-2 text-body text-foreground/70">{a.text}</p>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-card p-7 md:p-9">
                  <div className="flex items-center gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-primary text-primary-foreground">
                      <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <h3 className="font-heading text-title-3 font-semibold">
                      The honest objections
                    </h3>
                  </div>
                  <ul className="mt-7 space-y-6">
                    {OBJECTIONS.map((a) => (
                      <li key={a.title}>
                        <h4 className="font-heading text-title-4 font-semibold">{a.title}</h4>
                        <p className="mt-2 text-body text-foreground/70">{a.text}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="border-t border-border bg-muted/40 p-7 md:p-9">
                <p className="max-w-3xl text-body text-foreground/70">
                  Notice that most of the objections are objections to bad design rather than to the
                  idea itself. Thresholds, protected periods, who verifies a petition and what
                  counts as a valid outcome: get those wrong and every warning on the right hand
                  side comes true. That is precisely why the drafting detail, not the slogan, is
                  where the argument has to be won.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/*
       * MYTH VS FACT. Now on the muted step so the page keeps alternating as the
       * reader descends. Content-height, since the pair count comes from the CMS.
       */}
      <section
        id="myths"
        className="scroll-mt-28 border-b border-border bg-muted/30 px-6 py-20 md:px-12 md:py-28"
      >
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="max-w-2xl">
              <Eyebrow>Setting the record straight</Eyebrow>
              <h2 className="mt-gap-title font-heading text-title-1 font-semibold">
                Myth vs Fact.
              </h2>
              <p className="mt-gap-title text-lead text-foreground/70">
                Recall is unfamiliar in most national political conversation in India, and
                unfamiliar ideas attract confident claims. Much of what circulates comes from a few
                predictable places.
              </p>
              <div className="mt-6 space-y-4 text-body text-foreground/70">
                <p>
                  The word gets used loosely, and often gets folded together with other mechanisms
                  it has nothing to do with. Arguments are frequently made against the most reckless
                  imaginable version of a recall law rather than against any actual proposal. And
                  enthusiasm cuts the other way too: supporters sometimes present recall as a remedy
                  for problems it cannot touch, which does the case no favours.
                </p>
                <p>
                  The pairs below take the claims we hear most often and set each one against what
                  the mechanism actually involves.
                </p>
              </div>
            </div>
          </Reveal>
          <div className="mt-gap-block space-y-4">
            {myths.map((m, i) => (
              <Reveal key={m.id} delay={i * 0.05}>
                <div
                  className="grid gap-4 rounded border border-border bg-card p-6 md:grid-cols-2 md:p-8"
                  data-testid={`myth-${m.id}`}
                >
                  <div className="flex gap-3 rounded bg-destructive/10 p-5">
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded bg-destructive text-destructive-foreground">
                      <X className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-label font-bold uppercase text-destructive">Myth</p>
                      <p className="mt-1 font-medium">{m.myth}</p>
                    </div>
                  </div>
                  <div className="flex gap-3 rounded bg-secondary/10 p-5">
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded bg-secondary text-secondary-foreground">
                      <Check className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-label font-bold uppercase text-secondary">Fact</p>
                      <p className="mt-1 font-medium">{m.fact}</p>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/*
       * FAQ. Content-height and centred in a single reading column: an accordion
       * of unknown length is exactly the wrong thing to pin to the viewport.
       */}
      <section
        id="faq"
        className="scroll-mt-28 border-b border-border px-6 py-20 md:px-12 md:py-28"
      >
        <div className="mx-auto w-full max-w-3xl">
          <Reveal>
            <div className="text-center">
              <h2 className="font-heading text-title-1 font-semibold">
                Frequently asked questions.
              </h2>
              <p className="mx-auto mt-gap-title max-w-2xl text-lead text-foreground/70">
                The questions people actually send us, answered plainly. Where an answer depends on
                which law or which level of government you mean, we say so rather than guess.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <Accordion
              type="single"
              collapsible
              className="mt-gap-block space-y-3"
              data-testid="knowledge-faq"
            >
              {faq.map((f) => (
                <AccordionItem
                  key={f.id}
                  value={f.id}
                  className="overflow-hidden rounded border border-border bg-card px-5"
                >
                  <AccordionTrigger className="text-left font-heading text-lead font-medium hover:no-underline">
                    {f.question}
                  </AccordionTrigger>
                  <AccordionContent className="text-foreground/70">{f.answer}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </Reveal>
        </div>
      </section>

      {/*
       * RESEARCH. Content-height: the framing prose plus the evidence grid plus
       * three article cards is comfortably more than one screen already.
       */}
      <section
        id="research"
        className="scroll-mt-28 border-b border-border bg-muted/30 px-6 py-20 md:px-12 md:py-28"
      >
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="max-w-2xl">
              <Eyebrow>Read deeper</Eyebrow>
              <h2 className="mt-gap-title font-heading text-title-1 font-semibold">
                Research &amp; articles.
              </h2>
              <p className="mt-gap-title text-lead text-foreground/70">
                We are asking for a change to the law, so the burden of evidence sits with us. Four
                kinds of material do most of the work, and we try to cite primary documents wherever
                one exists.
              </p>
              <p className="mt-6 text-body text-foreground/70">
                Where the evidence is thin or contested, the honest answer is to say so, and you
                will find us saying so. A campaign that overstates its case invites everything it
                claims to be dismissed along with the overstatement.
              </p>
            </div>
          </Reveal>

          {/* Evidence types: one bordered object, hairlines from gap-px over bg-border. */}
          <Reveal delay={0.1}>
            <div className="mt-gap-block overflow-hidden rounded border border-border">
              <div className="grid gap-px bg-border sm:grid-cols-2">
                {EVIDENCE.map((e, i) => (
                  <div key={e.title} className="bg-card p-6 md:p-7">
                    <span className="font-heading text-micro font-bold text-muted-foreground">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="mt-3 font-heading text-title-4 font-semibold">{e.title}</h3>
                    <p className="mt-2 text-body text-foreground/70">{e.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal className="mt-gap-section">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <h3 className="font-heading text-title-2 font-semibold">Latest from the hub.</h3>
              <LinkButton to="/blog" variant="outline" size="sm">
                All articles <ArrowRight className="h-4 w-4" />
              </LinkButton>
            </div>
          </Reveal>
          <StaggerGroup className="mt-gap-block grid gap-6 md:grid-cols-3">
            {research.map((b) => (
              <StaggerItem key={b.id}>
                <article className="group h-full overflow-hidden rounded border border-border bg-card transition-transform duration-300 hover:-translate-y-2">
                  <div className="h-40 overflow-hidden">
                    <img
                      src={b.image}
                      alt={b.title}
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  </div>
                  <div className="p-6">
                    <span className="rounded bg-secondary px-3 py-1 text-label font-bold uppercase text-secondary-foreground">
                      {b.category}
                    </span>
                    <h3 className="mt-4 font-heading text-lead font-semibold">{b.title}</h3>
                    <p className="mt-2 text-body text-foreground/70">{b.excerpt}</p>
                  </div>
                </article>
              </StaggerItem>
            ))}
          </StaggerGroup>
        </div>
      </section>

      {/*
       * DOWNLOADS. Kept at full-viewport height: a short header over one row of
       * equal cards genuinely fills a screen, and ending the page on a full
       * section gives the toolkits a clean final frame.
       */}
      <section id="downloads" className="full-section scroll-mt-28 px-6 md:px-12">
        <div className="mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="max-w-2xl">
              <Eyebrow>Free toolkits</Eyebrow>
              <h2 className="mt-gap-title font-heading text-title-1 font-semibold">Downloads.</h2>
              <p className="mt-gap-title text-lead text-foreground/70">
                Everything here is free to copy, print, translate and hand on. If it helps someone
                explain recall accurately to a room of people, it is doing its job.
              </p>
            </div>
          </Reveal>
          <StaggerGroup className="mt-gap-block grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {resources.map((r) => {
              const Icon = typeIcon[r.type] || FileText;
              return (
                <StaggerItem key={r.id}>
                  <div className="flex h-full flex-col rounded border border-border bg-card p-7">
                    <div className="flex h-12 w-12 items-center justify-center rounded bg-secondary">
                      <Icon className="h-6 w-6 text-secondary-foreground" />
                    </div>
                    <span className="mt-5 text-label font-bold uppercase text-muted-foreground">
                      {r.type}
                    </span>
                    <h3 className="mt-2 font-heading text-lead font-semibold">{r.title}</h3>
                    <p className="mt-2 flex-1 text-body text-foreground/70">{r.description}</p>
                    <DynamicButton
                      variant="outline"
                      size="sm"
                      className="mt-6 self-start"
                      data-testid={`knowledge-download-${r.id}`}
                      onClick={() => handleDownload(r)}
                    >
                      {r.downloadLabel || "Download"}
                    </DynamicButton>
                  </div>
                </StaggerItem>
              );
            })}
          </StaggerGroup>
        </div>
      </section>
    </div>
  );
}
