"""CV Studio: the LaTeX-powered CV builder.

    GET  /cv/studio                 template carousel — arrows, type-to-find, Select
    GET  /cv/studio/use/<id>         pick a template, go to the form
    GET  /cv/studio/edit             the form (reuses the picked template)
    POST /cv/studio/edit             save
    POST /cv/studio/preview          AJAX: compile current form data, return a PNG preview
    GET  /cv/studio/download         download the PDF
    POST /cv/studio/publish          make this PDF your CV (same handoff as the old builder)
    POST /cv/studio/photo            upload/replace the CV photo
    POST /cv/studio/photo/remove     remove it
    GET  /cv/studio/photo.jpg        serve the learner's own photo (private)

This sits next to the older reportlab-based /cv routes in learner_routes.py
rather than replacing them: a learner's CVProfile.template is either one of
classic/modern/minimal/creative (reportlab) or latex:<id> (this file). Either
way cv_service.restore_builder_files() knows how to rebuild the PDF after a
Render redeploy wipes /uploads.
"""
import base64
import io
import json
import os

from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template,
    request, send_file, session, url_for,
)
from flask_login import current_user, login_required

import cv_pdf  # reportlab fallback when pdflatex isn't installed
from cv_latex_data import (
    ACCENTS, LATEX_TEMPLATES, cv_problems_latex, clean_cv_latex,
    donut_segments, identity_name_mismatch, starter_data_latex,
)
from latex_engine import (
    ICONS, LatexBuildError, RateLimited, compile_pdf, pdflatex_available,
    pdf_to_png_pages, stamp_identity_mismatch,
)
from models import CVPhoto, CVProfile, Document, User, db
from public_routes import csrf_bounce, csrf_ok, tile_tone

cv_studio_bp = Blueprint("cv_studio", __name__)

MAX_PHOTO_BYTES = 4 * 1024 * 1024
BUILDER_TAG = "cvbuilder"


# --------------------------------------------------------------------------
# small shared helpers
# --------------------------------------------------------------------------
def _profile():
    return CVProfile.query.filter_by(user_id=current_user.id).first()


def _current_template_id():
    p = _profile()
    if p and p.template.startswith("latex:"):
        tid = p.template.split(":", 1)[1]
        if tid in LATEX_TEMPLATES:
            return tid
    return session.get("cv_studio_template", next(iter(LATEX_TEMPLATES)))


def _load_data(profile):
    try:
        data = json.loads(profile.data) if profile else {}
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _photo_row(user_id=None):
    return CVPhoto.query.filter_by(user_id=user_id if user_id is not None else current_user.id).first()


def _render_context(data, template_id, user_id=None):
    meta = LATEX_TEMPLATES[template_id]
    photo = _photo_row(user_id) if data.get("show_photo") else None
    ctx = {
        "d": data,
        "accent_hex": ACCENTS.get(data.get("accent", "blue"), ACCENTS["blue"]).lstrip("#"),
        "has_photo": bool(photo),
        "donut": donut_segments(data.get("time_split", [])) if meta["donut"] else [],
    }
    assets = {"photo.jpg": photo.content} if photo else {}
    return meta["file"], ctx, assets


def _compile_for_user(data, template_id, user_id=None, use_cache=True):
    uid = user_id if user_id is not None else current_user.id
    tfile, ctx, assets = _render_context(data, template_id, user_id=uid)
    return compile_pdf(tfile, ctx, assets=assets, user_id=uid, use_cache=use_cache)


def _account_full_name(user_id):
    try:
        if user_id is None or (current_user.is_authenticated and user_id == current_user.id):
            return current_user.full_name
    except Exception:
        pass  # no request context (e.g. a background restore job) -- fall through to a direct lookup
    user = User.query.get(user_id) if user_id is not None else None
    return user.full_name if user else None


def _maybe_stamp_mismatch(pdf_bytes, data, user_id=None):
    """Apply the diagonal 'name doesn't match account' stamp (see
    latex_engine.stamp_identity_mismatch) whenever the CV's own full_name
    field shares no resemblance with the paying account's name. Never blocks
    anything -- it's purely a visible flag, applied identically to the live
    preview, the direct download, and the copy that gets published/attached
    to applications, so there's no path that skips it."""
    if identity_name_mismatch(data.get("full_name"), _account_full_name(user_id)):
        try:
            return stamp_identity_mismatch(pdf_bytes)
        except Exception:
            current_app.logger.exception("identity-mismatch stamp failed")
    return pdf_bytes


def build_latex_cv_pdf(user_id, data, template_id, path_or_buf):
    """Render a learner's saved CV Studio data to a PDF, writing it to a path
    or a file-like object. Falls back to the plain reportlab layout if
    pdflatex isn't installed, or if the LaTeX build fails for any reason —
    a learner should never be left with no CV at all over a template bug.
    Used both by the Flask routes below (current_user) and by
    cv_service.restore_builder_files() for any learner (explicit user_id)."""
    pdf_bytes = None
    if pdflatex_available():
        try:
            pdf_bytes = _compile_for_user(data, template_id, user_id=user_id)
        except (LatexBuildError, RateLimited):
            pdf_bytes = None
    if not pdf_bytes:
        buf = io.BytesIO()
        _fallback_reportlab(data, buf)
        pdf_bytes = buf.getvalue()

    pdf_bytes = _maybe_stamp_mismatch(pdf_bytes, data, user_id)

    if hasattr(path_or_buf, "write"):
        path_or_buf.write(pdf_bytes)
    else:
        with open(path_or_buf, "wb") as f:
            f.write(pdf_bytes)


# --------------------------------------------------------------------------
# template picker (carousel)
# --------------------------------------------------------------------------
@cv_studio_bp.route("/cv/studio")
@login_required
def cv_studio_picker():
    items = [{"id": k, **v} for k, v in LATEX_TEMPLATES.items()]
    current = _current_template_id()
    return render_template(
        "v2/cv_studio_picker.html", items=items, current=current,
        pdflatex_available=pdflatex_available(),
        from_apply=bool(session.get("apply_ids")),
    )


@cv_studio_bp.route("/cv/studio/use/<template_id>")
@login_required
def cv_studio_use(template_id):
    if template_id not in LATEX_TEMPLATES:
        flash("Pick a template from the list.", "warning")
        return redirect(url_for("cv_studio.cv_studio_picker"))
    session["cv_studio_template"] = template_id
    return redirect(url_for("cv_studio.cv_studio_edit"))


# --------------------------------------------------------------------------
# the form
# --------------------------------------------------------------------------
@cv_studio_bp.route("/cv/studio/edit", methods=["GET", "POST"])
@login_required
def cv_studio_edit():
    template_id = _current_template_id()
    meta = LATEX_TEMPLATES[template_id]
    profile = _profile()

    if request.method == "POST":
        if not csrf_ok():
            return csrf_bounce(url_for("cv_studio.cv_studio_edit"))
        data = clean_cv_latex(request.form)
        problems = cv_problems_latex(data)
        p = profile or CVProfile(user_id=current_user.id)
        p.data = json.dumps(data, ensure_ascii=False)
        p.template = f"latex:{template_id}"
        if p.id is None:
            db.session.add(p)
        db.session.commit()
        if problems:
            for msg in problems:
                flash(msg, "warning")
            return redirect(url_for("cv_studio.cv_studio_edit"))
        flash("Saved. Check the preview, then publish when you're happy.", "success")
        return redirect(url_for("cv_studio.cv_studio_edit"))

    data = _load_data(profile) if (profile and profile.template == f"latex:{template_id}") else starter_data_latex(current_user)
    return render_template(
        "v2/cv_studio_edit.html", d=data, template_id=template_id, meta=meta,
        templates=LATEX_TEMPLATES, icons=ICONS, accents=ACCENTS,
        pdflatex_available=pdflatex_available(),
        has_photo=bool(_photo_row()),
        from_apply=bool(session.get("apply_ids")),
    )


# --------------------------------------------------------------------------
# live preview (AJAX) — compiles whatever's currently in the form, unsaved
# --------------------------------------------------------------------------
@cv_studio_bp.route("/cv/studio/preview", methods=["POST"])
@login_required
def cv_studio_preview():
    if not csrf_ok():
        return jsonify(ok=False, message="Your session timed out — reload the page."), 400

    template_id = request.form.get("template") or _current_template_id()
    if template_id not in LATEX_TEMPLATES:
        return jsonify(ok=False, message="Unknown template."), 400

    if not pdflatex_available():
        return jsonify(ok=False, message="Live preview isn't available on this server right now "
                                          "(LaTeX isn't installed) — your text still saves fine, "
                                          "and you can download the PDF once it is."), 200

    data = clean_cv_latex(request.form)
    tfile, ctx, assets = _render_context(data, template_id)
    try:
        pdf = compile_pdf(tfile, ctx, assets=assets, user_id=current_user.id, use_cache=True)
    except RateLimited:
        return jsonify(ok=False, message="Slow down a touch — one preview every couple of seconds."), 200
    except LatexBuildError as e:
        return jsonify(ok=False, message=str(e)), 200

    pdf = _maybe_stamp_mismatch(pdf, data, current_user.id)

    try:
        pages = pdf_to_png_pages(pdf, dpi=104, max_pages=2)
    except Exception:
        current_app.logger.exception("preview render failed")
        return jsonify(ok=False, message="Couldn't render a preview image. Your text is still saved."), 200

    images = ["data:image/png;base64," + base64.b64encode(p).decode("ascii") for p in pages]
    return jsonify(ok=True, images=images)


# --------------------------------------------------------------------------
# photo
# --------------------------------------------------------------------------
@cv_studio_bp.route("/cv/studio/photo", methods=["POST"])
@login_required
def cv_studio_photo():
    if not csrf_ok():
        return csrf_bounce(url_for("cv_studio.cv_studio_edit"))
    f = request.files.get("photo")
    if not f or not f.filename:
        flash("Choose a photo first.", "warning")
        return redirect(url_for("cv_studio.cv_studio_edit"))

    raw = f.read(MAX_PHOTO_BYTES + 1)
    if len(raw) > MAX_PHOTO_BYTES:
        flash("That photo is too large (max 4 MB).", "warning")
        return redirect(url_for("cv_studio.cv_studio_edit"))

    try:
        from io import BytesIO
        from PIL import Image, ImageOps
        img = Image.open(BytesIO(raw))
        img.verify()
        img = Image.open(BytesIO(raw))  # re-open: verify() consumes the parser
        img = ImageOps.exif_transpose(img)  # don't carry EXIF location/orientation data
        img = img.convert("RGB")
        img.thumbnail((600, 600))
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        content = out.getvalue()
    except Exception:
        flash("Couldn't read that as an image. Try a JPG or PNG.", "warning")
        return redirect(url_for("cv_studio.cv_studio_edit"))

    row = _photo_row()
    if not row:
        row = CVPhoto(user_id=current_user.id)
        db.session.add(row)
    row.content = content
    row.mime = "image/jpeg"
    db.session.commit()
    flash("Photo saved.", "success")
    return redirect(url_for("cv_studio.cv_studio_edit"))


@cv_studio_bp.route("/cv/studio/photo/remove", methods=["POST"])
@login_required
def cv_studio_photo_remove():
    if not csrf_ok():
        return csrf_bounce(url_for("cv_studio.cv_studio_edit"))
    row = _photo_row()
    if row:
        db.session.delete(row)
        db.session.commit()
    return redirect(url_for("cv_studio.cv_studio_edit"))


@cv_studio_bp.route("/cv/studio/photo.jpg")
@login_required
def cv_studio_photo_serve():
    row = _photo_row()
    if not row:
        return "", 404
    return send_file(io.BytesIO(row.content), mimetype=row.mime, max_age=60)


# --------------------------------------------------------------------------
# download / publish
# --------------------------------------------------------------------------
def _fallback_reportlab(data, path_or_buf):
    """If pdflatex isn't installed (e.g. a learner's own machine), still hand
    back *something* usable rather than erroring out — the plain reportlab
    'classic' layout, built from the same data."""
    flat = dict(data)
    flat["skills"] = data.get("skills", [])
    flat["languages"] = [l["name"] for l in data.get("languages", []) if isinstance(l, dict)]
    cv_pdf.build_cv_pdf(flat, "classic", path_or_buf)


@cv_studio_bp.route("/cv/studio/download")
@login_required
def cv_studio_download():
    profile = _profile()
    if not profile or not profile.template.startswith("latex:"):
        return redirect(url_for("cv_studio.cv_studio_edit"))
    template_id = profile.template.split(":", 1)[1]
    data = _load_data(profile)
    buf = io.BytesIO()
    build_latex_cv_pdf(current_user.id, data, template_id, buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="My_CV.pdf")


@cv_studio_bp.route("/cv/studio/publish", methods=["POST"])
@login_required
def cv_studio_publish():
    if not csrf_ok():
        return csrf_bounce(url_for("cv_studio.cv_studio_edit"))
    profile = _profile()
    if not profile or not profile.template.startswith("latex:"):
        flash("Finish your CV first.", "warning")
        return redirect(url_for("cv_studio.cv_studio_edit"))
    template_id = profile.template.split(":", 1)[1]
    data = _load_data(profile)
    if cv_problems_latex(data):
        flash("Finish your CV first.", "warning")
        return redirect(url_for("cv_studio.cv_studio_edit"))

    from datetime import datetime
    import re
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "documents")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = re.sub(r"[^A-Za-z0-9]+", "_", data.get("full_name") or current_user.full_name or "My").strip("_")[:40] or "My"
    filename = f"{current_user.id}_{BUILDER_TAG}_{stamp}_{label}_CV.pdf"
    path = os.path.join(folder, filename)
    build_latex_cv_pdf(current_user.id, data, template_id, path)

    for old in Document.query.filter(
        Document.user_id == current_user.id, Document.is_active.is_(True),
        Document.filename.like(f"{current_user.id}\\_{BUILDER_TAG}\\_%", escape="\\"),
    ).all():
        old.is_active = False

    doc = Document(user_id=current_user.id, document_type="cv", filename=filename,
                    original_filename=f"{label}_CV.pdf", file_path=path,
                    file_size=os.path.getsize(path))
    db.session.add(doc)
    db.session.commit()

    if session.get("apply_ids"):
        flash("CV saved. It's ticked and ready to send.", "success")
        return redirect(url_for("public.confirm"))
    flash("CV saved. It will be attached when you apply.", "success")
    return redirect(url_for("document_center"))
