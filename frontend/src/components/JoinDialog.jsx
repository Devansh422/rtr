import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { joinMovement } from "@/lib/api";
import { Check } from "lucide-react";
import { useGsap, gsap, EASE_OUT } from "@/lib/motion";
import DynamicButton from "@/components/DynamicButton";

const STATES = [
  "Andhra Pradesh",
  "Assam",
  "Bihar",
  "Delhi",
  "Gujarat",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Punjab",
  "Rajasthan",
  "Tamil Nadu",
  "Telangana",
  "Uttar Pradesh",
  "West Bengal",
  "Other",
];

export default function JoinDialog({ open, onOpenChange }) {
  const [form, setForm] = useState({ name: "", email: "", state: "" });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  // Pops the confirmation in once `done` flips. Keyed on `done` so it replays if
  // the dialog is reopened and submitted again. Targets an explicit attribute
  // rather than a tag selector, so nested elements aren't animated twice.
  const successRef = useGsap(() => {
    gsap.from("[data-success-item]", {
      opacity: 0,
      y: 12,
      duration: 0.4,
      stagger: 0.06,
      ease: EASE_OUT,
    });
  }, [done]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.email) return toast.error("Please enter your email");
    setLoading(true);
    try {
      const res = await joinMovement(form);
      setDone(true);
      toast.success(res.message);
      setTimeout(() => {
        onOpenChange(false);
        setTimeout(() => {
          setDone(false);
          setForm({ name: "", email: "", state: "" });
        }, 300);
      }, 1400);
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="join-dialog"
        className="max-w-md rounded border-border p-0 overflow-hidden"
      >
        <div className="bg-primary px-6 py-5">
          <DialogHeader>
            <DialogTitle className="font-heading text-title-3 font-semibold tracking-tight text-primary-foreground">
              Join the Movement
            </DialogTitle>
            <DialogDescription className="text-primary-foreground/70">
              Add your voice. Non-partisan. Zero spam. Real accountability.
            </DialogDescription>
          </DialogHeader>
        </div>

        {done ? (
          <div ref={successRef} className="flex flex-col items-center gap-3 px-6 py-12 text-center">
            <div
              data-success-item
              className="flex h-16 w-16 items-center justify-center rounded bg-primary"
            >
              <Check className="h-8 w-8 text-primary-foreground" aria-hidden="true" />
            </div>
            <p data-success-item className="font-heading text-title-3 font-bold">
              You're in!
            </p>
            <p data-success-item className="text-body text-muted-foreground">
              Welcome to the movement.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4 px-6 pb-6 pt-5">
            <Input
              data-testid="join-name-input"
              placeholder="Your name (optional)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="h-10 rounded"
            />
            <Input
              data-testid="join-email-input"
              type="email"
              required
              placeholder="Email address"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="h-10 rounded"
            />
            <select
              data-testid="join-state-select"
              value={form.state}
              onChange={(e) => setForm({ ...form, state: e.target.value })}
              className="h-10 w-full rounded border border-input bg-background px-4 text-body text-foreground outline-none focus:ring-1 focus:ring-secondary"
            >
              <option value="">Select your state (optional)</option>
              {STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <DynamicButton
              data-testid="join-submit-button"
              type="submit"
              loading={loading}
              variant="secondary"
              className="w-full h-10"
            >
              Count me in
            </DynamicButton>
            <p className="text-center text-meta text-muted-foreground">
              A civic movement for democratic accountability. Not affiliated with any party.
            </p>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
