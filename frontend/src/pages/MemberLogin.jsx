import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Lock, Mail } from "lucide-react";
import { Input } from "@/components/ui/input";
import DynamicButton from "@/components/DynamicButton";
import { useMemberAuth } from "@/context/MemberAuthContext";
import { CONTACT_EMAIL } from "@/lib/social";

/*
 * Login for the supporter/volunteer dashboard. Credential is an access code
 * generated at signup (see backend/server.py generate_access_code), shown once
 * on a dedicated screen right after joining -- never printed on the shareable
 * certificate graphic, since that image is designed to be posted publicly.
 *
 * There is no password-reset email flow: this project has no SMTP configured,
 * so a lost code is a support contact, not a self-service reset.
 */
export default function MemberLogin() {
  const { login } = useMemberAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email || !code) return toast.error("Enter your email and access code");
    setLoading(true);
    try {
      await login(email, code);
      toast.success("Welcome back");
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Invalid email or access code");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex min-h-svh items-center justify-center bg-background px-6"
      data-testid="member-login"
    >
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <img
            src="/logo.png"
            alt="Right to Recall"
            className="h-14 w-14 rounded object-cover"
          />
          <h1 className="mt-4 font-heading text-title-3 font-bold">Your dashboard</h1>
          <p className="text-body text-muted-foreground">
            Sign in with the email and access code from your welcome screen.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded border border-border bg-card p-8">
          <label className="block">
            <span className="mb-1.5 flex items-center gap-1.5 text-label font-bold uppercase text-muted-foreground">
              <Mail className="h-3.5 w-3.5" /> Email
            </span>
            <Input
              data-testid="member-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@email.com"
              className="h-10 rounded"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 flex items-center gap-1.5 text-label font-bold uppercase text-muted-foreground">
              <Lock className="h-3.5 w-3.5" /> Access code
            </span>
            <Input
              data-testid="member-code"
              required
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="XXXX-XXXX"
              className="h-10 rounded font-heading tracking-widest"
            />
          </label>

          <DynamicButton
            data-testid="member-login-submit"
            type="submit"
            loading={loading}
            className="w-full"
          >
            Sign in
          </DynamicButton>

          <p className="text-center text-meta text-muted-foreground">
            Lost your code?{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="underline hover:text-foreground">
              Contact us
            </a>{" "}
            with the email you signed up with.
          </p>
        </form>
      </div>
    </div>
  );
}
