"""FastAPI application for Groot Share."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from groot_share.app.config import (
    add_storage,
    delete_storage,
    get_storage,
    list_storages,
    update_storage,
)
from groot_share.app.settings import (
    ADMIN_PASSWORD,
    APP_NAME,
    APP_TAGLINE,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_SECRET,
    SESSION_COOKIE_SECURE,
    MAX_UPLOAD_SIZE_BYTES,
    UPLOAD_TMP_ROOT,
)
from groot_share.app.storage import (
    InsufficientPermissionsError,
    PathOutsideRootError,
    StorageError,
    StorageNotAvailableError,
)
from groot_share.app.storage_manager import get_adapter, list_adapters


async def upload_progress_receivers():
    """Simple progress tracking placeholder."""
    pass


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME)

    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        session_cookie=SESSION_COOKIE_NAME,
    )

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )

    # ---- Auth helpers ----
    def is_authenticated(request: Request) -> bool:
        return request.session.get("authenticated", False)

    def require_auth(request: Request):
        if not is_authenticated(request):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Basic"},
            )

    # ---- Routes ----

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if not is_authenticated(request):
            return RedirectResponse(url="/login", status_code=302)
        storages = list_adapters()
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "app_name": APP_NAME,
                "app_tagline": APP_TAGLINE,
                "storages": storages,
            },
        )

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        if is_authenticated(request):
            return RedirectResponse(url="/", status_code=302)
        return templates.TemplateResponse(
            "login.html", {"request": request, "app_name": APP_NAME}
        )

    @app.post("/login")
    async def login_post(request: Request, password: str = Form(...)):
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            request.session["authenticated"] = True
            return RedirectResponse(url="/", status_code=302)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "app_name": APP_NAME, "error": "Invalid password"},
            status_code=400,
        )

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "app_name": APP_NAME})

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        if not is_authenticated(request):
            return RedirectResponse(url="/login", status_code=302)
        all_storages = list_storages()
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "app_name": APP_NAME,
                "app_tagline": APP_TAGLINE,
                "storages": all_storages,
            },
        )

    # ---- Storage Configuration API ----

    def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
        """Remove secrets from a config dict before returning to client."""
        return {
            k: v
            for k, v in config.items()
            if not k.endswith(("_password", "secret", "key", "token", "password"))
        }

    @app.get("/api/storages")
    async def api_list_storages(request: Request):
        require_auth(request)
        result = {}
        for sid, config in list_storages().items():
            result[sid] = sanitize_config(config)
        return JSONResponse(result)

    @app.post("/api/storages")
    async def api_add_storage(
        request: Request,
        display_name: str = Form(...),
        storage_type: str = Form(...),
        path: str = Form(...),
        read_only: bool = Form(False),
        enabled: bool = Form(True),
        smb_server: str | None = Form(None),
        smb_share: str | None = Form(None),
        smb_subdir: str | None = Form(None),
        smb_username: str | None = Form(None),
        smb_password: str | None = Form(None),
        smb_domain: str | None = Form(None),
        nfs_server: str | None = Form(None),
        nfs_export: str | None = Form(None),
        nfs_version: str | None = Form(None),
    ):
        require_auth(request)
        storage_id = f"{storage_type}-{secrets.token_hex(4)}"
        config: dict[str, Any] = {
            "display_name": display_name,
            "storage_type": storage_type,
            "path": path,
            "read_only": read_only,
            "enabled": enabled,
        }
        if storage_type == "smb":
            if smb_server:
                config["smb_server"] = smb_server
            if smb_share:
                config["smb_share"] = smb_share
            if smb_subdir:
                config["smb_subdir"] = smb_subdir
            if smb_username:
                config["smb_username"] = smb_username
            if smb_password:
                config["smb_password"] = smb_password
            if smb_domain:
                config["smb_domain"] = smb_domain
        if storage_type == "nfs":
            if nfs_server:
                config["nfs_server"] = nfs_server
            if nfs_export:
                config["nfs_export"] = nfs_export
            if nfs_version:
                config["nfs_version"] = nfs_version

        try:
            add_storage(storage_id, config)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse(
            {"status": "added", "storage_id": storage_id}, status_code=201
        )

    @app.get("/api/storages/{storage_id}")
    async def api_get_storage(storage_id: str, request: Request):
        require_auth(request)
        config = get_storage(storage_id)
        if config is None:
            raise HTTPException(status_code=404, detail="Storage not found")
        return JSONResponse(sanitize_config(config))

    @app.put("/api/storages/{storage_id}")
    async def api_update_storage(
        storage_id: str,
        request: Request,
        display_name: str | None = Form(None),
        storage_type: str | None = Form(None),
        path: str | None = Form(None),
        read_only: bool | None = Form(None),
        enabled: bool | None = Form(None),
        smb_server: str | None = Form(None),
        smb_share: str | None = Form(None),
        smb_subdir: str | None = Form(None),
        smb_username: str | None = Form(None),
        smb_password: str | None = Form(None),
        smb_domain: str | None = Form(None),
        nfs_server: str | None = Form(None),
        nfs_export: str | None = Form(None),
        nfs_version: str | None = Form(None),
    ):
        require_auth(request)
        updates: dict[str, Any] = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if storage_type is not None:
            updates["storage_type"] = storage_type
        if path is not None:
            updates["path"] = path
        if read_only is not None:
            updates["read_only"] = read_only
        if enabled is not None:
            updates["enabled"] = enabled
        if smb_server is not None:
            updates["smb_server"] = smb_server
        if smb_share is not None:
            updates["smb_share"] = smb_share
        if smb_subdir is not None:
            updates["smb_subdir"] = smb_subdir
        if smb_username is not None:
            updates["smb_username"] = smb_username
        if smb_password is not None and smb_password != "":
            updates["smb_password"] = smb_password
        if smb_domain is not None:
            updates["smb_domain"] = smb_domain
        if nfs_server is not None:
            updates["nfs_server"] = nfs_server
        if nfs_export is not None:
            updates["nfs_export"] = nfs_export
        if nfs_version is not None:
            updates["nfs_version"] = nfs_version

        try:
            update_storage(storage_id, updates)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse({"status": "updated"})

    @app.delete("/api/storages/{storage_id}")
    async def api_delete_storage(storage_id: str, request: Request):
        require_auth(request)
        try:
            delete_storage(storage_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse({"status": "deleted"})

    @app.post("/api/storages/{storage_id}/test")
    async def api_test_storage(storage_id: str, request: Request):
        require_auth(request)
        try:
            adapter = get_adapter(storage_id)
            result = adapter.test_connection()
            return JSONResponse(result)
        except StorageError as exc:
            return JSONResponse(
                {"status": "error", "reason": str(exc)}, status_code=400
            )

    # ---- File Operations ----

    @app.get("/api/storages/{storage_id}/browse")
    async def api_browse(storage_id: str, request: Request, path: str = ""):
        require_auth(request)
        try:
            adapter = get_adapter(storage_id)
            items = adapter.browse(path)
            return JSONResponse(items)
        except (
            StorageNotAvailableError,
            InsufficientPermissionsError,
            PathOutsideRootError,
        ) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except StorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/storages/{storage_id}/upload")
    async def api_upload(
        storage_id: str,
        path: str = Form(""),
        file: UploadFile = File(...),
        request: Request,
    ):
        require_auth(request)
        try:
            adapter = get_adapter(storage_id)
            filename = file.filename or "unnamed"
            # Sanitize filename - take basename only
            filename = os.path.basename(filename)
            target_rel = f"{path}/{filename}" if path else filename
            # Stream to disk in chunks
            UPLOAD_TMP_ROOT.mkdir(parents=True, exist_ok=True)
            tmp_path = UPLOAD_TMP_ROOT / f"{secrets.token_hex(8)}_{filename}"
            total_size = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_UPLOAD_SIZE_BYTES:
                        f.close()
                        tmp_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413, detail="File exceeds maximum upload size."
                        )
                    f.write(chunk)
            # Now save through the adapter
            contents = tmp_path.read_bytes()
            result = adapter.upload_file(target_rel, contents)
            tmp_path.unlink(missing_ok=True)
            return JSONResponse(result)
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/storages/{storage_id}/download")
    async def api_download(
        storage_id: str, path: str = "", request: Request
    ):
        require_auth(request)
        try:
            adapter = get_adapter(storage_id)
            file_path = adapter.download_file(path)

            def iterfile(file_path: Path):
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        yield chunk

            return StreamingResponse(
                iterfile(file_path),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{file_path.name}"'
                },
            )
        except StorageNotAvailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except InsufficientPermissionsError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/storages/{storage_id}/mkdir")
    async def api_mkdir(
        storage_id: str, path: str = Form(...), request: Request
    ):
        require_auth(request)
        try:
            adapter = get_adapter(storage_id)
            adapter.create_dir(path)
            return JSONResponse({"status": "created"})
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/storages/{storage_id}/rename")
    async def api_rename(
        storage_id: str,
        old_path: str = Form(...),
        new_path: str = Form(...),
        request: Request,
    ):
        require_auth(request)
        try:
            adapter = get_adapter(storage_id)
            adapter.rename(old_path, new_path)
            return JSONResponse({"status": "renamed"})
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/storages/{storage_id}/item")
    async def api_delete_item(
        storage_id: str, path: str = None, request: Request
    ):
        require_auth(request)
        if path is None:
            path = request.query_params.get("path", "")
        try:
            adapter = get_adapter(storage_id)
            adapter.delete(path)
            return JSONResponse({"status": "deleted"})
        except StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return app


app = create_app()