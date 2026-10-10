"""Bahrain Jobs server: serves the site and a /api/jobs endpoint backed by a free job API.

Setup: copy .env.example to .env, add ONE key, then run:  python server.py
Providers (free tiers): Jooble (JOOBLE_API_KEY) or JSearch on RapidAPI (RAPIDAPI_KEY).
"""
import json, os, re, time, urllib.request, urllib.error
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_SECONDS = 15 * 60  # protects free-tier quotas
PORT = int(os.environ.get("PORT", 8000))


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def http_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "bahrain-jobs/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def guess_category(text):
    rules = [("Technology", "software|developer|engineer.*(it|software)|data |devops|it |network|cyber"),
             ("Finance", "account|finance|audit|bank|financial|treasury"),
             ("Healthcare", "nurse|doctor|medical|pharmac|clinic|health"),
             ("Engineering", "engineer|civil|mechanical|electrical|technician"),
             ("Marketing", "market|brand|social media|content|designer|seo"),
             ("Education", "teacher|lecturer|tutor|school|academic"),
             ("Hospitality", "hotel|chef|restaurant|waiter|front desk|guest"),
             ("Logistics", "logistic|driver|warehouse|supply chain|shipping"),
             ("Customer Service", "customer|support|call cent|receptionist"),
             ("Sales", "sales|business development|account manager")]
    t = text.lower()
    for name, pat in rules:
        if re.search(pat, t):
            return name
    return "Other"


def norm_type(s):
    s = (s or "").lower().replace("_", " ").replace("-", " ")
    for key, val in [("part", "Part-time"), ("contract", "Contract"), ("intern", "Internship"), ("temp", "Contract"), ("free", "Freelance")]:
        if key in s:
            return val
    return "Full-time"


def fetch_jooble(key):
    out = []
    for kw in ("", ):
        data = http_json(f"https://jooble.org/api/{key}", {"keywords": kw, "location": "Bahrain", "page": 1})
        for i, j in enumerate(data.get("jobs", [])):
            desc = strip_html(j.get("snippet"))
            out.append({"id": f"j{j.get('id', i)}", "title": strip_html(j.get("title")), "company": j.get("company") or j.get("source") or "Company",
                        "area": (j.get("location") or "Bahrain").split(",")[0].strip() or "Bahrain",
                        "category": guess_category(j.get("title", "") + " " + desc), "type": norm_type(j.get("type")),
                        "salary": j.get("salary") or "Not stated", "posted": (j.get("updated") or "")[:10] or datetime.now().strftime("%Y-%m-%d"),
                        "description": desc, "applyUrl": j.get("link")})
    return out


def fetch_jsearch(key):
    out = []
    for page in (1, 2):
        url = f"https://jsearch.p.rapidapi.com/search?query=jobs%20in%20Bahrain&country=bh&page={page}&num_pages=1&date_posted=month"
        data = http_json(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"})
        for j in data.get("data", []):
            lo, hi, cur = j.get("job_min_salary"), j.get("job_max_salary"), j.get("job_salary_currency")
            salary = f"{int(lo):,} - {int(hi):,} {cur or ''}".strip() if lo and hi else "Not stated"
            desc = strip_html(j.get("job_description"))[:600]
            out.append({"id": j.get("job_id"), "title": j.get("job_title"), "company": j.get("employer_name") or "Company",
                        "area": j.get("job_city") or "Bahrain", "category": guess_category((j.get("job_title") or "") + " " + desc),
                        "type": norm_type(j.get("job_employment_type")), "salary": salary,
                        "posted": (j.get("job_posted_at_datetime_utc") or datetime.now(timezone.utc).isoformat())[:10],
                        "description": desc, "applyUrl": j.get("job_apply_link")})
    return out


_cache = {"t": 0, "jobs": None}


def get_jobs():
    if _cache["jobs"] is not None and time.time() - _cache["t"] < CACHE_SECONDS:
        return _cache["jobs"]
    if os.environ.get("JOOBLE_API_KEY"):
        jobs = fetch_jooble(os.environ["JOOBLE_API_KEY"])
    elif os.environ.get("RAPIDAPI_KEY"):
        jobs = fetch_jsearch(os.environ["RAPIDAPI_KEY"])
    else:
        raise RuntimeError("No API key configured. See .env.example")
    seen, unique = set(), []
    for j in jobs:  # drop duplicates and entries missing core fields
        k = (j["title"], j["company"])
        if j["title"] and k not in seen:
            seen.add(k)
            unique.append(j)
    _cache.update(t=time.time(), jobs=unique)
    return unique


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/jobs":
            try:
                body, status = json.dumps({"jobs": get_jobs()}).encode(), 200
            except Exception as e:  # surface a readable message to the page
                body, status = json.dumps({"error": str(e)}).encode(), 502
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if os.path.basename(self.path.split("?")[0]) in (".env", "server.py", ".env.example"):
            self.send_error(404)  # never serve secrets or source
            return
        super().do_GET()


if __name__ == "__main__":
    load_env()
    print(f"Bahrain Jobs running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
