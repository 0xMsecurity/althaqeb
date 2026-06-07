"""HTML and JSON report generator."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from althaqeb import __version__

TEMPLATES_DIR = Path(__file__).parent / "templates"


class ReportGenerator:
    def __init__(self):
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        self._env.globals["now"] = lambda: time.strftime("%Y-%m-%d %H:%M UTC")
        self._env.globals["version"] = __version__

    def generate_html(self, session: Any) -> str:
        data = session.to_dict() if hasattr(session, "to_dict") else session
        template = self._env.get_template("full_report.html")
        return template.render(session=data, findings=data.get("findings", []))
