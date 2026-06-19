"""Export the backend's OpenAPI (Swagger) spec + standalone browsable docs.

Run:  python -m scripts.export_openapi   (from apps/api)
Writes to <repo>/docs/api/:
  - openapi.json   (canonical spec)
  - openapi.yaml   (if PyYAML is available)
  - index.html     (Swagger UI, loads ./openapi.json)
  - redoc.html     (ReDoc, loads ./openapi.json)

The spec is generated from the live FastAPI app, so it's always in sync with the
routers. No server or DB connection is needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "api"

SWAGGER_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Job Application &amp; Outreach Engine — API (Swagger UI)</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: "./openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
      });
    </script>
  </body>
</html>
"""

REDOC_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Job Application &amp; Outreach Engine — API (ReDoc)</title>
  </head>
  <body>
    <redoc spec-url="./openapi.json"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
  </body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()

    (OUT_DIR / "openapi.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    wrote = ["openapi.json"]

    try:
        import yaml  # optional

        (OUT_DIR / "openapi.yaml").write_text(
            yaml.safe_dump(spec, sort_keys=False), encoding="utf-8"
        )
        wrote.append("openapi.yaml")
    except ImportError:
        print("(PyYAML not installed — skipping openapi.yaml; JSON is canonical)")

    (OUT_DIR / "index.html").write_text(SWAGGER_HTML, encoding="utf-8")
    (OUT_DIR / "redoc.html").write_text(REDOC_HTML, encoding="utf-8")
    wrote += ["index.html", "redoc.html"]

    paths = len(spec.get("paths", {}))
    ops = sum(len([m for m in item if m in
                   ("get", "post", "put", "patch", "delete")])
              for item in spec.get("paths", {}).values())
    print(f"OpenAPI {spec['info']['version']} — {paths} paths, {ops} operations")
    print(f"Wrote to {OUT_DIR}:")
    for f in wrote:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
