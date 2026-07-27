import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import { Download, Loader2, BadgeCheck } from "lucide-react";
import { toast } from "sonner";
import ChakraWheel from "@/components/ChakraWheel";

export default function SupporterCertificate({ name, movementId, date }) {
  const ref = useRef(null);
  const [downloading, setDownloading] = useState(false);

  const prettyDate = date
    ? new Date(date).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })
    : new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });

  const download = async () => {
    if (!ref.current) return;
    setDownloading(true);
    try {
      const dataUrl = await toPng(ref.current, { pixelRatio: 2, cacheBust: true });
      const link = document.createElement("a");
      link.download = `RightToRecall-Certificate-${movementId || "supporter"}.png`;
      link.href = dataUrl;
      link.click();
      toast.success("Certificate downloaded!");
    } catch {
      toast.error("Could not download. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-8">
      {/* Certificate (always light for clean export) */}
      <div
        ref={ref}
        data-testid="supporter-certificate"
        className="relative z-10 w-full max-w-xl overflow-hidden rounded bg-white text-slate-900"
        style={{ fontFamily: '"Roboto Mono", monospace' }}
      >
        <div
          style={{
            height: 8,
            background:
              "linear-gradient(90deg,#FF9933 0 33.33%,#ffffff 33.33% 66.66%,#138808 66.66% 100%)",
          }}
        />
        <div className="px-8 py-9 text-center" style={{ border: "1px solid #eee" }}>
          <div
            className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded"
            style={{ border: "1px solid #e2e2e2" }}
          >
            <ChakraWheel className="h-10 w-10" color="#000080" />
          </div>
          <p
            className="text-[0.65rem] font-bold uppercase tracking-[0.35em]"
            style={{ color: "#138808" }}
          >
            Certificate of Support
          </p>
          <p className="mt-5 text-body text-slate-500">This certifies that</p>
          <p
            className="mt-2 text-title-2 font-bold tracking-tight"
            style={{ color: "#0b1030" }}
            data-testid="certificate-name"
          >
            {name || "A Proud Citizen"}
          </p>
          <p className="mx-auto mt-5 max-w-md text-body leading-relaxed text-slate-600">
            has pledged support for greater accountability in democracy through the
            <span style={{ color: "#FF9933", fontWeight: 700 }}> Right to Recall</span> Movement.
          </p>
          <div className="mt-7 flex items-center justify-between text-left text-meta">
            <div>
              <p className="font-bold uppercase tracking-widest text-slate-400">Movement ID</p>
              <p
                className="mt-1 font-bold"
                style={{ color: "#000080" }}
                data-testid="certificate-id"
              >
                {movementId || "Pending"}
              </p>
            </div>
            <div className="text-right">
              <p className="font-bold uppercase tracking-widest text-slate-400">Issued</p>
              <p className="mt-1 font-bold text-slate-700">{prettyDate}</p>
            </div>
          </div>
          <p className="mt-6 text-meta font-semibold tracking-wide text-slate-500">
            #RightToRecall Movement · A non-partisan civic initiative
          </p>
        </div>
        <div
          style={{
            height: 8,
            background:
              "linear-gradient(90deg,#FF9933 0 33.33%,#ffffff 33.33% 66.66%,#138808 66.66% 100%)",
          }}
        />
      </div>

      {/* Badge + ID + Download */}
      <div className="flex w-full max-w-xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
        <div
          className="flex items-center gap-3 rounded border border-border bg-card px-4 py-3"
          data-testid="supporter-badge"
        >
          <span className="flex h-11 w-11 items-center justify-center rounded bg-secondary">
            <BadgeCheck className="h-6 w-6 text-secondary-foreground" />
          </span>
          <div className="leading-tight">
            <p className="text-label font-bold uppercase text-muted-foreground">
              Verified Supporter
            </p>
            <p className="font-heading text-body font-bold">{movementId}</p>
          </div>
        </div>
        <button
          data-testid="download-certificate"
          onClick={download}
          disabled={downloading}
          className="inline-flex items-center justify-center gap-2 rounded bg-primary px-6 py-3 font-heading text-body font-semibold text-primary-foreground transition-transform hover:scale-105 active:scale-95 disabled:opacity-60"
        >
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Download Certificate
        </button>
      </div>
    </div>
  );
}
