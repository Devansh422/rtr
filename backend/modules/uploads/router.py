"""Binary uploads for the admin CMS.

Current storage is base64 inside Mongo, carried over unchanged from before
Phase 0. That is fine for a handful of editorial images and wrong for the Media
Library described in the brief -- it consumes the 512 MB Atlas cap with data
that is neither queryable nor cacheable, and serves every byte back through a
serverless function.

MIGRATION TARGET (Phase 4, with the Media Library): Cloudflare R2 -- 10 GB free
and, unusually, zero egress charges, which is the property that matters for a
public library of posters and PDFs. The route contract below (`{id, filename,
url}`) is already storage-agnostic, so that swap changes this module only.
"""

import base64

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from backend.core import config
from backend.core.deps import get_current_admin
from backend.core.models import new_id
from backend.core.mongo import db
from backend.core.rbac import Principal
from backend.core.security import now_iso

router = APIRouter(tags=["uploads"])


@router.post("/admin/uploads")
async def admin_upload(file: UploadFile = File(...), admin: Principal = Depends(get_current_admin)):
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 6MB)")
    uid = new_id().replace("-", "")
    await db.uploads.insert_one(
        {
            "id": uid,
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "data": base64.b64encode(data).decode("utf-8"),
            "uploaded_by": admin.id,
            "created_at": now_iso(),
        }
    )
    return {"id": uid, "filename": file.filename, "url": f"/api/uploads/{uid}"}


@router.get("/uploads/{uid}")
async def get_upload(uid: str):
    doc = await db.uploads.find_one({"id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=base64.b64decode(doc["data"]), media_type=doc["content_type"])
