"""LaTeX CV engine: safe templating, sandboxed compilation, cached PDF->PNG previews.

Nothing here trusts the learner's text. Every value that reaches a .tex file goes
through tex_escape() (or a value built entirely server-side, e.g. an icon macro
picked from a fixed allow-list). pdflatex itself runs with -no-shell-escape, a
hard timeout, a scratch working directory that is deleted straight after, and a
cap on how many compiles can run at once.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections import OrderedDict

from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "cv_latex_templates")
CACHE_DIR = os.path.join(BASE_DIR, "instance", "cv_cache")
CACHE_MAX_FILES = 300          # oldest evicted past this
COMPILE_TIMEOUT = 20           # seconds
MAX_CONCURRENT_COMPILES = 2    # per worker process
MIN_SECONDS_BETWEEN_COMPILES_PER_USER = 1.4

_compile_slots = threading.Semaphore(MAX_CONCURRENT_COMPILES)
_last_compile_at = {}          # user_id -> monotonic time, best-effort in-process throttle
_throttle_lock = threading.Lock()


class LatexBuildError(Exception):
    """pdflatex ran but the document didn't compile (bad input slipped past validation, etc)."""


class RateLimited(Exception):
    pass


def pdflatex_available():
    return shutil.which("pdflatex") is not None


# --------------------------------------------------------------------------
# icon pack — trusted, server-authored TikZ/pifont macros only. Never let user
# input choose anything but one of these fixed ids; the macro body itself
# never contains user text.
# --------------------------------------------------------------------------
ICON_PACK_TEX = r"""
\newcommand{\icphone}{\begin{tikzpicture}[baseline=-0.55ex,scale=0.048,rotate=-30]
  \draw[accent,line width=1.5pt,line cap=round]
    (0,0) .. controls (0.3,-1.9) and (2.1,-2.8) .. (3.6,-1.9);
  \fill[accent] (0,0) circle (0.85);
  \fill[accent] (3.6,-1.9) circle (0.85);
\end{tikzpicture}}
\newcommand{\icat}{\begin{tikzpicture}[baseline=-0.6ex,scale=0.046]
  \draw[accent,line width=0.9pt] (0,0) circle (3.2);
  \node[accent,font=\fontsize{5}{5}\selectfont] at (0,-0.1) {@};
\end{tikzpicture}}
\newcommand{\iclink}{\begin{tikzpicture}[baseline=-0.6ex,scale=0.048,rotate=-40]
  \draw[accent,line width=0.85pt,rounded corners=0.85pt] (-2.3,-0.85) rectangle (0.45,0.85);
  \draw[accent,line width=0.85pt,rounded corners=0.85pt] (-0.45,-0.85) rectangle (2.3,0.85);
\end{tikzpicture}}
\newcommand{\icpin}{\begin{tikzpicture}[baseline=-0.6ex,scale=0.042]
  \fill[accent] (0,-3.2) .. controls (-2.6,-0.6) and (-2.8,0.6) .. (-2.0,1.8)
    .. controls (-1.2,3.0) and (1.2,3.0) .. (2.0,1.8)
    .. controls (2.8,0.6) and (2.6,-0.6) .. (0,-3.2) -- cycle;
  \fill[white] (0,1.35) circle (0.85);
\end{tikzpicture}}
\newcommand{\icflag}{\raisebox{-0.15ex}{\textcolor{accent}{\fontsize{7.6}{7.6}\selectfont\ding{73}}}}
\newcommand{\iccal}{\begin{tikzpicture}[baseline=-0.55ex,scale=0.042]
  \draw[meta,line width=0.9pt] (-2.6,-2.4) rectangle (2.6,2.0);
  \fill[meta] (-2.6,1.0) rectangle (2.6,2.0);
  \draw[meta,line width=0.9pt,line cap=round] (-1.4,2.0) -- (-1.4,3.0);
  \draw[meta,line width=0.9pt,line cap=round] ( 1.4,2.0) -- ( 1.4,3.0);
  \foreach \x in {-1.4,0,1.4}\foreach \y in {-0.2,-1.5}{\fill[meta] (\x,\y) circle (0.32);}
\end{tikzpicture}}
\newcommand{\icpingray}{\begin{tikzpicture}[baseline=-0.6ex,scale=0.040]
  \fill[meta] (0,-3.2) .. controls (-2.6,-0.6) and (-2.8,0.6) .. (-2.0,1.8)
    .. controls (-1.2,3.0) and (1.2,3.0) .. (2.0,1.8)
    .. controls (2.8,0.6) and (2.6,-0.6) .. (0,-3.2) -- cycle;
  \fill[white] (0,1.35) circle (0.85);
\end{tikzpicture}}
\newcommand{\iccode}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.11]
  \draw[accent,line width=1.5pt,line join=round,line cap=round]
    (-1.4,1.4) -- (-3.0,0) -- (-1.4,-1.4);
  \draw[accent,line width=1.5pt,line join=round,line cap=round]
    ( 1.4,1.4) -- ( 3.0,0) -- ( 1.4,-1.4);
  \draw[accent,line width=1.5pt,line cap=round] (-0.7,-1.8) -- (0.7,1.8);
\end{tikzpicture}}
\newcommand{\icserver}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.105]
  \foreach \y in {1.5,-1.0}{
    \draw[accent,line width=1.3pt,rounded corners=0.6pt] (-3.0,\y) rectangle (3.0,\y+1.6);
    \fill[accent] (-1.9,\y+0.8) circle (0.32);
    \draw[accent,line width=1.1pt,line cap=round] (0.6,\y+0.8) -- (2.1,\y+0.8);}
  \draw[accent,line width=1.3pt,rounded corners=0.6pt] (-3.0,-3.5) rectangle (3.0,-1.9);
  \fill[accent] (-1.9,-2.7) circle (0.32);
  \draw[accent,line width=1.1pt,line cap=round] (0.6,-2.7) -- (2.1,-2.7);
\end{tikzpicture}}
\newcommand{\icdb}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.105]
  \draw[accent,line width=1.3pt] (-2.6,2.1) arc (180:360:2.6 and 1.0);
  \draw[accent,line width=1.3pt] (-2.6,2.1) arc (180:0:2.6 and 1.0);
  \draw[accent,line width=1.3pt] (-2.6,2.1) -- (-2.6,-2.1);
  \draw[accent,line width=1.3pt] ( 2.6,2.1) -- ( 2.6,-2.1);
  \draw[accent,line width=1.3pt] (-2.6,-2.1) arc (180:360:2.6 and 1.0);
  \draw[accent,line width=1.3pt] (-2.6,0.0) arc (180:360:2.6 and 1.0);
\end{tikzpicture}}
\newcommand{\icai}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.118]
  \fill[accent] (-0.6,1.0) .. controls (0.2,1.2) and (0.5,1.6) .. (0.7,3.0)
    .. controls (0.9,1.6) and (1.2,1.2) .. (2.0,1.0)
    .. controls (1.2,0.8) and (0.9,0.4) .. (0.7,-1.0)
    .. controls (0.5,0.4) and (0.2,0.8) .. (-0.6,1.0) -- cycle;
  \fill[accent] (-3.2,-1.6) .. controls (-2.6,-1.5) and (-2.4,-1.2) .. (-2.2,-0.2)
    .. controls (-2.0,-1.2) and (-1.8,-1.5) .. (-1.2,-1.6)
    .. controls (-1.8,-1.7) and (-2.0,-2.0) .. (-2.2,-3.0)
    .. controls (-2.4,-2.0) and (-2.6,-1.7) .. (-3.2,-1.6) -- cycle;
\end{tikzpicture}}
\newcommand{\icgrid}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.105]
  \draw[accent,line width=1.3pt,rounded corners=0.5pt] (-3.0,0.3) rectangle (-0.4,2.9);
  \draw[accent,line width=1.3pt,rounded corners=0.5pt] ( 0.4,0.3) rectangle ( 3.0,2.9);
  \draw[accent,line width=1.3pt,rounded corners=0.5pt] (-3.0,-2.9) rectangle (-0.4,-0.3);
  \fill[accent,rounded corners=0.5pt] ( 0.4,-2.9) rectangle ( 3.0,-0.3);
\end{tikzpicture}}
\newcommand{\icform}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.10]
  \draw[accent,line width=1.4pt,rounded corners=0.8pt] (-3.0,-2.6) rectangle (3.0,2.6);
  \fill[accent] (-3.0,1.2) rectangle (3.0,2.6);
  \draw[accent,line width=1.3pt,line cap=round] (-1.9,0.1) -- (1.9,0.1);
  \draw[accent,line width=1.3pt,line cap=round] (-1.9,-1.4) -- (0.6,-1.4);
\end{tikzpicture}}
\newcommand{\iclist}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.10]
  \draw[accent,line width=1.4pt,rounded corners=0.8pt] (-3.0,-2.6) rectangle (3.0,2.6);
  \fill[accent] (-3.0,1.3) rectangle (3.0,2.6);
  \draw[accent,line width=1.3pt,line cap=round] (-1.9,0.2) -- (1.9,0.2);
  \draw[accent,line width=1.3pt,line cap=round] (-1.9,-1.2) -- (1.9,-1.2);
\end{tikzpicture}}
\newcommand{\icaward}{\raisebox{-0.1ex}{\textcolor{accent}{\fontsize{9}{9}\selectfont\ding{72}}}}
\newcommand{\icbriefcase}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.105]
  \draw[accent,line width=1.3pt,rounded corners=0.6pt] (-3.0,-2.0) rectangle (3.0,1.6);
  \draw[accent,line width=1.3pt,rounded corners=0.8pt] (-1.4,1.6) rectangle (1.4,2.9);
  \draw[accent,line width=1.1pt] (-3.0,-0.2) -- (3.0,-0.2);
\end{tikzpicture}}
\newcommand{\icglobe}{\begin{tikzpicture}[baseline=-0.9ex,scale=0.105]
  \draw[accent,line width=1.2pt] (0,0) circle (3.0);
  \draw[accent,line width=0.9pt] (-3.0,0) -- (3.0,0);
  \draw[accent,line width=0.9pt] (0,0) ellipse (1.1 and 3.0);
\end{tikzpicture}}
\newcommand{\iccheck}{\raisebox{-0.1ex}{\textcolor{accent}{\fontsize{8.5}{8.5}\selectfont\ding{51}}}}
"""

ICONS = OrderedDict([
    ("none", "No icon"),
    ("briefcase", "Briefcase \\icbriefcase"),
    ("code", "Code \\iccode"),
    ("server", "Server \\icserver"),
    ("db", "Database \\icdb"),
    ("ai", "AI / sparkle \\icai"),
    ("grid", "Grid \\icgrid"),
    ("form", "Form \\icform"),
    ("list", "Checklist \\iclist"),
    ("award", "Award \\icaward"),
    ("globe", "Globe \\icglobe"),
    ("check", "Check \\iccheck"),
    ("flag", "Star \\icflag"),
])
ICON_MACRO = {k: ("\\ic" + k if k not in ("none", "flag") else ("" if k == "none" else "\\icflag"))
              for k in ICONS}


# --------------------------------------------------------------------------
# escaping — the only thing standing between a learner's text box and \write18
# --------------------------------------------------------------------------
_TEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "%": r"\%",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_TEX_SPECIAL_RE = re.compile("|".join(re.escape(k) for k in _TEX_SPECIAL))


def tex_escape(value):
    """Escape plain text for safe use inside a .tex document. Always use this on
    anything a user typed; never pass user text through the `raw` filter."""
    if value is None:
        return ""
    text = str(value)
    text = _TEX_SPECIAL_RE.sub(lambda m: _TEX_SPECIAL[m.group(0)], text)
    # Collapse to single paragraphs; a hard linebreak macro is opt-in via tex_lines().
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def tex_lines(value):
    """Escape each line of a textarea and join with a LaTeX linebreak."""
    if not value:
        return ""
    lines = [tex_escape(ln) for ln in str(value).replace("\r\n", "\n").split("\n")]
    lines = [ln for ln in lines if ln]
    return r" \\ ".join(lines)


def tex_url(value):
    """Escape for use inside \\href{...}{...}'s URL argument (no backslash-escaping
    of the url itself needed beyond stripping anything that could close the brace)."""
    if not value:
        return ""
    return re.sub(r"[{}\\]", "", str(value)).strip()


# --------------------------------------------------------------------------
# Jinja environment with LaTeX-safe delimiters
# --------------------------------------------------------------------------
_env = SandboxedEnvironment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    block_start_string=r"\BLOCK{", block_end_string="}",
    variable_start_string=r"\VAR{", variable_end_string="}",
    comment_start_string=r"\#{", comment_end_string="}",
    line_statement_prefix="%%",
    line_comment_prefix="%#",
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)
_env.filters["e"] = tex_escape
_env.filters["lines"] = tex_lines
_env.filters["url"] = tex_url


def icon_macro(icon_id):
    """Map a validated icon id (one of ICONS' keys) to its trusted macro call.
    Never feed this anything but a key already checked against ICONS — it is
    the one place a bad id would turn into a bare \\undefined macro name."""
    if icon_id not in ICONS or icon_id == "none":
        return ""
    return "\\ic" + icon_id if icon_id != "flag" else "\\icflag"


_env.globals["icon"] = icon_macro
_env.globals["icon_pack"] = ICON_PACK_TEX


def render_tex(template_file, context):
    tmpl = _env.get_template(template_file)
    return tmpl.render(**context)


# --------------------------------------------------------------------------
# compilation
# --------------------------------------------------------------------------
def _cache_key(template_file, context, assets_sig):
    payload = json.dumps(
        {"t": template_file, "c": context, "a": assets_sig}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def _cache_path(key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, key + ".pdf")


def _evict_cache():
    try:
        files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)]
    except OSError:
        return
    if len(files) <= CACHE_MAX_FILES:
        return
    files.sort(key=lambda p: os.path.getmtime(p))
    for p in files[: len(files) - CACHE_MAX_FILES]:
        try:
            os.remove(p)
        except OSError:
            pass


def _throttle(user_id):
    if user_id is None:
        return
    with _throttle_lock:
        now = time.monotonic()
        last = _last_compile_at.get(user_id, 0)
        if now - last < MIN_SECONDS_BETWEEN_COMPILES_PER_USER:
            raise RateLimited("Give it a second between previews.")
        _last_compile_at[user_id] = now


def compile_pdf(template_file, context, assets=None, user_id=None, use_cache=True):
    """Render + compile a CV to PDF bytes. `assets` is an optional
    {dest_filename: bytes} map of trusted binary files (e.g. a resized photo)
    copied into the compile sandbox. Returns pdf bytes. Raises LatexBuildError
    or RateLimited."""
    assets = assets or {}
    assets_sig = {name: hashlib.sha1(data).hexdigest() for name, data in assets.items()}
    key = _cache_key(template_file, context, assets_sig)
    cache_file = _cache_path(key)
    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            return f.read()

    _throttle(user_id)
    tex_source = render_tex(template_file, context)

    acquired = _compile_slots.acquire(timeout=COMPILE_TIMEOUT)
    if not acquired:
        raise RateLimited("The CV builder is busy — try again in a moment.")
    try:
        workdir = tempfile.mkdtemp(prefix="cvtex_")
        try:
            for name, data in assets.items():
                safe_name = os.path.basename(name)
                with open(os.path.join(workdir, safe_name), "wb") as f:
                    f.write(data)
            tex_path = os.path.join(workdir, "cv.tex")
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(tex_source)

            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": workdir}
            try:
                proc = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                     "-no-shell-escape", "-file-line-error", "cv.tex"],
                    cwd=workdir, env=env, capture_output=True, text=True,
                    timeout=COMPILE_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                raise LatexBuildError("The CV took too long to generate. Try shortening a section.")

            pdf_path = os.path.join(workdir, "cv.pdf")
            if proc.returncode != 0 or not os.path.exists(pdf_path):
                log = (proc.stdout or "") + (proc.stderr or "")
                raise LatexBuildError(_friendly_latex_error(log))

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    finally:
        _compile_slots.release()

    if use_cache:
        try:
            with open(cache_file, "wb") as f:
                f.write(pdf_bytes)
            _evict_cache()
        except OSError:
            pass
    return pdf_bytes


def _friendly_latex_error(log):
    if "Dimension too large" in log or "TeX capacity exceeded" in log:
        return "One of your sections is too long for the page. Try trimming it."
    if "Undefined control sequence" in log:
        return "Something in your text broke the CV layout. Remove any unusual symbols and try again."
    return "Couldn't generate the CV from that text. Try removing unusual symbols and try again."


# --------------------------------------------------------------------------
# identity-mismatch stamp — a visible flag, not a block. cv_studio_routes
# decides *whether* to call this (cv_latex_data.identity_name_mismatch);
# this just burns a diagonal red stamp into every page, the same way on the
# live preview and the final download/published PDF.
# --------------------------------------------------------------------------
def stamp_identity_mismatch(pdf_bytes, label="NAME DOES NOT MATCH ACCOUNT"):
    """Burn a big, rough, ink-stamp-style diagonal across every page, corner to
    corner -- not a clean watermark. Two overlapping passes (a slightly offset
    "ghost" re-press) plus a scatter of punched-out highlights along the main
    line fake the uneven, gappy look of a real rubber stamp, since there's no
    distressed/stamp font available to render with directly."""
    import math
    import random
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        fontname = "hebo"  # built-in Helvetica-Bold, always available
        red = (0.80, 0.0, 0.03)  # alarming, saturated red -- not a pastel

        for page in doc:
            rect = page.rect
            cx, cy = rect.width / 2, rect.height / 2
            diag = math.hypot(rect.width, rect.height)
            angle = math.degrees(math.atan2(rect.height, rect.width))  # true corner-to-corner
            rot = fitz.Matrix(1, 1).prerotate(-angle)
            pivot = fitz.Point(cx, cy)

            unit_w = fitz.get_text_length(label, fontname=fontname, fontsize=1)
            fontsize = (diag * 0.92) / unit_w
            width = fitz.get_text_length(label, fontname=fontname, fontsize=fontsize)
            origin = fitz.Point(cx - width / 2, cy + fontsize * 0.32)
            morph = (pivot, rot)

            # main ink pass
            page.insert_text(origin, label, fontsize=fontsize, fontname=fontname,
                              color=red, fill_opacity=0.74, morph=morph, overlay=True)
            # slightly offset "re-pressed" ghost pass -- a stamp is never pressed twice
            # in exactly the same spot
            ghost = fitz.Point(origin.x + fontsize * 0.028, origin.y - fontsize * 0.022)
            page.insert_text(ghost, label, fontsize=fontsize, fontname=fontname,
                              color=red, fill_opacity=0.30, morph=(pivot, rot), overlay=True)

            sub = "VERIFY BEFORE USING THIS CV"
            sub_size = fontsize * 0.26
            sub_w = fitz.get_text_length(sub, fontname=fontname, fontsize=sub_size)
            sub_origin = fitz.Point(cx - sub_w / 2, cy + fontsize * 0.32 + fontsize * 0.62)
            page.insert_text(sub_origin, sub, fontsize=sub_size, fontname=fontname,
                              color=red, fill_opacity=0.55, morph=morph, overlay=True)

            # worn-ink texture: punch small white gaps out of the main line so it
            # reads as pressed rubber, not printed vector text
            rnd = random.Random(1337)  # deterministic -- same stamp look every render
            gap_count = max(18, int(width / 22))
            for _ in range(gap_count):
                frac_x = rnd.random()
                gx = origin.x + frac_x * width + rnd.uniform(-fontsize * 0.04, fontsize * 0.04)
                gy = origin.y - fontsize * rnd.uniform(0.08, 0.68)
                p = pivot + (fitz.Point(gx, gy) - pivot) * rot
                r = fontsize * rnd.uniform(0.012, 0.045)
                page.draw_circle(p, r, color=None, fill=(1, 1, 1), fill_opacity=1, overlay=True)

            page.draw_rect(rect, color=red, width=max(3, rect.width * 0.008))
        return doc.tobytes(deflate=True, garbage=3)
    finally:
        doc.close()


# --------------------------------------------------------------------------
# preview images (PyMuPDF) — kept small and few, for prepaid-data mobile users
# --------------------------------------------------------------------------
def pdf_to_png_pages(pdf_bytes, dpi=108, max_pages=2):
    import fitz  # PyMuPDF

    out = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out.append(pix.tobytes("png"))
    finally:
        doc.close()
    return out
