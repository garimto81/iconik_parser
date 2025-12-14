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


def normalize_base_url(base_url: str) -> str:
    normalized = (base_url or "").rstrip("/")
    if not normalized.lower().endswith("/api"):
        return normalized + "/API/"
    return normalized + "/"


def main() -> None:
    load_dotenv()

    base_url = normalize_base_url(os.getenv("ICONIK_BASE_URL", "https://app.iconik.io/API/"))
    headers = {
        "App-ID": require_env("ICONIK_APP_ID"),
        "Auth-Token": require_env("ICONIK_AUTH_TOKEN"),
    }

    url = urljoin(base_url, "assets/v1/collections/")
    page = 1
    per_page = int(os.getenv("ICONIK_PER_PAGE", "200"))
    results: list[dict] = []

    while True:
        resp = requests.get(
            url,
            headers=headers,
            params={"page": page, "per_page": per_page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            items = data.get("objects") or data.get("collections") or []
            pages = data.get("pages")
            next_url = data.get("next_url")
        else:
            items = data or []
            pages = None
            next_url = None

        if not items:
            break

        for col in items:
            results.append(
                {
                    "id": col.get("id"),
                    "name": col.get("name"),
                    "is_root": col.get("is_root"),
                    "date_modified": col.get("date_modified"),
                }
            )

        if next_url or (pages and page < pages):
            page += 1
            continue
        if pages is None and len(items) == per_page:
            page += 1
            continue
        break

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

