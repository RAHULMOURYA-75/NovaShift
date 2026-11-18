
import os
import uuid
import threading
import socket
import ipaddress
import shutil
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask, render_template, request, jsonify,
    send_file, abort, session
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp


# =====================================================
# CONFIGURATION
# =====================================================

BASE = Path(__file__).resolve().parent

DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", str(BASE / "downloads"))).expanduser().resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-before-deploying"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

MAX_ACTIVE = int(os.environ.get("MAX_ACTIVE_JOBS", "2"))
MAX_DURATION = int(os.environ.get("MAX_DURATION_SECONDS", "7200"))
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "1024"))

ALLOWED_DOMAINS = [
    x.strip().lower()
    for x in os.environ.get(
        "ALLOWED_DOMAINS",
        "youtube.com,youtu.be"
    ).split(",")
    if x.strip()
]


# =====================================================
# FFMPEG
# =====================================================

LOCAL_FFMPEG = BASE / "ffmpeg"

if (LOCAL_FFMPEG / "ffmpeg").is_file() or (LOCAL_FFMPEG / "ffmpeg.exe").is_file():
    FFMPEG_LOCATION = LOCAL_FFMPEG
elif shutil.which("ffmpeg"):
    FFMPEG_LOCATION = Path(shutil.which("ffmpeg")).parent
else:
    FFMPEG_LOCATION = None

FFMPEG_AVAILABLE = bool(
    FFMPEG_LOCATION
    and (FFMPEG_LOCATION / "ffmpeg").is_file()
    or FFMPEG_LOCATION and (FFMPEG_LOCATION / "ffmpeg.exe").is_file()
)


# =====================================================
# DENO
# =====================================================

DENO_LOCATION = os.environ.get("DENO_PATH", "").strip()

if not DENO_LOCATION:
    possible_deno = Path.home() / ".deno" / "bin" / "deno.exe"

    if possible_deno.is_file():
        DENO_LOCATION = str(possible_deno)
    else:
        DENO_LOCATION = shutil.which("deno") or ""


# =====================================================
# FIREFOX COOKIES
# =====================================================

YTDLP_BROWSER = os.environ.get(
    "YTDLP_BROWSER", "firefox"
).strip().lower()


# =====================================================
# JOB STORAGE
# =====================================================

jobs = {}
jobs_lock = threading.Lock()
active_jobs = 0

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per hour"]
)


# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(429)
def handle_rate_limit(error):

    if request.path.startswith("/api/"):
        return jsonify({
            "error": "Too many requests. Please wait and try again."
        }), 429

    return "Too many requests. Please try again later.", 429


@app.errorhandler(500)
def handle_server_error(error):

    if request.path.startswith("/api/"):
        return jsonify({
            "error": "Internal server error. Check PowerShell output."
        }), 500

    return "Internal server error.", 500


# =====================================================
# YT-DLP OPTIONS
# =====================================================

def base_ydl_options():

    options = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "continuedl": True
    }

    if YTDLP_BROWSER and YTDLP_BROWSER != "none":
        options["cookiesfrombrowser"] = (YTDLP_BROWSER,)

    if DENO_LOCATION:
        options["js_runtimes"] = {
            "deno": {
                "path": DENO_LOCATION
            }
        }

    if FFMPEG_LOCATION and FFMPEG_LOCATION.exists():
        options["ffmpeg_location"] = str(FFMPEG_LOCATION)

    return options


# =====================================================
# URL VALIDATION
# =====================================================

def domain_allowed(host):

    host = (host or "").lower().rstrip(".")

    return any(
        host == domain or host.endswith("." + domain)
        for domain in ALLOWED_DOMAINS
    )


def validate_url(url):

    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Please enter a valid URL.")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only HTTPS links are accepted.")

    host = parsed.hostname.lower().rstrip(".")

    if not domain_allowed(host):
        raise ValueError("This host is not enabled on this server.")

    try:
        addresses = socket.getaddrinfo(host, None)

        if not addresses:
            raise ValueError("The host could not be resolved.")

        for item in addresses:
            ip = ipaddress.ip_address(item[4][0])

            if not ip.is_global:
                raise ValueError(
                    "Private or local network addresses are blocked."
                )

    except socket.gaierror:
        raise ValueError("The host could not be resolved.")

    return url


# =====================================================
# LOGIN
# =====================================================

def auth_required():
    return bool(APP_PASSWORD) and not session.get("authenticated")


@app.before_request
def require_login():

    if request.endpoint in ("login", "static"):
        return None

    if auth_required():

        if request.path.startswith("/api/"):
            return jsonify(
                error="Please sign in first.",
                login_required=True
            ), 401

        return render_template("login.html"), 401


@app.get("/")
def index():

    return render_template(
        "index.html",
        auth_enabled=bool(APP_PASSWORD)
    )


@app.get("/privacy")
def privacy():
    content = """
    <h2>Information this service processes</h2>
    <p>When you submit a media URL, NovaShift processes that URL to retrieve available media information and, when requested, create an output file. The server may process technical request data such as IP address, browser details, and timestamps for security, rate limiting, and troubleshooting.</p>
    <h2>Files and retention</h2>
    <p>Files created by this installation are stored on the operator's server. The operator must configure and publish a retention and deletion schedule before opening the service to the public. Do not submit private or confidential links.</p>
    <h2>Cookies and advertising</h2>
    <p>This application may use a session cookie for sign-in. If advertising or analytics services are added, this notice must be updated to identify those providers, their cookies or similar technologies, and applicable user choices before launch.</p>
    <h2>Third-party services</h2>
    <p>Supported media sources are operated by third parties and have their own privacy policies and terms. NovaShift is not affiliated with those platforms.</p>
    <h2>Contact</h2>
    <p>The site operator must add a monitored contact email or address here before public launch.</p>
    <p><strong>Operator note:</strong> This starter notice is a template, not legal advice. Replace it with a notice that accurately describes your hosting, logs, retention, analytics, advertising, and local legal obligations.</p>
    """
    return render_template("legal.html", title="Privacy Policy", content=content)


@app.get("/terms")
def terms():
    content = """
    <h2>Permitted use</h2>
    <p>Use NovaShift only for media that you own or are expressly authorized to download, convert, and store. You are responsible for complying with copyright law, platform terms, and any licenses or permissions that apply.</p>
    <h2>Prohibited use</h2>
    <p>Do not use this service to infringe copyright, distribute unlawful material, bypass DRM, paywalls, login walls, or other access controls, or interfere with the service or its security limits.</p>
    <h2>Availability and files</h2>
    <p>Availability, supported sources, formats, and resolutions depend on the original source and server configuration. No particular quality, uptime, or successful conversion is guaranteed. The operator may remove files and limit or suspend access.</p>
    <h2>Third-party platforms</h2>
    <p>NovaShift is an independent tool and is not endorsed by YouTube, Facebook, Instagram, or other media platforms. Platform names belong to their respective owners.</p>
    <h2>Operator details</h2>
    <p>The site owner must add their legal/business contact details and any locally required disclosures before public launch.</p>
    """
    return render_template("legal.html", title="Terms of Use", content=content)


@app.get("/contact")
def contact():
    content = """
    <h2>Contact the site operator</h2>
    <p>Before public launch, the site owner should replace this message with a monitored support email address or contact form, plus any required business details.</p>
    <p>For copyright or abuse reports, include the relevant page or URL, explain the concern, and provide enough information for the operator to review it.</p>
    """
    return render_template("legal.html", title="Contact", content=content)


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():

    if request.method == "POST":

        if not APP_PASSWORD:
            return jsonify(ok=True)

        if request.form.get("password", "") == APP_PASSWORD:
            session["authenticated"] = True
            return jsonify(ok=True)

        return jsonify(
            error="Incorrect password."
        ), 401

    return render_template("login.html")


# =====================================================
# VIDEO INFORMATION API
# =====================================================

@app.post("/api/info")
@limiter.limit("15 per minute")
def info():

    data = request.get_json(silent=True) or {}

    try:

        url = validate_url(data.get("url", ""))

        options = base_ydl_options()
        options["skip_download"] = True

        with yt_dlp.YoutubeDL(options) as ydl:
            video = ydl.extract_info(
                url,
                download=False
            )

        if not video:
            raise RuntimeError(
                "Video information could not be loaded."
            )

        heights = sorted({
            int(f["height"])
            for f in video.get("formats", [])
            if f.get("vcodec") != "none" and f.get("height")
        })

        return jsonify({
            "title": video.get("title") or "Untitled",
            "thumbnail": video.get("thumbnail"),
            "duration": video.get("duration"),
            "uploader": (
                video.get("uploader")
                or video.get("channel")
                or ""
            ),
            "qualities": heights
        })

    except Exception as error:

        print("[NovaShift info error]", error, flush=True)

        return jsonify(
            error=str(error)[:300]
        ), 400


# =====================================================
# DOWNLOAD WORKER
# =====================================================

def run_download(job_id, url, mode, quality):

    global active_jobs

    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def progress_hook(data):

        with jobs_lock:

            if job_id not in jobs:
                return

            if data["status"] == "downloading":

                total = (
                    data.get("total_bytes")
                    or data.get("total_bytes_estimate")
                    or 0
                )

                downloaded = data.get("downloaded_bytes", 0)

                percent = (
                    round(downloaded * 100 / total, 1)
                    if total else 0
                )

                jobs[job_id].update({
                    "status": "downloading",
                    "percent": percent,
                    "speed": data.get("_speed_str", ""),
                    "eta": data.get("_eta_str", "")
                })

            elif data["status"] == "finished":

                jobs[job_id].update({
                    "status": "processing",
                    "percent": 100
                })

    try:

        if not FFMPEG_AVAILABLE:

            raise RuntimeError(
                "FFmpeg not found. Install FFmpeg or add it to PATH."
            )

        if mode == "mp3":
            fmt = "bestaudio/best"
        else:

            max_height = int(quality)

            fmt = (
                f"bestvideo[height<={max_height}]+bestaudio/"
                f"best[height<={max_height}]/best"
            )

        options = base_ydl_options()

        options.update({
            "format": fmt,
            "outtmpl": str(job_dir / "%(title).150B.%(ext)s"),
            "paths": {
                "home": str(job_dir),
                "temp": str(job_dir)
            },
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "max_filesize": MAX_FILE_MB * 1024 * 1024,
            "overwrites": True,
            "continuedl": True
        })

        # Allow videos shorter than the configured maximum duration.
        if MAX_DURATION:

            options["match_filter"] = (
                yt_dlp.utils.match_filter_func(
                    f"duration < {MAX_DURATION}"
                )
            )

        if mode == "mp4":
            options["merge_output_format"] = "mp4"

        if mode == "mp3":

            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]

        reported_files = []

        def postprocessor_hook(data):

            info = data.get("info_dict") or {}

            for key in ("filepath", "_filename"):

                value = info.get(key)

                if value:
                    reported_files.append(Path(value))

        options["postprocessor_hooks"] = [postprocessor_hook]

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        if not info:

            raise RuntimeError(
                "yt-dlp did not return video information."
            )

        candidates = list(reported_files)

        for key in ("filepath", "_filename"):

            value = info.get(key)

            if value:
                candidates.append(Path(value))

        for item in info.get("requested_downloads") or []:

            value = item.get("filepath")

            if value:
                candidates.append(Path(value))

        candidates.extend(job_dir.rglob("*"))

        valid_files = []

        for candidate in candidates:

            try:

                candidate = candidate.resolve()

                if (
                    candidate.is_file()
                    and candidate.stat().st_size > 0
                    and candidate.suffix.lower() in (
                        ".mp4", ".mkv", ".webm", ".mp3", ".m4a"
                    )
                    and candidate not in valid_files
                ):

                    valid_files.append(candidate)

            except (OSError, ValueError):
                continue

        if not valid_files:

            raise RuntimeError(
                "Output file not found. Check PowerShell for yt-dlp errors."
            )

        if mode == "mp3":

            preferred = [
                f for f in valid_files
                if f.suffix.lower() == ".mp3"
            ]

        else:

            preferred = [
                f for f in valid_files
                if f.suffix.lower() == ".mp4"
            ]

        output_file = max(
            preferred or valid_files,
            key=lambda f: f.stat().st_mtime
        )

        # =================================================
        # SAVE USING ORIGINAL VIDEO TITLE
        # =================================================

        final_file = DOWNLOAD_DIR / output_file.name

        counter = 1

        while final_file.exists():

            final_file = DOWNLOAD_DIR / (
                f"{output_file.stem} ({counter})"
                f"{output_file.suffix.lower()}"
            )

            counter += 1

        shutil.move(str(output_file), str(final_file))

        with jobs_lock:

            jobs[job_id].update({
                "status": "complete",
                "percent": 100,
                "filename": final_file.name,
                "download_url": f"/api/file/{job_id}",
                "error": None
            })

        print(
            f"[NovaShift] Download complete: {final_file}",
            flush=True
        )

    except Exception as error:

        print(
            f"[NovaShift download error] {job_id}: {error!r}",
            flush=True
        )

        with jobs_lock:

            if job_id in jobs:

                jobs[job_id].update({
                    "status": "error",
                    "error": str(error)[:300]
                })

    finally:

        with jobs_lock:
            active_jobs = max(0, active_jobs - 1)


# =====================================================
# START DOWNLOAD API
# =====================================================

@app.post("/api/download")
@limiter.limit("5 per minute")
def start_download():

    global active_jobs

    data = request.get_json(silent=True) or {}

    try:

        url = validate_url(data.get("url", ""))

        mode = data.get("mode", "mp4")
        quality = str(data.get("quality", "1080"))

        if mode not in ("mp3", "mp4"):
            raise ValueError("Choose MP3 or MP4 format.")

        if not quality.isdigit():
            raise ValueError("Choose a valid video quality.")

        with jobs_lock:

            if active_jobs >= MAX_ACTIVE:

                return jsonify(
                    error="Server is busy. Please try again shortly."
                ), 429

            job_id = uuid.uuid4().hex

            jobs[job_id] = {
                "status": "queued",
                "percent": 0,
                "speed": "",
                "eta": "",
                "filename": None,
                "error": None
            }

            active_jobs += 1

        thread = threading.Thread(
            target=run_download,
            args=(job_id, url, mode, quality),
            daemon=True
        )

        thread.start()

        return jsonify(job_id=job_id)

    except Exception as error:

        print("[NovaShift start error]", error, flush=True)

        return jsonify(
            error=str(error)[:300]
        ), 400


# =====================================================
# DOWNLOAD STATUS API
# =====================================================

@app.get("/api/status/<job_id>")
@limiter.exempt
def status(job_id):

    with jobs_lock:

        item = jobs.get(job_id)

        if not item:

            return jsonify(
                error="Job not found."
            ), 404

        return jsonify(item)


# =====================================================
# DOWNLOAD FILE API
# =====================================================

@app.get("/api/file/<job_id>")
def file(job_id):

    with jobs_lock:

        item = jobs.get(job_id)

        if not item or item.get("status") != "complete":
            abort(404)

        filename = item.get("filename")

    if not filename:
        abort(404)

    path = (DOWNLOAD_DIR / filename).resolve()

    if path.parent != DOWNLOAD_DIR.resolve():
        abort(403)

    if not path.is_file():
        abort(404)

    return send_file(
        path,
        as_attachment=True,
        download_name=path.name
    )


# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/health")
def health():

    ffmpeg_ok = FFMPEG_AVAILABLE

    return jsonify({
        "status": "ok",
        "yt_dlp": yt_dlp.version.__version__,
        "ffmpeg_available": ffmpeg_ok,
        "deno_available": bool(DENO_LOCATION),
        "download_folder": str(DOWNLOAD_DIR)
    })


# =====================================================
# RUN SERVER
# =====================================================

if __name__ == "__main__":

    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
        threaded=True
    )
