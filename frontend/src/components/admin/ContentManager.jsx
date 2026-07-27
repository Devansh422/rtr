import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Loader2, Upload, X } from "lucide-react";
import {
  listContent,
  createContent,
  updateContent,
  deleteContent,
  uploadFile,
} from "@/lib/adminApi";

const emptyFrom = (schema) => {
  const o = {};
  schema.fields.forEach((f) => (o[f.name] = ""));
  return o;
};

export default function ContentManager({ type, schema }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [uploadingField, setUploadingField] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      setItems(await listContent(type));
    } catch {
      toast.error("Could not load items");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(); /* eslint-disable-next-line */
  }, [type]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyFrom(schema));
    setOpen(true);
  };
  const openEdit = (item) => {
    setEditing(item);
    setForm({ ...emptyFrom(schema), ...item });
    setOpen(true);
  };

  const handleUpload = async (fieldName, file) => {
    if (!file) return;
    setUploadingField(fieldName);
    try {
      const res = await uploadFile(file);
      setForm((f) => ({ ...f, [fieldName]: res.absoluteUrl }));
      toast.success("File uploaded");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setUploadingField(null);
    }
  };

  const save = async () => {
    const titleVal = form[schema.titleField];
    if (!titleVal || !String(titleVal).trim())
      return toast.error(`${schema.fields[0].label} is required`);
    setSaving(true);
    try {
      if (editing?.id) await updateContent(type, editing.id, form);
      else await createContent(type, form);
      toast.success(editing ? "Updated" : "Created");
      setOpen(false);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm("Delete this item? This cannot be undone.")) return;
    try {
      await deleteContent(type, item.id);
      toast.success("Deleted");
      setItems((prev) => prev.filter((x) => x.id !== item.id));
    } catch {
      toast.error("Could not delete ");
    }
  };

  return (
    <div data-testid={`cm-${type}`}>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="font-heading text-title-3 font-bold tracking-tight">{schema.label}</h2>
          <p className="text-body text-muted-foreground">
            {items.length} item{items.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          data-testid="cm-add"
          onClick={openNew}
          className="inline-flex items-center gap-2 rounded bg-primary px-5 py-2.5 text-body font-semibold text-primary-foreground transition-transform hover:scale-105 active:scale-95"
        >
          <Plus className="h-4 w-4" /> Add new
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-secondary" />
        </div>
      ) : items.length === 0 ? (
        <p className="rounded border border-border bg-card p-10 text-center text-muted-foreground">
          No items yet. Click"Add new"to create one.
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.id}
              data-testid={`cm-row-${item.id}`}
              className="flex items-center gap-4 rounded border border-border bg-card p-4"
            >
              {(item.image || item.avatar) && (
                <img
                  src={item.image || item.avatar}
                  alt=""
                  className="h-12 w-12 shrink-0 rounded object-cover"
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{item[schema.titleField] || "(untitled)"}</p>
                {schema.subField && item[schema.subField] && (
                  <p className="truncate text-meta uppercase tracking-widest text-muted-foreground">
                    {item[schema.subField]}
                  </p>
                )}
              </div>
              <button
                data-testid={`cm-edit-${item.id}`}
                onClick={() => openEdit(item)}
                className="flex h-9 w-9 items-center justify-center rounded border border-border text-foreground/70 transition-colors hover:bg-muted"
                aria-label="Edit"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                data-testid={`cm-delete-${item.id}`}
                onClick={() => remove(item)}
                className="flex h-9 w-9 items-center justify-center rounded border border-border text-destructive transition-colors hover:bg-destructive/10"
                aria-label="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] max-w-2xl overflow-y-auto rounded">
          <DialogHeader>
            <DialogTitle className="font-heading text-title-4">
              {editing ? "Edit" : "New"} · {schema.label}
            </DialogTitle>
            <DialogDescription>
              Fill in the fields below and save. Changes go live on the site immediately.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {schema.fields.map((f) => (
              <label key={f.name} className="block">
                <span className="mb-1.5 block text-label font-bold uppercase text-muted-foreground">
                  {f.label}
                </span>
                {f.type === "textarea" ? (
                  <Textarea
                    data-testid={`field-${f.name}`}
                    rows={f.name === "content" ? 6 : 3}
                    value={form[f.name] || ""}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                    className="rounded"
                  />
                ) : f.type === "image" ? (
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <Input
                        data-testid={`field-${f.name}`}
                        value={form[f.name] || ""}
                        onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                        placeholder="Paste a URL or upload"
                        className="h-11 rounded"
                      />
                      <label className="inline-flex cursor-pointer items-center gap-2 rounded border border-border px-4 text-body font-semibold transition-colors hover:bg-muted">
                        {uploadingField === f.name ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Upload className="h-4 w-4" />
                        )}
                        <input
                          data-testid={`upload-${f.name}`}
                          type="file"
                          className="hidden"
                          onChange={(e) => handleUpload(f.name, e.target.files?.[0])}
                        />
                      </label>
                    </div>
                    {form[f.name] && (
                      <div className="flex items-center gap-2">
                        <img
                          src={form[f.name]}
                          alt="preview"
                          className="h-14 w-14 rounded object-cover"
                          onError={(e) => (e.currentTarget.style.display = "none")}
                        />
                        <button
                          onClick={() => setForm({ ...form, [f.name]: "" })}
                          className="text-meta text-muted-foreground hover:text-foreground"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <Input
                    data-testid={`field-${f.name}`}
                    type={f.type === "date" ? "date" : "text"}
                    value={form[f.name] || ""}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                    className="h-11 rounded"
                  />
                )}
              </label>
            ))}
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setOpen(false)}
              className="rounded border border-border px-5 py-2.5 text-body font-semibold transition-colors hover:bg-muted"
            >
              Cancel
            </button>
            <button
              data-testid="cm-save"
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded bg-primary px-6 py-2.5 text-body font-semibold text-primary-foreground transition-transform hover:scale-105 active:scale-95 disabled:opacity-60"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : editing ? (
                "Save changes"
              ) : (
                "Create"
              )}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
