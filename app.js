// Live jobs come from /api/jobs (server.py). If that fails, fall back to sample data in jobs.js.
let jobs = window.JOBS || [];
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fillSelect(el, label, key) {
  const vals = [...new Set(jobs.map(j => j[key]))].sort();
  el.innerHTML = `<option value="">All ${label}</option>` + vals.map(v => `<option>${esc(v)}</option>`).join("");
}
function init() {
  fillSelect($("category"), "categories", "category");
  fillSelect($("area"), "locations", "area");
  fillSelect($("type"), "types", "type");
  $("sJobs").textContent = jobs.length;
  $("sCos").textContent = new Set(jobs.map(j => j.company)).size;
  $("sAreas").textContent = new Set(jobs.map(j => j.area)).size;
  render();
}

function hue(s) {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `linear-gradient(135deg, hsl(${h} 70% 55%), hsl(${(h + 40) % 360} 70% 45%))`;
}

function daysAgo(d) {
  const n = Math.floor((Date.now() - new Date(d)) / 864e5);
  return n <= 0 ? "Today" : n === 1 ? "1 day ago" : `${n} days ago`;
}

function render() {
  const q = $("q").value.trim().toLowerCase();
  const f = { category: $("category").value, area: $("area").value, type: $("type").value };
  let out = jobs.filter(j =>
    (!q || `${j.title} ${j.company} ${j.description}`.toLowerCase().includes(q)) &&
    Object.entries(f).every(([k, v]) => !v || j[k] === v));
  out.sort($("sort").value === "az" ? (a, b) => a.title.localeCompare(b.title) : (a, b) => b.posted.localeCompare(a.posted));

  $("count").textContent = `${out.length} job${out.length === 1 ? "" : "s"} found`;
  $("list").innerHTML = out.length ? out.map(j => `
    <li class="job" tabindex="0" data-id="${j.id}">
      <div class="logo" style="background:${hue(j.company)}">${esc(j.company[0])}</div>
      <div>
        <h3>${esc(j.title)}</h3>
        <p class="co">${esc(j.company)}</p>
        <div class="tags"><span class="tag type">${esc(j.type)}</span><span class="tag">📍 ${esc(j.area)}</span><span class="tag">${esc(j.category)}</span></div>
      </div>
      <div class="side"><span class="pay">BHD ${esc(j.salary)}</span><span class="when">${daysAgo(j.posted)}</span></div>
    </li>`).join("") : `<li class="empty">No jobs match your search. Try clearing some filters.</li>`;
}

function openJob(id) {
  const j = jobs.find(x => x.id == id);
  if (!j) return;
  $("mTitle").textContent = j.title;
  $("mMeta").textContent = `${j.company} · ${j.area} · ${j.type} · BHD ${j.salary}`;
  $("mDesc").textContent = j.description;
  $("mApply").href = /^https?:\/\//.test(j.applyUrl) ? j.applyUrl : "#"; // block javascript: URLs from API data
  $("modal").hidden = false;
  $("close").focus();
}

$("searchForm").addEventListener("submit", e => { e.preventDefault(); render(); });
["q", "category", "area", "type", "sort"].forEach(id => $(id).addEventListener("input", render));
$("reset").addEventListener("click", () => { $("q").value = ""; ["category", "area", "type"].forEach(id => $(id).value = ""); render(); });
$("list").addEventListener("click", e => { const li = e.target.closest(".job"); if (li) openJob(li.dataset.id); });
$("list").addEventListener("keydown", e => { if (e.key === "Enter") { const li = e.target.closest(".job"); if (li) openJob(li.dataset.id); } });
$("close").addEventListener("click", () => $("modal").hidden = true);
$("modal").addEventListener("click", e => { if (e.target === $("modal")) $("modal").hidden = true; });
document.addEventListener("keydown", e => { if (e.key === "Escape") $("modal").hidden = true; });
$("year").textContent = new Date().getFullYear();

fetch("/api/jobs")
  .then(r => r.json().then(d => { if (!r.ok) throw new Error(d.error || r.status); return d; }))
  .then(d => { jobs = d.jobs; $("notice").textContent = "Live listings · salaries as advertised"; init(); })
  .catch(err => { console.warn("Using sample data:", err.message); $("notice").textContent = "Sample listings (live feed unavailable: " + err.message + ")"; init(); });
