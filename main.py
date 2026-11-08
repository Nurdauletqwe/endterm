import os, html, hmac, time
import mailer
from contextlib import contextmanager
from functools import wraps
import psycopg2, psycopg2.extras
from flask import (Flask, request, redirect, session, url_for, render_template_string,
                   flash, abort, jsonify)
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)       
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1")   
DB_URL = os.environ.get("DATABASE_URL", "dbname=docrequest user=postgres password=12345 host=localhost")
STATUSES = ["New", "In progress", "Ready", "Cancelled"]
STATUS_ICONS = {"New": "i-send", "In progress": "i-pending", "Ready": "i-check", "Cancelled": "i-cancel"}
EMAIL_DOMAIN = "@astanait.edu.kz"
app.jinja_env.globals["STATUS_ICONS"] = STATUS_ICONS

PAGE_SIZE = 20                                                  
PICKUP_SQL = "CASE WHEN p.point_id IS NULL THEN NULL ELSE p.block || ', room ' || p.room END"


@contextmanager
def db():
    con = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        with con, con.cursor() as cur:
            yield cur
    finally:
        con.close()


def login_required(role):
    def deco(f):
        @wraps(f)
        def wrap(*a, **k):
            if "uid" not in session:
                return redirect(url_for("login"))
            if session["role"] != role:
                abort(403)                      
            return f(*a, **k)
        return wrap
    return deco


MACROS = """
{% macro icon(name, before=False) -%}
{%- if before -%}<img class="icon-img" src="{{ url_for('static', filename='before/' ~ name ~ '.png') }}" width="18" height="18" alt="">
{%- else -%}<svg class="icon" aria-hidden="true" focusable="false"><use href="#{{ name }}"/></svg>{%- endif -%}
{%- endmacro %}
{% macro badge(s, before=False) -%}
<span class="status status-{{ s|lower|replace(' ', '-') }}">{{ icon(STATUS_ICONS[s], before) }} {{ s }}</span>
{%- endmacro %}
{% macro cancel_btn(r) -%}
{%- if r.status == 'New' -%}<form method="post" action="{{ url_for('cancel_request', rid=r.request_id) }}" class="cancel-form"><button class="btn btn-sm btn-outline-danger">Cancel</button></form>{%- endif -%}
{%- endmacro %}
{% macro req_row(r, before=False, fresh=False) -%}
<tr data-id="{{ r.request_id }}" data-status="{{ r.status }}"{% if fresh %} class="row-new"{% endif %}><td>{{ r.request_id }}</td><td>{{ r.name }}</td><td>{{ r.copies }}</td><td class="st">{{ badge(r.status, before) }}</td><td class="pk">{% if r.pickup %}{{ r.pickup }}{% else %}&mdash;{% endif %}</td><td>{{ r.created_at }}</td><td class="act">{{ cancel_btn(r) }}</td></tr>
{%- endmacro %}
"""

BASE = MACROS + """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DocRequest</title>
<link rel="icon" href="{{ url_for('static', filename='favicon.svg') }}" type="image/svg+xml">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
 .icon{width:1.1em;height:1.1em;vertical-align:-.15em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
 .icon-img{vertical-align:-.15em}
 .btn,.form-select,.form-control{min-height:44px}
 .status{display:inline-block;padding:.2rem .6rem;border-radius:1rem;font-weight:600;white-space:nowrap}
 .status-new{background:#fff3cd;color:#664d03}.status-in-progress{background:#cfe2ff;color:#084298}
 .status-ready{background:#d1e7dd;color:#0a3622}.status-cancelled{background:#f8d7da;color:#58151c}
 .hero{position:relative;max-width:720px;border-radius:.75rem;overflow:hidden;margin-bottom:1.5rem;color:#fff}
 .hero-img{display:block;width:100%;height:auto}
 .hero-text{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:1rem 1.25rem;
            background:linear-gradient(90deg,rgba(10,25,50,.86),rgba(10,25,50,.60))}
 .hero-text h1{font-size:clamp(1.25rem,5vw,1.9rem);margin:0 0 .25rem}.hero-text p{margin:0;max-width:60%;font-size:clamp(.8rem,2.6vw,1rem)}
 .toast-box{display:flex;gap:.75rem;align-items:center;justify-content:space-between;max-width:720px;margin-bottom:1rem;
            padding:.75rem 1rem;border-radius:.5rem;background:#d1e7dd;color:#0a3622;border:1px solid #a3cfbb;animation:slide-in .35s ease-out}
 .toast-box.toast-error{background:#f8d7da;color:#58151c;border-color:#f1aeb5}
 .row-new td{animation:flash 2.4s ease-out}
 .sound-switch{display:flex;align-items:center;gap:.75rem;min-height:44px;cursor:pointer}
 .sound-switch input{width:1.5rem;height:1.5rem;flex:none}
 .bar{height:1.1rem;background:#0d6efd;border-radius:.25rem}
 @keyframes slide-in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
 @keyframes flash{from{background:#cfe2ff}to{background:transparent}}
 @media (prefers-reduced-motion:reduce){.toast-box,.row-new td{animation:none}}
</style></head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0" aria-hidden="true" focusable="false">
 <symbol id="i-doc" viewBox="0 0 24 24"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h6M9.5 16h6"/></symbol>
 <symbol id="i-send" viewBox="0 0 24 24"><path d="M21 3 3 10.5l7 2.5 2.5 7z"/><path d="M10 13 21 3"/></symbol>
 <symbol id="i-pending" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></symbol>
 <symbol id="i-check" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/></symbol>
 <symbol id="i-cancel" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/></symbol>
 <symbol id="i-user" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/></symbol>
</svg>
<a class="visually-hidden-focusable" href="#main">Skip to content</a>
<nav class="navbar bg-light px-3">
 <a class="navbar-brand" href="{{ url_for('home') }}">
  {% if before %}<img src="{{ url_for('static', filename='before/logo.png') }}" width="168" height="40" alt="DocRequest, home">
  {% else %}<img src="{{ url_for('static', filename='logo.svg') }}" width="168" height="40" alt="DocRequest, home">{% endif %}
 </a>
 {% if session.uid %}<span>{{ icon('i-user', before) }} {{ session.name }} ({{ session.role }})
  {% if session.role == 'staff' %}&middot; <a href="{{ url_for('staff_list') }}">Requests</a> &middot; <a href="{{ url_for('staff_stats') }}">Statistics</a> &middot; <a href="{{ url_for('staff_lockers') }}">Lockers</a>{% endif %}
  &middot; <a href="{{ url_for('home') }}">Home</a> &middot; <a href="{{ url_for('logout') }}">Log out</a></span>{% endif %}
</nav>
<main id="main" class="container py-3">
{% for m in get_flashed_messages() %}<div class="alert alert-info" role="status">{{ m }}</div>{% endfor %}
{% block body %}{% endblock %}
</main></body></html>"""


def page(body, **ctx):
    before = request.args.get("media") == "before"                  
    poll = request.args.get("poll") != "off" and not before         
    return render_template_string(BASE.replace("{% block body %}{% endblock %}", body), before=before, poll=poll, **ctx)


def wants_json():
    return "application/json" in request.headers.get("Accept", "")


@app.route("/")
def home():
    if "uid" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("new_request" if session["role"] == "student" else "staff_list"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with db() as cur:
            cur.execute("""SELECT user_id, full_name, role FROM users
                           WHERE email = %s AND password_hash = crypt(%s, password_hash)""",
                        (request.form["email"].strip().lower(), request.form["password"]))
            u = cur.fetchone()
        if u:
            session.update(uid=u["user_id"], name=u["full_name"], role=u["role"])
            return redirect(url_for("home"))
        flash("Wrong e-mail or password")                          
    return page("""<h1 class="h4">Log in</h1>
      <form method="post" class="col-md-4">
       <label class="fw-bold" for="email">University e-mail</label>
       <input class="form-control mb-2" id="email" name="email" type="email" placeholder="name@astanait.edu.kz" required>
       <label class="fw-bold" for="password">Password</label>
       <input class="form-control mb-3" id="password" type="password" name="password" required>
       <button class="btn btn-primary w-100" style="height:48px">Log in</button></form>
      <p class="mt-3">No account? <a href="{{ url_for('register') }}">Register with your university e-mail</a></p>
      <p class="text-muted">Test: staff1@astanait.edu.kz / Test1234!</p>""")


@app.route("/register", methods=["GET", "POST"])
def register():
    with db() as cur:
        cur.execute("SELECT program_id, name FROM programs ORDER BY name")
        programs = cur.fetchall()
        form = {"email": "", "full_name": "", "program_id": ""}
        if request.method == "POST":
            form = {k: request.form.get(k, "").strip() for k in form}
            email, name, password = form["email"].lower(), form["full_name"][:100], request.form.get("password", "")
            valid_programs = {str(p["program_id"]) for p in programs}
            error = None
            if not email.endswith(EMAIL_DOMAIN) or len(email) == len(EMAIL_DOMAIN) or " " in email or len(email) > 120:
                error = "Use your university e-mail (name" + EMAIL_DOMAIN + ")"
            elif len(name) < 3:
                error = "Enter your full name"
            elif len(password) < 8:
                error = "Password must have at least 8 characters"
            elif form["program_id"] not in valid_programs:
                error = "Choose your study program"
            else:
                cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    error = "This e-mail is already registered"
            if error:
                flash(error)
            else:
                cur.execute("""INSERT INTO users (email, password_hash, full_name, role, program_id)
                               VALUES (%s, crypt(%s, gen_salt('bf')), %s, 'student', %s)""",
                            (email, password, name, int(form["program_id"])))
                flash("Account created. You can log in now.")
                return redirect(url_for("login"))
    return page("""<h1 class="h4">Register</h1>
      <form method="post" class="col-md-5">
       <label class="fw-bold" for="email">University e-mail</label>
       <input class="form-control mb-2" id="email" name="email" type="email" value="{{ form.email }}" placeholder="name@astanait.edu.kz" required>
       <label class="fw-bold" for="full_name">Full name</label>
       <input class="form-control mb-2" id="full_name" name="full_name" value="{{ form.full_name }}" required maxlength="100">
       <label class="fw-bold" for="program_id">Study program</label>
       <select class="form-select mb-2" id="program_id" name="program_id" required>
        <option value="">Choose...</option>
        {% for p in programs %}<option value="{{ p.program_id }}" {{ 'selected' if form.program_id == p.program_id|string }}>{{ p.name }}</option>{% endfor %}</select>
       <label class="fw-bold" for="password">Password (at least 8 characters)</label>
       <input class="form-control mb-3" id="password" type="password" name="password" required minlength="8">
       <button class="btn btn-primary w-100" style="height:48px">Create account</button></form>
      <p class="mt-3"><a href="{{ url_for('login') }}">Back to log in</a></p>""", programs=programs, form=form)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def bad_request(message):
    if wants_json():
        return jsonify(error=message), 400
    flash(message)
    return redirect(url_for("new_request"))


MY_REQUESTS_SQL = ("""SELECT r.request_id, d.name, r.copies, r.status, r.created_at, """ + PICKUP_SQL + """ AS pickup
                      FROM requests r JOIN document_types d USING (type_id)
                      LEFT JOIN pickup_points p ON p.point_id = r.pickup_point_id
                      WHERE r.student_id = %s ORDER BY r.created_at DESC""")


@app.route("/new", methods=["GET", "POST"])
@login_required("student")
def new_request():
    with db() as cur:
        if request.method == "POST":
            try:
                type_id, copies = int(request.form["type_id"]), int(request.form["copies"])
            except (KeyError, ValueError):
                return bad_request("Invalid form data")
            purpose = request.form.get("purpose", "").strip()[:200]
            if not purpose or not 1 <= copies <= 10:
                return bad_request("Purpose is required and copies must be 1-10")
            cur.execute("SELECT name FROM document_types WHERE type_id = %s", (type_id,))
            doc = cur.fetchone()
            if not doc:
                return bad_request("Unknown document type")
            cur.execute("""INSERT INTO requests (student_id, type_id, purpose, copies)
                           VALUES (%s, %s, %s, %s) RETURNING request_id, status, created_at""",
                        (session["uid"], type_id, purpose, copies))
            new = cur.fetchone()
            if wants_json():          
                row = dict(request_id=new["request_id"], name=doc["name"], copies=copies, status=new["status"],
                           pickup=None, created_at=new["created_at"].strftime("%Y-%m-%d %H:%M:%S"))
                row_html = render_template_string(MACROS + "{{ req_row(r, False, True) }}", r=row)
                return jsonify(request_id=row["request_id"], status=row["status"], row_html=row_html)
            flash(f"Request #{new['request_id']} submitted. Status: {new['status']}")   
            return redirect(url_for("new_request"))
        cur.execute("SELECT type_id, name FROM document_types ORDER BY name")
        types = cur.fetchall()
        cur.execute(MY_REQUESTS_SQL, (session["uid"],))
        mine = cur.fetchall()
    return page("""
    <section class="hero" aria-labelledby="hero-title">
     {% if before %}
      <img class="hero-img" src="{{ url_for('static', filename='before/hero-original.png') }}" width="2400" height="1350" alt="">
     {% else %}
      <picture>
       <source type="image/webp" srcset="{{ url_for('static', filename='hero-640.webp') }} 640w, {{ url_for('static', filename='hero-1280.webp') }} 1280w"
               sizes="(max-width: 720px) 100vw, 720px">
       <img class="hero-img" src="{{ url_for('static', filename='hero-640.jpg') }}" width="640" height="360" alt="">
      </picture>
     {% endif %}
     <div class="hero-text"><h1 id="hero-title">{{ icon('i-doc', before) }} Request a document</h1>
      <p>Choose a certificate, send the request and follow its status here.</p></div>
    </section>

    <div id="toast" class="toast-box" role="status" aria-live="polite" hidden>
     <span id="toastMsg"></span><button id="toastClose" type="button" class="btn btn-sm btn-outline-dark">Close</button></div>

    <form id="reqForm" method="post" action="{{ url_for('new_request') }}" class="col-md-6 mb-2">
     <label class="fw-bold" for="type_id">Document type</label>
     <select id="type_id" name="type_id" class="form-select mb-2">{% for t in types %}<option value="{{ t.type_id }}">{{ t.name }}</option>{% endfor %}</select>
     <label class="fw-bold" for="purpose">Purpose</label>
     <input id="purpose" name="purpose" class="form-control mb-2" placeholder="e.g. for the military office" required maxlength="200">
     <label class="fw-bold" for="copies">Copies</label>
     <input id="copies" name="copies" type="number" min="1" max="10" value="1" class="form-control mb-3">
     <button type="submit" class="btn btn-primary w-100" style="height:48px">Submit</button>
    </form>
    <label class="sound-switch mb-4" for="soundOn"><input type="checkbox" id="soundOn" checked> <span>Play a short sound when a request is sent or becomes ready</span></label>
    <audio id="notifySound" src="{{ url_for('static', filename='notification.mp3') }}" preload="none"></audio>

    <h2 class="h5">My requests</h2>
    <div class="table-responsive"><table class="table">
     <caption class="visually-hidden">My document requests, their status and where to pick them up</caption>
     <thead><tr><th scope="col">#</th><th scope="col">Document</th><th scope="col">Copies</th><th scope="col">Status</th><th scope="col">Pick up at</th><th scope="col">Date</th><th scope="col">Action</th></tr></thead>
     <tbody id="myRows">{% for r in mine %}{{ req_row(r, before) }}{% endfor %}</tbody></table></div>

    <script>
    (function () {
      var form = document.getElementById('reqForm'), toast = document.getElementById('toast'),
          msg = document.getElementById('toastMsg'), audio = document.getElementById('notifySound'),
          sound = document.getElementById('soundOn'), rows = document.getElementById('myRows');
      function show(text, isError) { msg.textContent = text; toast.classList.toggle('toast-error', !!isError); toast.hidden = false; }
      function play() { if (sound.checked) { audio.currentTime = 0; var p = audio.play(); if (p && p.catch) { p.catch(function () {}); } } }
      document.getElementById('toastClose').addEventListener('click', function () { toast.hidden = true; });

      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var btn = form.querySelector('button[type=submit]'); btn.disabled = true;
        fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'Accept': 'application/json' } })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (x) {
            if (!x.ok) { throw new Error(x.d.error || 'Server error'); }
            show('\\u2714 Request #' + x.d.request_id + ' submitted. Status: ' + x.d.status, false);
            rows.insertAdjacentHTML('afterbegin', x.d.row_html);
            form.reset(); play();
          })
          .catch(function (err) { show('Could not send the request: ' + err.message, true); })
          .then(function () { btn.disabled = false; });
      });

      rows.addEventListener('submit', function (e) {
        var f = e.target; if (!f.classList.contains('cancel-form')) { return; }
        e.preventDefault();
        var tr = f.closest('tr'), id = tr.dataset.id;
        if (!window.confirm('Cancel request #' + id + '?')) { return; }
        fetch(f.action, { method: 'POST', headers: { 'Accept': 'application/json' } })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (x) {
            if (!x.ok) { throw new Error(x.d.error || 'Server error'); }
            tr.dataset.status = x.d.status; tr.querySelector('.st').innerHTML = x.d.badge; tr.querySelector('.act').textContent = '';
            show('Request #' + id + ' is cancelled', false);
          })
          .catch(function (err) { show('Could not cancel: ' + err.message, true); });
      });

      {% if poll %}
      function refresh() {
        fetch('{{ url_for("api_my_requests") }}', { headers: { 'Accept': 'application/json' }, cache: 'no-store' })
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (items) {
            items.forEach(function (it) {
              var tr = rows.querySelector('tr[data-id="' + it.id + '"]'); if (!tr) { return; }
              var pk = tr.querySelector('.pk'), place = it.pickup || '\\u2014';
              if (tr.dataset.status !== it.status) {
                tr.dataset.status = it.status; tr.querySelector('.st').innerHTML = it.badge; pk.textContent = place;
                if (it.status !== 'New') { tr.querySelector('.act').textContent = ''; }
                if (it.status === 'Ready') { show('\\u2714 Request #' + it.id + ' is ready. Pick it up at ' + place, false); play(); }
                else { show('Request #' + it.id + ' is now: ' + it.status, false); }
              } else if (pk.textContent !== place) { pk.textContent = place; show('Request #' + it.id + ': pick up at ' + place, false); }
            });
          }).catch(function () {});
      }
      setInterval(refresh, 3000);
      {% endif %}
    })();
    </script>""", types=types, mine=mine)


@app.route("/new/cancel/<int:rid>", methods=["POST"])
@login_required("student")
def cancel_request(rid):
    with db() as cur:
        cur.execute("""UPDATE requests SET status = 'Cancelled', updated_at = now()
                       WHERE request_id = %s AND student_id = %s AND status = 'New' RETURNING request_id""",
                    (rid, session["uid"]))
        done = cur.fetchone()
        if done:
            cur.execute("""INSERT INTO status_history (request_id, old_status, new_status, changed_by)
                           VALUES (%s, 'New', 'Cancelled', %s)""", (rid, session["uid"]))
    if not done:
        message = "Only your own requests with status New can be cancelled"
        if wants_json():
            return jsonify(error=message), 409
        flash(message)
        return redirect(url_for("new_request"))
    if wants_json():
        return jsonify(request_id=rid, status="Cancelled",
                       badge=render_template_string(MACROS + "{{ badge(s, False) }}", s="Cancelled"))
    flash(f"Request #{rid} cancelled")
    return redirect(url_for("new_request"))


@app.route("/api/my-requests")
@login_required("student")
def api_my_requests():
    with db() as cur:
        cur.execute(MY_REQUESTS_SQL, (session["uid"],))
        rows = cur.fetchall()
    return jsonify([dict(id=r["request_id"], status=r["status"], pickup=r["pickup"],
                         badge=render_template_string(MACROS + "{{ badge(s, False) }}", s=r["status"])) for r in rows])


@app.route("/staff")
@login_required("staff")
def staff_list():
    status, tid = request.args.get("status", ""), request.args.get("type_id", "")
    try:
        pg = max(1, int(request.args.get("page", "1")))
    except ValueError:
        pg = 1
    sql = ("""SELECT r.request_id, u.full_name, d.name AS doc, r.created_at, r.status, r.pickup_point_id, """ + PICKUP_SQL + """ AS pickup
              FROM requests r JOIN users u ON u.user_id = r.student_id
              JOIN document_types d ON d.type_id = r.type_id
              LEFT JOIN pickup_points p ON p.point_id = r.pickup_point_id WHERE 1=1""")
    params = []
    if status == "all":
        pass            
    elif status in STATUSES:
        sql += " AND r.status = %s"; params.append(status)
    else:
        sql += " AND r.status IN ('New', 'In progress')" 
    if tid.isdigit():
        sql += " AND r.type_id = %s"; params.append(int(tid))
    sql += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
    params += [PAGE_SIZE + 1, (pg - 1) * PAGE_SIZE]        
    with db() as cur:
        cur.execute(sql, params); rows = cur.fetchall()
        cur.execute("SELECT type_id, name FROM document_types ORDER BY name"); types = cur.fetchall()
        cur.execute("SELECT point_id, block, room FROM pickup_points ORDER BY block, room"); points = cur.fetchall()
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    return page("""<h1 class="h4">Requests</h1>
    <form class="row g-2 mb-3">
     <div class="col-auto"><label class="visually-hidden" for="f_status">Filter by status</label>
      <select id="f_status" name="status" class="form-select"><option value="">Open requests (New + In progress)</option>
       <option value="all" {{ 'selected' if status == 'all' }}>All statuses</option>
       {% for s in sts %}<option {{ 'selected' if s == status }}>{{ s }}</option>{% endfor %}</select></div>
     <div class="col-auto"><label class="visually-hidden" for="f_type">Filter by document type</label>
      <select id="f_type" name="type_id" class="form-select"><option value="">Type: All</option>
       {% for t in types %}<option value="{{ t.type_id }}" {{ 'selected' if tid == t.type_id|string }}>{{ t.name }}</option>{% endfor %}</select></div>
     <div class="col-auto"><button class="btn btn-secondary">Filter</button></div>
    </form>
    <div class="table-responsive"><table class="table table-sm align-middle">
     <caption class="visually-hidden">All document requests</caption>
     <thead><tr><th scope="col">Student</th><th scope="col">Document</th><th scope="col">Date</th><th scope="col">Status</th><th scope="col">Pick up at</th><th scope="col">Change status and pickup point</th></tr></thead>
     <tbody>{% for r in rows %}<tr><td>{{ r.full_name }}</td><td>{{ r.doc }}</td><td>{{ r.created_at }}</td><td>{{ badge(r.status, before) }}</td>
      <td>{% if r.pickup %}{{ r.pickup }}{% else %}&mdash;{% endif %}</td><td>
      <form method="post" action="{{ url_for('set_status', rid=r.request_id) }}" class="status-form d-flex gap-1 flex-wrap">
       <select name="status" class="form-select form-select-sm w-auto" aria-label="New status for request {{ r.request_id }}">
        {% for s in sts %}<option {{ 'selected' if s == r.status }}>{{ s }}</option>{% endfor %}</select>
       <select name="pickup_point_id" class="form-select form-select-sm w-auto" aria-label="Pickup block and room for request {{ r.request_id }}">
        <option value="">Pickup point (needed for Ready)</option>
        {% for p in points %}<option value="{{ p.point_id }}" {{ 'selected' if r.pickup_point_id == p.point_id }}>{{ p.block }} &middot; room {{ p.room }}</option>{% endfor %}</select>
       <button class="btn btn-sm btn-primary">Save</button></form></td></tr>{% endfor %}</tbody></table></div>
    <nav aria-label="Pages" class="d-flex gap-3 align-items-center mb-3">
     {% if pg > 1 %}<a href="{{ url_for('staff_list', status=status, type_id=tid, page=pg-1) }}">&laquo; Previous 20</a>{% endif %}
     <span>Page {{ pg }}</span>
     {% if has_next %}<a href="{{ url_for('staff_list', status=status, type_id=tid, page=pg+1) }}">Next 20 &raquo;</a>{% endif %}</nav>
    <script>
    (function () {
      function check(f) {
        var bad = f.elements['status'].value === 'Ready' && !f.elements['pickup_point_id'].value;
        f.querySelector('button').disabled = bad; f.elements['pickup_point_id'].classList.toggle('is-invalid', bad);
      }
      document.querySelectorAll('form.status-form').forEach(function (f) { check(f); f.addEventListener('change', function () { check(f); }); });
    })();
    </script>""",
                rows=rows, types=types, points=points, sts=STATUSES, status=status, tid=tid, pg=pg, has_next=has_next)


@app.route("/staff/status/<int:rid>", methods=["POST"])
@login_required("staff")
def set_status(rid):
    new = request.form.get("status", "")
    point = request.form.get("pickup_point_id", "")
    if new not in STATUSES:
        abort(400)
    notify = None
    with db() as cur:
        cur.execute("SELECT status, pickup_point_id FROM requests WHERE request_id = %s FOR UPDATE", (rid,))
        row = cur.fetchone()
        if not row:
            abort(404)
        point_id = None                                
        if new == "Ready":
            if not point.isdigit():
                flash("Choose a pickup point (block and room) before setting Ready")
                return redirect(request.referrer or url_for("staff_list"))
            cur.execute("SELECT 1 FROM pickup_points WHERE point_id = %s", (int(point),))
            if not cur.fetchone():
                abort(400)
            point_id = int(point)
        if row["status"] != new or row["pickup_point_id"] != point_id:
            cur.execute("""UPDATE requests SET status = %s, handled_by = %s, pickup_point_id = %s, updated_at = now()
                           WHERE request_id = %s""", (new, session["uid"], point_id, rid))
        if row["status"] != new:
            cur.execute("""INSERT INTO status_history (request_id, old_status, new_status, changed_by)
                           VALUES (%s, %s, %s, %s)""", (rid, row["status"], new, session["uid"]))
        if new == "Ready" and (row["status"] != "Ready" or row["pickup_point_id"] != point_id):
            cur.execute("""SELECT u.email, u.full_name, d.name AS doc, p.block, p.room
                           FROM requests r JOIN users u ON u.user_id = r.student_id
                           JOIN document_types d ON d.type_id = r.type_id
                           JOIN pickup_points p ON p.point_id = %s WHERE r.request_id = %s""", (point_id, rid))
            notify = cur.fetchone()
    if notify:                                            
        mailer.send_async(notify["email"], f"Your document is ready: {notify['doc']}",
                          f"Hello, {notify['full_name']}!\n\nYour request #{rid} ({notify['doc']}) is ready.\n"
                          f"Pick it up at block {notify['block']}, room {notify['room']}.\nPlease take your student ID.\n\nDocRequest")
    flash(f"Request #{rid}: status set to {new}")
    return redirect(request.referrer or url_for("staff_list"))


Q_BY_TYPE = """SELECT d.name AS label, COUNT(*) AS value
               FROM requests r JOIN document_types d USING (type_id)
               GROUP BY d.name ORDER BY value DESC"""
Q_HOURS = """SELECT d.name AS label,
                    ROUND((AVG(EXTRACT(EPOCH FROM (h.ready_at - r.created_at))) / 3600)::numeric, 1) AS value,
                    COUNT(*) AS n
             FROM requests r JOIN document_types d USING (type_id)
             JOIN (SELECT request_id, MIN(changed_at) AS ready_at FROM status_history
                   WHERE new_status = 'Ready' GROUP BY request_id) h USING (request_id)
             GROUP BY d.name ORDER BY value DESC"""
Q_WEEKLY = """SELECT date_trunc('week', created_at)::date AS label, COUNT(*) AS value
              FROM requests GROUP BY label ORDER BY label"""


def line_chart_svg(points, y_title, x_title):
    if not points:
        return "<p>No data</p>"
    W, H, L, R, T, B = 640, 260, 56, 16, 16, 52
    mx = max(v for _, v in points) or 1
    n = len(points); step = (W - L - R) / max(n - 1, 1)
    xs = [L + i * step for i in range(n)]
    ys = [H - B - (v / mx) * (H - B - T) for _, v in points]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#0d6efd"><title>{html.escape(str(l))}: {v}</title></circle>'
                   for x, y, (l, v) in zip(xs, ys, points))
    every = max(1, -(-n // 6))
    xl = "".join(f'<text x="{x:.1f}" y="{H-B+16}" font-size="11" text-anchor="middle">{html.escape(str(l))}</text>'
                 for i, (x, (l, _)) in enumerate(zip(xs, points)) if i % every == 0)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(y_title)} by {html.escape(x_title)}" style="max-width:100%;height:auto">'
            f'<line x1="{L}" y1="{T}" x2="{L}" y2="{H-B}" stroke="#6c757d"/><line x1="{L}" y1="{H-B}" x2="{W-R}" y2="{H-B}" stroke="#6c757d"/>'
            f'<text x="{L-8}" y="{T+4}" font-size="11" text-anchor="end">{mx}</text><text x="{L-8}" y="{H-B+4}" font-size="11" text-anchor="end">0</text>'
            f'<polyline points="{poly}" fill="none" stroke="#0d6efd" stroke-width="2.5"/>{dots}{xl}'
            f'<text x="{(L+W-R)/2:.0f}" y="{H-6}" font-size="12" text-anchor="middle">{html.escape(x_title)}</text>'
            f'<text transform="translate(14 {(T+H-B)/2:.0f}) rotate(-90)" font-size="12" text-anchor="middle">{html.escape(y_title)}</text></svg>')


@app.route("/staff/stats")
@login_required("staff")
def staff_stats():
    with db() as cur:
        cur.execute(Q_BY_TYPE); by_type = [dict(label=r["label"], value=int(r["value"])) for r in cur.fetchall()]
        cur.execute(Q_HOURS); hours = [dict(label=r["label"], value=float(r["value"]), n=int(r["n"])) for r in cur.fetchall()]
        cur.execute(Q_WEEKLY); weekly = [(str(r["label"]), int(r["value"])) for r in cur.fetchall()]
    for rows_ in (by_type, hours):
        mx = max((r["value"] for r in rows_), default=0) or 1
        for r in rows_:
            r["pct"] = round(r["value"] / mx * 100)
    svg = line_chart_svg(weekly, "Requests (count)", "Week starting (date)")
    return page("""<h1 class="h4">Statistics</h1>
    <p class="text-muted">Source: tables requests, document_types and status_history of the docrequest database (test data).
     Queries: analysis.sql.</p>

    <h2 class="h5 mt-4">1. Which documents are requested most often?</h2>
    <table class="table table-sm align-middle"><caption class="visually-hidden">Requests per document type</caption>
     <thead><tr><th scope="col">Document type</th><th scope="col" style="width:50%">Requests (count)</th></tr></thead>
     <tbody>{% for r in by_type %}<tr><td>{{ r.label }}</td><td><div class="d-flex align-items-center gap-2">
      <div class="bar" style="width:{{ r.pct }}%"></div><span>{{ r.value }}</span></div></td></tr>{% endfor %}</tbody></table>

    <h2 class="h5 mt-4">2. How long does a request take until it is Ready?</h2>
    <table class="table table-sm align-middle"><caption class="visually-hidden">Average hours until Ready per document type</caption>
     <thead><tr><th scope="col">Document type</th><th scope="col" style="width:50%">Average time to Ready (hours)</th><th scope="col">Requests</th></tr></thead>
     <tbody>{% for r in hours %}<tr><td>{{ r.label }}</td><td><div class="d-flex align-items-center gap-2">
      <div class="bar" style="width:{{ r.pct }}%"></div><span>{{ r.value }}</span></div></td><td>{{ r.n }}</td></tr>{% endfor %}</tbody></table>

    <h2 class="h5 mt-4">3. How does the number of requests change week by week?</h2>
    {{ svg|safe }}""", by_type=by_type, hours=hours, svg=svg)


IOT_EVENTS = ("heartbeat", "door_closed", "door_opened", "document_present", "document_removed")
HEARTBEAT_DAYS = 90                                                      
_purge = {"last": 0.0}
DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", "dev-device-token")      

LOCKERS_SQL = """SELECT l.locker_id, l.label, p.block, p.room, s.event_type AS state, s.request_id,
                        seen.last_seen, (seen.last_seen > now() - interval '15 seconds') AS online, b.battery_pct
                 FROM lockers l JOIN pickup_points p USING (point_id)
                 LEFT JOIN LATERAL (SELECT e.event_type, e.request_id FROM locker_events e
                                    WHERE e.locker_id = l.locker_id AND e.event_type IN ('document_present', 'document_removed')
                                    ORDER BY e.created_at DESC, e.event_id DESC LIMIT 1) s ON TRUE
                 LEFT JOIN LATERAL (SELECT MAX(e.created_at) AS last_seen FROM locker_events e WHERE e.locker_id = l.locker_id) seen ON TRUE
                 LEFT JOIN LATERAL (SELECT e.battery_pct FROM locker_events e
                                    WHERE e.locker_id = l.locker_id AND e.battery_pct IS NOT NULL
                                    ORDER BY e.created_at DESC, e.event_id DESC LIMIT 1) b ON TRUE
                 ORDER BY p.block, p.room"""
EVENTS_SQL = """SELECT e.created_at, l.label, e.event_type, e.request_id
                FROM locker_events e JOIN lockers l USING (locker_id)
                WHERE e.event_type <> 'heartbeat' ORDER BY e.created_at DESC, e.event_id DESC LIMIT 8"""


def locker_snapshot(cur):
    cur.execute(LOCKERS_SQL); lockers = cur.fetchall()
    cur.execute(EVENTS_SQL); events = cur.fetchall()
    fmt = lambda t: t.strftime("%H:%M:%S") if t else "never"
    return dict(
        lockers=[dict(label=l["label"], place=f"{l['block']}, room {l['room']}",
                      state="Occupied" if l["state"] == "document_present" else "Empty",
                      request=l["request_id"] if l["state"] == "document_present" else None,
                      battery=l["battery_pct"], online=bool(l["online"]), last_seen=fmt(l["last_seen"])) for l in lockers],
        events=[dict(time=fmt(e["created_at"]), label=e["label"], event=e["event_type"].replace("_", " "), request=e["request_id"]) for e in events])


def purge_old_heartbeats(cur):
    if time.time() - _purge["last"] < 3600:
        return
    _purge["last"] = time.time()
    cur.execute("DELETE FROM locker_events WHERE event_type = 'heartbeat' AND created_at < now() - %s * interval '1 day'",
                (HEARTBEAT_DAYS,))


@app.route("/api/lockers")
@login_required("staff")
def api_lockers():
    with db() as cur:
        return jsonify(locker_snapshot(cur))


@app.route("/staff/lockers")
@login_required("staff")
def staff_lockers():
    return page("""<h1 class="h4">Smart pickup cabinets (simulation)</h1>
    <p class="text-muted">Readings come from the cabinet sensors (here: simulate_lockers.py) through POST /api/iot/event; the table refreshes every 3 seconds.</p>
    <div class="table-responsive"><table class="table table-sm align-middle">
     <caption class="visually-hidden">State of the pickup cabinets</caption>
     <thead><tr><th scope="col">Cabinet</th><th scope="col">Pick up at</th><th scope="col">State</th><th scope="col">Request</th><th scope="col">Battery</th><th scope="col">Connection</th><th scope="col">Last signal</th></tr></thead>
     <tbody id="lockerRows"><tr><td colspan="7">Loading...</td></tr></tbody></table></div>
    <h2 class="h5 mt-4">Latest events</h2>
    <ul id="eventList" class="list-unstyled"></ul>
    <script>
    (function () {
      var rows = document.getElementById('lockerRows'), list = document.getElementById('eventList');
      function cell(tr, text, cls) { var td = document.createElement('td');
        if (cls) { var s = document.createElement('span'); s.className = 'status ' + cls; s.textContent = text; td.appendChild(s); } else { td.textContent = text; }
        tr.appendChild(td); }
      function draw(d) {
        rows.textContent = '';
        d.lockers.forEach(function (l) {
          var tr = document.createElement('tr');
          cell(tr, l.label); cell(tr, l.place);
          cell(tr, l.state === 'Occupied' ? 'Occupied: document waiting' : 'Empty', l.state === 'Occupied' ? 'status-in-progress' : null);
          cell(tr, l.request ? '#' + l.request : '\u2014');
          cell(tr, l.battery === null ? '\u2014' : l.battery + ' %');
          cell(tr, l.online ? 'Online' : 'Offline', l.online ? 'status-ready' : 'status-cancelled');
          cell(tr, l.last_seen); rows.appendChild(tr);
        });
        list.textContent = '';
        d.events.forEach(function (e) { var li = document.createElement('li');
          li.textContent = e.time + '  ' + e.label + ': ' + e.event + (e.request ? ' (request #' + e.request + ')' : ''); list.appendChild(li); });
        if (!d.events.length) { list.textContent = 'No events yet. Start simulate_lockers.py.'; }
      }
      function refresh() { fetch('{{ url_for("api_lockers") }}', { headers: { 'Accept': 'application/json' }, cache: 'no-store' })
        .then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d) { draw(d); } }).catch(function () {}); }
      refresh(); setInterval(refresh, 3000);
    })();
    </script>""")


@app.route("/api/iot/event", methods=["POST"])
def iot_event():
    if not hmac.compare_digest(request.headers.get("X-Device-Token", "").encode(), DEVICE_TOKEN.encode()):
        return jsonify(error="unauthorised"), 401
    data = request.get_json(silent=True) or {}
    try:
        locker_id = int(data.get("locker_id"))
        req = int(data["request_id"]) if data.get("request_id") is not None else None
        battery = int(data["battery_pct"]) if data.get("battery_pct") is not None else None
    except (TypeError, ValueError):
        return jsonify(error="bad data"), 400
    event = data.get("event_type")
    if event not in IOT_EVENTS or (battery is not None and not 0 <= battery <= 100):
        return jsonify(error="bad data"), 400
    with db() as cur:
        cur.execute("SELECT 1 FROM lockers WHERE locker_id = %s", (locker_id,))
        if not cur.fetchone():
            return jsonify(error="unknown cabinet"), 404
        if req is not None:
            cur.execute("SELECT 1 FROM requests WHERE request_id = %s", (req,))
            if not cur.fetchone():
                return jsonify(error="unknown request"), 404
        cur.execute("""INSERT INTO locker_events (locker_id, request_id, event_type, battery_pct)
                       VALUES (%s, %s, %s, %s) RETURNING event_id""", (locker_id, req, event, battery))
        event_id = cur.fetchone()["event_id"]
        purge_old_heartbeats(cur)
        return jsonify(event_id=event_id), 201


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
