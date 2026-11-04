"""Schema, validation and sample data for the LaTeX CV Studio.

Kept separate from cv_service.py (which still drives the older, reportlab-based
builder) so the two can evolve independently; a learner's CVProfile.template
field says which family (`classic|modern|minimal|creative` = reportlab,
`latex:<id>` = this one) is in charge of their saved data.
"""
import re
from collections import OrderedDict

from latex_engine import ICONS

MAX_EXP, MAX_EDU, MAX_SKILLS, MAX_LANGS, MAX_STRENGTHS = 8, 6, 20, 8, 6
ACCENTS = OrderedDict([
    ("blue", "#2C9FFF"), ("teal", "#12B5A6"), ("violet", "#7C5CFC"),
    ("rose", "#F0527A"), ("amber", "#E08A00"), ("ink", "#111111"),
])

LATEX_TEMPLATES = OrderedDict([
    ("sidebar_pro", {
        "name": "Sidebar Pro",
        "file": "sidebar_pro.tex.jinja",
        "blurb": "Two-column, photo + icons + a skills sidebar. The one that gets noticed.",
        "photo": True, "icons": True, "donut": True, "pages": 2,
    }),
    ("bold_band", {
        "name": "Bold Band",
        "file": "bold_band.tex.jinja",
        "blurb": "A bold colour header, single column, timeline-style experience.",
        "photo": False, "icons": True, "donut": False, "pages": 1,
    }),
    ("minimal_serif", {
        "name": "Minimal ATS",
        "file": "minimal_serif.tex.jinja",
        "blurb": "Plain serif, no colour, no icons — built to sail through ATS scanners.",
        "photo": False, "icons": False, "donut": False, "pages": 1,
    }),
])


def _s(value, limit):
    return re.sub(r"[ \t]+", " ", (value or "").replace("\r", "")).strip()[:limit]


def _list(value, max_items, item_limit):
    parts = re.split(r"[,\n;]+", value or "")
    out = []
    for p in parts:
        p = _s(p, item_limit)
        if p and p.lower() not in (x.lower() for x in out):
            out.append(p)
    return out[:max_items]


def _icon(value):
    return value if value in ICONS else "none"


def clean_cv_latex(form):
    """Posted form -> stored JSON. Mirrors cv_service.clean_cv's shape plus the
    extra fields the LaTeX templates use (icons, accent, strengths/achievements,
    language proficiency, donut 'my time' breakdown)."""
    f = form.getlist
    experience = []
    for role, company, start, end, details, icn in zip(
        f("exp_role"), f("exp_company"), f("exp_start"), f("exp_end"),
        f("exp_details"), f("exp_icon") or [""] * len(f("exp_role")),
    ):
        item = {"role": _s(role, 80), "company": _s(company, 80), "start": _s(start, 20),
                "end": _s(end, 20), "details": _s(details, 500), "icon": _icon(icn)}
        if item["role"] or item["company"]:
            experience.append(item)

    education = []
    for qual, inst, year, details in zip(
        f("edu_qualification"), f("edu_institution"), f("edu_year"), f("edu_details")
    ):
        item = {"qualification": _s(qual, 100), "institution": _s(inst, 100),
                "year": _s(year, 20), "details": _s(details, 300)}
        if item["qualification"] or item["institution"]:
            education.append(item)

    strengths = []
    for title, body, icn in zip(
        f("str_title"), f("str_body"), f("str_icon") or [""] * len(f("str_title"))
    ):
        title, body = _s(title, 60), _s(body, 220)
        if title or body:
            strengths.append({"title": title, "body": body, "icon": _icon(icn)})

    time_split = []
    for label, pct in zip(f("time_label"), f("time_pct")):
        label = _s(label, 40)
        try:
            pct = max(0, min(100, int(float(pct))))
        except (TypeError, ValueError):
            pct = 0
        if label and pct:
            time_split.append({"label": label, "pct": pct})

    languages = []
    for raw in _list(form.get("languages"), MAX_LANGS, 40):
        if ":" in raw:
            name, level = raw.split(":", 1)
        else:
            name, level = raw, ""
        languages.append({"name": _s(name, 30), "level": _s(level, 20)})

    return {
        "full_name": _s(form.get("full_name"), 80),
        "job_title": _s(form.get("job_title"), 80),
        "phone": _s(form.get("phone"), 30),
        "email": _s(form.get("email"), 120),
        "location": _s(form.get("location"), 80),
        "linkedin": _s(form.get("linkedin"), 160),
        "portfolio": _s(form.get("portfolio"), 160),
        "nationality": _s(form.get("nationality"), 40),
        "summary": _s(form.get("summary"), 600),
        "experience": experience[:MAX_EXP],
        "education": education[:MAX_EDU],
        "strengths": strengths[:MAX_STRENGTHS],
        "skills": _list(form.get("skills"), MAX_SKILLS, 40),
        "languages": languages[:MAX_LANGS],
        "licence": _s(form.get("licence"), 20),
        "availability": _s(form.get("availability"), 40),
        "time_split": time_split[:6],
        "accent": form.get("accent") if form.get("accent") in ACCENTS else "blue",
        "show_icons": bool(form.get("show_icons")),
        "show_photo": bool(form.get("show_photo")),
    }


def cv_problems_latex(data):
    problems = []
    if not data.get("full_name"):
        problems.append("Add your full name.")
    if not data.get("phone") and not data.get("email"):
        problems.append("Add a phone number or email.")
    if not data.get("experience") and not data.get("education"):
        problems.append("Add at least your school or one piece of experience.")
    return problems


def starter_data_latex(user):
    return {
        "full_name": user.full_name or "", "email": user.email or "", "phone": user.phone or "",
        "experience": [], "education": [], "strengths": [], "skills": [], "languages": [],
        "time_split": [], "accent": "blue", "show_icons": True, "show_photo": False,
    }


def _name_tokens(name):
    name = (name or "").lower()
    name = re.sub(r"[^a-z\s]", " ", name)
    return {t for t in name.split() if len(t) > 1}


def identity_name_mismatch(cv_full_name, account_full_name):
    """Fraud-prevention signal for CV Studio: does the name typed into the CV
    share no resemblance at all with the name on the account paying for it?
    A learner filling the CV in for themselves -- under a maiden name, a
    nickname, reordered names, a middle name dropped -- will always share at
    least one name token with their account, so this only fires when the two
    names look like genuinely different people. It never blocks saving or
    generating the CV; callers use it purely to decide whether to stamp the
    resulting PDF (see latex_engine.stamp_identity_mismatch)."""
    cv_tokens = _name_tokens(cv_full_name)
    account_tokens = _name_tokens(account_full_name)
    if not cv_tokens or not account_tokens:
        return False
    return cv_tokens.isdisjoint(account_tokens)


def sample_data_latex(show_photo=False):
    """A realistic, deliberately one-page-sized 'John Doe' CV used to render
    real preview thumbnails for the template picker (so a learner sees an
    actual filled CV, not a blank shell) -- not shown to real learners as
    their own starting data, which stays empty via starter_data_latex above."""
    return {
        "full_name": "John Doe", "job_title": "Junior Software Developer",
        "phone": "071 234 5678", "email": "john.doe@example.com", "location": "Johannesburg, Gauteng",
        "linkedin": "linkedin.com/in/johndoe", "portfolio": "", "nationality": "South African",
        "summary": ("Recent IT graduate with hands-on experience building web applications in "
                     "Python and JavaScript, plus a year of freelance and volunteer work on the "
                     "side. Quick to learn new tools, comfortable working in a team, and looking "
                     "for a learnership where I can grow into a full-stack developer role."),
        "experience": [
            {"role": "IT Support Intern", "company": "Thusong Youth Centre", "start": "Jan 2025",
             "end": "Jun 2025", "details": "Resolved desktop and network issues for 40+ staff. "
             "Built a small Flask tool to log support tickets, cutting response time by a third. "
             "Trained two new volunteers on the helpdesk workflow.",
             "icon": "briefcase"},
            {"role": "Freelance Web Developer", "company": "Self-employed", "start": "2023",
             "end": "Present", "details": "Built and maintained sites for two local small "
             "businesses using HTML, CSS and JavaScript. Set up basic SEO and Google Business "
             "listings that grew one client's foot traffic noticeably.", "icon": "code"},
            {"role": "Volunteer Coding Tutor", "company": "Soshanguve Youth Hub", "start": "Mar 2024",
             "end": "Dec 2024", "details": "Ran weekend Python basics sessions for 15 high school "
             "learners. Put together simple exercises and marked homework every week.",
             "icon": "award"},
        ],
        "education": [
            {"qualification": "National Diploma: Information Technology", "institution": "TUT",
             "year": "2024", "details": "Majored in software development. Final-year project: a "
             "Flask-based helpdesk ticketing system."},
            {"qualification": "Google IT Support Professional Certificate", "institution": "Coursera",
             "year": "2023", "details": "Self-paced, completed alongside the diploma."},
            {"qualification": "National Senior Certificate", "institution": "Soshanguve Secondary",
             "year": "2021", "details": "Maths and Information Technology as subjects."},
        ],
        "strengths": [
            {"title": "Problem solver", "body": "Breaks a messy bug down and works it through calmly.", "icon": "check"},
            {"title": "Team player", "body": "Comfortable pairing and taking feedback well.", "icon": "globe"},
            {"title": "Fast learner", "body": "Picks up a new framework or tool in a few days, not weeks.", "icon": "award"},
        ],
        "skills": ["Python", "JavaScript", "Flask", "SQL", "Git", "HTML/CSS", "React (basics)", "Linux", "REST APIs"],
        "languages": [
            {"name": "English", "level": "Fluent"},
            {"name": "Zulu", "level": "Native"},
            {"name": "Afrikaans", "level": "Conversational"},
        ],
        "licence": "Code 8", "availability": "Immediate",
        "time_split": [{"label": "Coding", "pct": 50}, {"label": "Learning", "pct": 30}, {"label": "Support", "pct": 20}],
        "accent": "blue", "show_icons": True, "show_photo": show_photo,
    }


DONUT_COLORS = ["donutA", "donutB", "donutC", "donutD", "donutE", "donutF"]


def donut_segments(time_split):
    """Turn [{label, pct}] into TikZ-ready arc segments (start/end degrees,
    clockwise from 12 o'clock) plus a cycling colour name. Pure math — safe to
    compute once per render and hand straight to the template."""
    total = sum(max(0, s.get("pct", 0)) for s in time_split) or 1
    segs = []
    angle = 90.0  # start at 12 o'clock, TikZ angles go counter-clockwise
    for i, s in enumerate(time_split[:6]):
        pct = max(0, s.get("pct", 0))
        sweep = 360.0 * pct / total
        end = angle - sweep
        segs.append({
            "label": s.get("label", ""), "pct": round(100.0 * pct / total),
            "start": round(angle, 2), "end": round(end, 2),
            "color": DONUT_COLORS[i % len(DONUT_COLORS)],
            "badge": chr(65 + i),
        })
        angle = end
    return segs


SAMPLE_CV = {
    "full_name": "Jane Learner", "job_title": "Junior Software Developer",
    "phone": "+27 71 234 5678", "email": "jane.learner@example.com",
    "location": "Johannesburg, Gauteng", "linkedin": "linkedin.com/in/janelearner",
    "portfolio": "", "nationality": "South African",
    "summary": "Recent IT graduate with hands-on experience building web applications in "
               "React and Python during a 2026 learnership. Comfortable picking up new "
               "frameworks quickly and shipping features end to end.",
    "experience": [
        {"role": "Junior Developer (Learnership)", "company": "Tech Solutions SA",
         "start": "02/2026", "end": "Present",
         "details": "Built and shipped three internal tools in Flask and React; "
                     "paired with senior engineers on code review.", "icon": "code"},
        {"role": "IT Support Intern", "company": "Gauteng Retail Group",
         "start": "06/2025", "end": "12/2025",
         "details": "Resolved 40+ helpdesk tickets a week; set up new starter laptops "
                     "and accounts.", "icon": "server"},
    ],
    "education": [
        {"qualification": "Diploma in Information Technology", "institution": "UJ",
         "year": "2022 - 2024", "details": "Graduated with distinction in Web Development."},
        {"qualification": "Matric", "institution": "Hoërskool Centurion",
         "year": "2017 - 2021", "details": ""},
    ],
    "strengths": [
        {"title": "Fast learner", "body": "Picked up React from scratch in six weeks on the job.", "icon": "ai"},
        {"title": "Team player", "body": "Pairs well, gives and takes feedback in code review.", "icon": "list"},
    ],
    "skills": ["Python", "JavaScript", "React", "Flask", "SQL", "Git", "HTML/CSS"],
    "languages": [{"name": "English", "level": "Fluent"}, {"name": "Zulu", "level": "Home language"}],
    "licence": "Code 8 (EB)", "availability": "Immediately",
    "time_split": [{"label": "Feature work", "pct": 45}, {"label": "Learning", "pct": 25},
                   {"label": "Code review", "pct": 15}, {"label": "Support", "pct": 15}],
    "accent": "blue", "show_icons": True, "show_photo": False,
}
