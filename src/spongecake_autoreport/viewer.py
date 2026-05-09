"""Tiny Flask viewer serving the reports directory.

Bound to 127.0.0.1 by default (Traefik fronts it). Direct exposure mode
opens 0.0.0.0 + UFW + basic auth.
"""

from __future__ import annotations

import argparse
import base64
import html
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, abort, request, send_from_directory


def create_app(reports_root: Path, viewer_auth: str = "") -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _auth():
        if request.path == "/healthz":
            return None
        if not viewer_auth:
            return None
        header = request.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return Response(
                "auth required", 401,
                {"WWW-Authenticate": 'Basic realm="spongecake"'},
            )
        try:
            decoded = base64.b64decode(header.split(" ", 1)[1]).decode()
        except Exception:
            return Response("bad auth", 400)
        if decoded != viewer_auth:
            return Response(
                "forbidden", 401,
                {"WWW-Authenticate": 'Basic realm="spongecake"'},
            )
        return None

    @app.route("/healthz")
    def healthz():
        return {"status": "ok", "reports_root": str(reports_root)}

    @app.route("/")
    def index():
        if not reports_root.exists():
            return "<p>no reports yet</p>"
        run_dirs = sorted(
            (d for d in reports_root.iterdir() if d.is_dir() and not d.name.startswith(".")),
            reverse=True,
        )
        rows = []
        for d in run_dirs[:60]:
            html_index = d / "index.html"
            pdf_files = sorted(d.glob("*.pdf"))
            label = d.name
            html_link = f'<a href="/r/{d.name}/index.html">html</a>' if html_index.exists() else "—"
            pdf_link = (
                f'<a href="/r/{d.name}/{pdf_files[0].name}">pdf</a>' if pdf_files else "—"
            )
            rows.append(f"<tr><td>{html.escape(label)}</td><td>{html_link}</td><td>{pdf_link}</td></tr>")

        return (
            "<html><head><title>Spongecake</title>"
            "<style>body{font-family:-apple-system,sans-serif;margin:24px;}"
            "table{border-collapse:collapse;font-size:13px;}"
            "td,th{border:1px solid #ccc;padding:4px 10px;text-align:left;}"
            "th{background:#f0f0f0;}</style></head><body>"
            f"<h1>Spongecake — runs</h1>"
            f"<p>Reports root: <code>{html.escape(str(reports_root))}</code></p>"
            "<table><tr><th>Date</th><th>HTML</th><th>PDF</th></tr>"
            + "".join(rows) +
            "</table></body></html>"
        )

    @app.route("/r/<path:run_path>")
    def serve_run(run_path: str):
        # Basic path traversal protection
        target = (reports_root / run_path).resolve()
        if not str(target).startswith(str(reports_root.resolve())):
            abort(403)
        if not target.exists():
            abort(404)
        return send_from_directory(target.parent, target.name)

    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument(
        "--reports", default=os.environ.get("SPONGECAKE_REPORTS", "./reports"),
        help="path to reports directory",
    )
    args = ap.parse_args()
    reports_root = Path(args.reports).resolve()
    auth = os.environ.get("VIEWER_AUTH", "")
    app = create_app(reports_root, auth)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
