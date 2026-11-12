#!/usr/bin/env python3
"""Serve the published reader locally and accept notes saved from localhost."""

from __future__ import annotations

import json
import os
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
MAX_BODY = 2 * 1024 * 1024


class ReaderHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/_local/notes":
            self.respond(404, {"error": "未知的本地接口"})
            return

        host = (urlsplit("//" + self.headers.get("Host", "")).hostname or "").lower()
        origin = self.headers.get("Origin")
        if host not in {"localhost", "127.0.0.1", "::1"}:
            self.respond(403, {"error": "本地保存接口只接受 localhost 请求"})
            return
        if origin:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme != "http" or parsed_origin.netloc.lower() != self.headers.get("Host", "").lower():
                self.respond(403, {"error": "请求来源不匹配"})
                return
        if self.headers.get_content_type() != "application/json":
            self.respond(415, {"error": "请求必须使用 JSON"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_BODY:
                raise ValueError("请求内容过大或长度无效")
            payload = json.loads(self.rfile.read(length))
            paper_id, markdown = payload["paperId"], payload["markdown"]
            manifest = json.loads((PUBLIC / "content/manifest.json").read_text(encoding="utf-8"))
            if paper_id not in manifest["papers"]:
                raise ValueError("未知论文编号")
            if not isinstance(markdown, str):
                raise ValueError("笔记内容必须是文本")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self.respond(400, {"error": str(error) or "请求内容无效"})
            return

        destination = PUBLIC / "notes" / paper_id / "notes.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=destination.parent, delete=False) as file:
                temporary = Path(file.name)
                file.write(markdown)
            os.replace(temporary, destination)
        except OSError as error:
            if temporary:
                temporary.unlink(missing_ok=True)
            self.respond(500, {"error": f"无法写入笔记文件：{error}"})
            return
        self.respond(200, {"path": f"public/notes/{paper_id}/notes.md"})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ReaderHandler)
    print(f"Serving {PUBLIC} at http://localhost:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local reader server.")
    finally:
        server.server_close()
