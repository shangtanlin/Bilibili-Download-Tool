from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from yt_dlp import YoutubeDL

INVALID_FILENAME_CHARS = r'\/:*?"<>|'


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/download")
    def download():
        url = request.form.get("url", "").strip()
        media_format = request.form.get("format", "video")
        custom_name = request.form.get("filename", "").strip()

        if not url:
            flash("请输入有效的哔哩哔哩视频链接。")
            return redirect(url_for("index"))

        if "bilibili.com" not in url:
            flash("目前仅支持哔哩哔哩链接，请重新输入。")
            return redirect(url_for("index"))

        tmp_dir = tempfile.mkdtemp(prefix="bili-download-")
        try:
            output_template = str(Path(tmp_dir) / "%(title)s.%(ext)s")
            ydl_opts = {
                "outtmpl": output_template,
                "quiet": True,
                "nocheckcertificate": True,
            }

            if media_format == "audio":
                ydl_opts.update(
                    {
                        "format": "bestaudio/best",
                        "postprocessors": [
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192",
                            }
                        ],
                        "prefer_ffmpeg": True,
                    }
                )
            else:
                ydl_opts.update(
                    {
                        "format": "bestvideo+bestaudio/best",
                        "merge_output_format": "mp4",
                    }
                )

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_path = Path(ydl.prepare_filename(info))

            if media_format == "audio":
                downloaded_path = downloaded_path.with_suffix(".mp3")
                download_name = f"{_build_download_name(custom_name, info)}.mp3"
            else:
                downloaded_path = downloaded_path.with_suffix(".mp4")
                download_name = f"{_build_download_name(custom_name, info)}.mp4"

            if not downloaded_path.exists():
                flash("解析文件失败，请稍后再试。")
                return redirect(url_for("index"))

            response = send_file(
                downloaded_path,
                as_attachment=True,
                download_name=download_name,
            )
            response.call_on_close(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
            return response
        except Exception as exc:  # pylint: disable=broad-except
            shutil.rmtree(tmp_dir, ignore_errors=True)
            flash(f"下载失败：{exc}")
            return redirect(url_for("index"))

    return app


def _build_download_name(custom_name: str, info: dict) -> str:
    """Generate a user-facing download name while stripping invalid characters."""
    base = custom_name or info.get("title") or "bilibili"
    sanitized = re.sub(f"[{re.escape(INVALID_FILENAME_CHARS)}]", "", base).strip()
    return sanitized or "bilibili"


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
