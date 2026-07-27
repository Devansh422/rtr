import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Loader2, ShieldCheck, UserCog } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { listAdminUsers, createAdminUser, updateAdminUser, deleteAdminUser } from "@/lib/adminApi";
import { ALL_PERMISSIONS } from "@/pages/admin/schemas";
import { useAdminAuth } from "@/context/AdminAuthContext";

const CONTENT_PERMS = ALL_PERMISSIONS.filter((p) => p.key.startsWith("content."));
const OTHER_PERMS = ALL_PERMISSIONS.filter((p) => !p.key.startsWith("content."));
const ALL_KEYS = ALL_PERMISSIONS.map((p) => p.key);

const EMPTY = { name: "", email: "", password: "", permissions: [] };

function accessLabel(permissions) {
  if (permissions == null) return "Full access";
  if (permissions.length === 0) return "No access yet";
  if (permissions.length === ALL_KEYS.length) return "Full access";
  return `${permissions.length} permission${permissions.length === 1 ? "" : "s"}`;
}

export default function Team() {
  const { user: me } = useAdminAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setUsers(await listAdminUsers());
    } catch {
      toast.error("Could not load team");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setEditing(null);
    setForm(EMPTY);
    setOpen(true);
  };

  const openEdit = (u) => {
    setEditing(u);
    // A legacy null-permissions account is seeded with every key checked, so
    // saving without touching anything preserves the same effective access --
    // the API has no way to write permissions back to null once set (see
    // update_admin_user in backend/server.py), so this direction is one-way.
    setForm({
      name: u.name || "",
      email: u.email,
      password: "",
      permissions: u.permissions == null ? [...ALL_KEYS] : u.permissions,
    });
    setOpen(true);
  };

  const togglePerm = (key) =>
    setForm((f) => ({
      ...f,
      permissions: f.permissions.includes(key)
        ? f.permissions.filter((p) => p !== key)
        : [...f.permissions, key],
    }));

  const save = async () => {
    if (!form.name.trim()) return toast.error("Name is required");
    if (!editing) {
      if (!form.email.trim()) return toast.error("Email is required");
      if (!form.password || form.password.length < 8)
        return toast.error("Password must be at least 8 characters");
    }
    setSaving(true);
    try {
      if (editing) {
        const payload = { name: form.name, permissions: form.permissions };
        if (form.password) payload.password = form.password;
        await updateAdminUser(editing.id, payload);
        toast.success("Updated");
      } else {
        await createAdminUser({
          name: form.name,
          email: form.email,
          password: form.password,
          permissions: form.permissions,
        });
        toast.success("Teammate added");
      }
      setOpen(false);
      await load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (u) => {
    const next = !(u.active !== false);
    try {
      await updateAdminUser(u.id, { active: next });
      setUsers((list) => list.map((x) => (x.id === u.id ? { ...x, active: next } : x)));
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Could not update status");
    }
  };

  const remove = async (u) => {
    if (!window.confirm(`Remove ${u.name || u.email} from the team? This cannot be undone.`))
      return;
    try {
      await deleteAdminUser(u.id);
      setUsers((list) => list.filter((x) => x.id !== u.id));
      toast.success("Removed");
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Could not remove");
    }
  };

  return (
    <div data-testid="team-page">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="font-heading text-title-3 font-bold tracking-tight">Team</h2>
          <p className="text-body text-muted-foreground">
            Admin users and what each of them can access.
          </p>
        </div>
        <button
          data-testid="team-add"
          onClick={openNew}
          className="inline-flex items-center gap-2 rounded bg-primary px-5 py-2.5 text-body font-semibold text-primary-foreground transition-transform hover:scale-105 active:scale-95"
        >
          <Plus className="h-4 w-4" /> Add teammate
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-secondary" />
        </div>
      ) : (
        <div className="space-y-3">
          {users.map((u) => {
            const isSelf = u.id === me?.id;
            const active = u.active !== false;
            return (
              <div
                key={u.id}
                data-testid={`team-row-${u.id}`}
                className={`flex flex-wrap items-center gap-4 rounded border border-border bg-card p-4 ${
                  !active ? "opacity-60" : ""
                }`}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-muted">
                  <UserCog className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-semibold">{u.name || "(no name)"}</p>
                    {isSelf && (
                      <span className="rounded bg-muted px-2 py-0.5 text-micro font-bold uppercase text-muted-foreground">
                        You
                      </span>
                    )}
                    {!active && (
                      <span className="rounded bg-destructive/10 px-2 py-0.5 text-micro font-bold uppercase text-destructive">
                        Deactivated
                      </span>
                    )}
                  </div>
                  <p className="truncate text-meta text-muted-foreground">{u.email}</p>
                </div>
                <div
                  className="flex items-center gap-1.5 rounded border border-border px-3 py-1.5 text-meta font-semibold text-foreground/80"
                  data-testid={`team-access-${u.id}`}
                >
                  <ShieldCheck className="h-3.5 w-3.5 text-secondary" /> {accessLabel(u.permissions)}
                </div>
                <button
                  data-testid={`team-edit-${u.id}`}
                  onClick={() => openEdit(u)}
                  className="flex h-9 w-9 items-center justify-center rounded border border-border text-foreground/70 transition-colors hover:bg-muted"
                  aria-label="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <label className="flex items-center gap-2" title={isSelf ? "You cannot deactivate your own account" : "Active"}>
                  <Switch
                    data-testid={`team-active-${u.id}`}
                    checked={active}
                    disabled={isSelf}
                    onCheckedChange={() => toggleActive(u)}
                  />
                </label>
                <button
                  data-testid={`team-delete-${u.id}`}
                  onClick={() => remove(u)}
                  disabled={isSelf}
                  title={isSelf ? "You cannot remove your own account" : "Remove"}
                  className="flex h-9 w-9 items-center justify-center rounded border border-border text-destructive transition-colors hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] max-w-2xl overflow-y-auto rounded">
          <DialogHeader>
            <DialogTitle className="font-heading text-title-4">
              {editing ? "Edit teammate" : "Add teammate"}
            </DialogTitle>
            <DialogDescription>
              {editing
                ? "Update their name, password, or what they can access."
                : "They'll sign in with the email and password below at /admin/login."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
                  Name
                </span>
                <Input
                  data-testid="team-field-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="h-11 rounded"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
                  Email
                </span>
                <Input
                  data-testid="team-field-email"
                  type="email"
                  value={form.email}
                  disabled={!!editing}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="h-11 rounded disabled:opacity-60"
                />
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
                {editing ? "New password (leave blank to keep current)" : "Password"}
              </span>
              <Input
                data-testid="team-field-password"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={editing ? "••••••••" : "At least 8 characters"}
                className="h-11 rounded"
              />
            </label>

            <div className="border-t border-border pt-4">
              <p className="mb-3 text-label font-bold uppercase text-muted-foreground">
                Content permissions
              </p>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {CONTENT_PERMS.map((p) => (
                  <PermRow key={p.key} p={p} checked={form.permissions.includes(p.key)} onToggle={togglePerm} />
                ))}
              </div>
            </div>

            <div className="border-t border-border pt-4">
              <p className="mb-3 text-label font-bold uppercase text-muted-foreground">
                Dashboard permissions
              </p>
              <div className="grid gap-2.5">
                {OTHER_PERMS.map((p) => (
                  <PermRow key={p.key} p={p} checked={form.permissions.includes(p.key)} onToggle={togglePerm} />
                ))}
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setOpen(false)}
              className="rounded border border-border px-5 py-2.5 text-body font-semibold transition-colors hover:bg-muted"
            >
              Cancel
            </button>
            <button
              data-testid="team-save"
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded bg-primary px-6 py-2.5 text-body font-semibold text-primary-foreground transition-transform hover:scale-105 active:scale-95 disabled:opacity-60"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : editing ? "Save changes" : "Add teammate"}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PermRow({ p, checked, onToggle }) {
  return (
    <label
      data-testid={`team-perm-${p.key}`}
      className="flex items-center gap-2.5 rounded px-2 py-1.5 text-body-sm transition-colors hover:bg-muted"
    >
      <Checkbox checked={checked} onCheckedChange={() => onToggle(p.key)} />
      {p.label}
    </label>
  );
}
