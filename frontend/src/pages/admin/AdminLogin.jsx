import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Lock } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import DynamicButton from "@/components/DynamicButton";

export default function AdminLogin() {
  const { login, status } = useAdminAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (status === "in") navigate("/admin", { replace: true });
  }, [status, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      navigate("/admin", { replace: true });
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex min-h-screen items-center justify-center bg-background px-6"
      data-testid="admin-login"
    >
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src="/logo.png" alt="Right to Recall" className="h-16 w-16 rounded object-cover" />
          <h1 className="mt-4 font-heading text-title-3 font-bold tracking-tight">
            Admin Dashboard
          </h1>
          <p className="text-body text-muted-foreground">#RightToRecall Movement</p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded border border-border bg-card p-8">
          <label className="block">
            <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
              Email
            </span>
            <input
              data-testid="admin-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-12 w-full rounded border border-input bg-background px-4 text-body outline-none focus:ring-1 focus:ring-secondary"
              placeholder="you@email.com"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
              Password
            </span>
            <input
              data-testid="admin-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-12 w-full rounded border border-input bg-background px-4 text-body outline-none focus:ring-1 focus:ring-secondary"
              placeholder="••••••••"
            />
          </label>
          <DynamicButton
            data-testid="admin-login-submit"
            type="submit"
            loading={loading}
            size="lg"
            className="w-full"
            loadingLabel="Signing in"
          >
            <Lock className="h-4 w-4" /> Sign in
          </DynamicButton>
        </form>
      </div>
    </div>
  );
}
