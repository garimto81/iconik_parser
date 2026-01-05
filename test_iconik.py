import json
import os
from urllib.parse import urljoin

import requests

from utils import load_dotenv, normalize_base_url, require_env


def main() -> None:
    load_dotenv()

    base_url = normalize_base_url(os.getenv("ICONIK_BASE_URL", "https://app.iconik.io/API/"))
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
