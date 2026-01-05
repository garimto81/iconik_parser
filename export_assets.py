import json
import os
import time
from urllib.parse import urljoin

import requests

from utils import load_dotenv, normalize_base_url, require_env


def get_with_retries(
    url: str,
    headers: dict,
    params: dict | None = None,
    timeout: int = 60,
    retries: int = 3,
    backoff_base: float = 2.0,
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            # Handle rate limiting / temporary errors
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                sleep_sec = float(retry_after) if retry_after and retry_after.isdigit() else backoff_base ** attempt
                time.sleep(sleep_sec)
                last_exc = RuntimeError(f"HTTP {resp.status_code}")
                continue
            return resp
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff_base ** attempt)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Request failed without exception")


def main() -> None:
    load_dotenv()

    base_url = normalize_base_url(os.getenv("ICONIK_BASE_URL", "https://app.iconik.io/API/"))
    headers = {
        "App-ID": require_env("ICONIK_APP_ID"),
        "Auth-Token": require_env("ICONIK_AUTH_TOKEN"),
    }

    collection_id = os.getenv("ICONIK_COLLECTION_ID")
    per_page = int(os.getenv("ICONIK_PER_PAGE", "200"))
    limit = int(os.getenv("ICONIK_LIMIT", "0"))
    output_path = os.getenv("ICONIK_OUTPUT", "assets.json")
    detail_mode = os.getenv("ICONIK_DETAIL", "0").lower() in ("1", "true", "yes", "y")
    timeout = int(os.getenv("ICONIK_TIMEOUT", "60"))
    retries = int(os.getenv("ICONIK_RETRIES", "3"))

    if limit > 0:
        per_page = min(per_page, limit)

    url = urljoin(base_url, "assets/v1/assets/")
    page = 1
    all_assets: list[dict] = []

    while True:
        if limit > 0:
            remaining = limit - len(all_assets)
            if remaining <= 0:
                break
            page_size = min(per_page, remaining)
        else:
            page_size = per_page

        params = {"page": page, "per_page": page_size}
        if collection_id:
            params["collection_id"] = collection_id

        resp = get_with_retries(url, headers, params=params, timeout=timeout, retries=retries)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            items = data.get("objects") or data.get("assets") or []
            pages = data.get("pages")
            next_url = data.get("next_url")
        else:
            items = data or []
            pages = None
            next_url = None

        if not items:
            break

        if detail_mode:
            detailed_items: list[dict] = []
            for item in items:
                asset_id = item.get("id")
                if not asset_id:
                    detailed_items.append(item)
                    continue
                detail_url = urljoin(base_url, f"assets/v1/assets/{asset_id}/")
                d_resp = get_with_retries(detail_url, headers, timeout=timeout, retries=retries)
                d_resp.raise_for_status()
                detail_data = d_resp.json()
                merged = dict(item)
                if isinstance(detail_data, dict):
                    merged.update(detail_data)
                detailed_items.append(merged)
            items = detailed_items

        all_assets.extend(items)
        if limit > 0 and len(all_assets) >= limit:
            all_assets = all_assets[:limit]
            break

        if next_url or (pages and page < pages):
            page += 1
            continue
        if pages is None and len(items) == per_page:
            page += 1
            continue
        break

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_assets, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(all_assets)} assets to {output_path}")


if __name__ == "__main__":
    main()
