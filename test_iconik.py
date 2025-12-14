import json
import os
import sys
from urllib.parse import urljoin

import requests


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing env var: {name}", file=sys.stderr)
        sys.exit(2)
    return value


def main() -> None:
    load_dotenv()

    base_url = os.getenv("ICONIK_BASE_URL", "https://app.iconik.io/API/")
    normalized_base = base_url.rstrip("/")
    if not normalized_base.lower().endswith("/api"):
        base_url = normalized_base + "/API/"
    else:
        base_url = normalized_base + "/"
    app_id = require_env("ICONIK_APP_ID")
    auth_token = require_env("ICONIK_AUTH_TOKEN")

    headers = {"App-ID": app_id, "Auth-Token": auth_token}

    url = urljoin(base_url.rstrip("/") + "/", "assets/v1/assets/")
    params = {"page": 1, "per_page": 5}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    print(
        "HTTP",
        resp.status_code,
        "| content-type:",
        resp.headers.get("content-type"),
        "| len:",
        len(resp.text or ""),
    )
    resp.raise_for_status()

    try:
        data = resp.json()
    except ValueError:
        print("Non-JSON response preview:")
        print((resp.text or "")[:1000])
        raise
    # iconik returns a list or an object with items depending on endpoint/version
    items = data.get("objects") or data.get("assets") or data
    print(json.dumps(items, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
