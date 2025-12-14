import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
from typing import Any, Iterable

from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_HEADER = [
    "id",
    "title",
    "time_start_ms",
    "time_end_ms",
    "time_start_S",
    "time_end_S",
    "Description",
    "ProjectName",
    "ProjectNameTag",
    "SearchTag",
    "Year_",
    "Location",
    "Venue",
    "EpisodeEvent",
    "Source",
    "Scene",
    "GameType",
    "PlayersTags",
    "HandGrade",
    "HANDTag",
    "EPICHAND",
    "Tournament",
    "PokerPlayTags",
    "Adjective",
    "Emotion",
    "AppearanceOutfit",
    "SceneryObject",
    "_gcvi_tags",
    "Badbeat",
    "Bluff",
    "Suckout",
    "Cooler",
    "RUNOUTTag",
    "PostFlop",
    "All-in",
]


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            try:
                stream.reconfigure(errors="backslashreplace")
            except Exception:
                pass


def normalize_cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        if all(not isinstance(v, (dict, list)) for v in value):
            return "\n".join(str(v) for v in value if v is not None).strip()
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def build_header(assets: Iterable[dict]) -> list[str]:
    metadata_keys: set[str] = set()
    for asset in assets:
        md = asset.get("metadata")
        if not isinstance(md, dict):
            continue
        for key in md.keys():
            if isinstance(key, str) and key:
                metadata_keys.add(key)

    base = list(BASE_HEADER)
    base_set = set(base)
    extra = sorted(k for k in metadata_keys if k not in base_set)
    return base + extra


def asset_to_row(asset: dict, header: list[str]) -> list[str]:
    md = asset.get("metadata") or {}
    if not isinstance(md, dict):
        md = {}

    time_start_ms = asset.get("time_start_milliseconds")
    time_end_ms = asset.get("time_end_milliseconds")

    def ms_to_s(ms: Any) -> str:
        if isinstance(ms, (int, float)):
            return str(ms / 1000)
        return ""

    row: dict[str, str] = {
        "id": str(asset.get("id") or ""),
        "title": str(asset.get("title") or asset.get("name") or ""),
        "time_start_ms": str(time_start_ms or ""),
        "time_end_ms": str(time_end_ms or ""),
        "time_start_S": ms_to_s(time_start_ms),
        "time_end_S": ms_to_s(time_end_ms),
        "ProjectNameTag": "",
        "SearchTag": "",
    }

    for key in header:
        if key in row:
            continue
        if key in md:
            row[key] = normalize_cell_value(md.get(key))
        else:
            row[key] = ""

    return [row.get(col, "") for col in header]


def flatten_assets(assets: Iterable[dict], header: list[str]) -> list[list[str]]:
    rows = [header]
    for asset in assets:
        rows.append(asset_to_row(asset, header))
    return rows


def load_assets(json_path: str) -> list[dict]:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        items = data.get("objects") or data.get("assets") or []
        return [d for d in items if isinstance(d, dict)]
    return []


def build_credentials() -> Any:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    sa_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    oauth_client_file = os.getenv("GOOGLE_OAUTH_CLIENT_FILE")

    if sa_file and os.path.exists(sa_file):
        return service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
    if sa_json:
        info = json.loads(sa_json)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    if oauth_client_file and os.path.exists(oauth_client_file):
        flow = InstalledAppFlow.from_client_secrets_file(oauth_client_file, scopes=scopes)
        creds = flow.run_local_server(port=0)
        return creds

    raise RuntimeError(
        "Google credentials not found. Set one of: "
        "GOOGLE_APPLICATION_CREDENTIALS (service account json path), "
        "GOOGLE_SERVICE_ACCOUNT_JSON (raw json), "
        "GOOGLE_OAUTH_CLIENT_FILE (OAuth client json)."
    )


def ensure_tab(service, spreadsheet_id: str, tab_name: str) -> str:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    name = tab_name
    if name in existing:
        suffix = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{tab_name}_{suffix}"

    body = {"requests": [{"addSheet": {"properties": {"title": name}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    return name


def write_rows(service, spreadsheet_id: str, tab_name: str, rows: list[list[str]]) -> None:
    range_name = f"{tab_name}!A1"
    body = {"values": rows}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body,
    ).execute()


def print_match_report(
    *,
    assets: list[dict],
    header: list[str],
    rows: list[list[str]],
    tab_name: str | None,
    print_all_matches: bool,
    match_preview: int,
    stream,
) -> None:
    asset_count = len(assets)
    base_cols = len(BASE_HEADER)
    total_cols = len(header)
    extra_cols = max(0, total_cols - base_cols)

    if tab_name:
        print(f"탭: {tab_name}", file=stream)
    print(f"행(헤더 제외): {asset_count}", file=stream)
    print(f"컬럼: {total_cols} (기본 {base_cols} + 확장 {extra_cols})", file=stream)

    if asset_count > 0 and rows:
        counts = {col: 0 for col in header}
        for row in rows[1:]:
            for col, cell in zip(header, row):
                if str(cell).strip() != "":
                    counts[col] += 1

        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        print("컬럼 채움 TOP 10:", file=stream)
        for col, cnt in top:
            print(f"- {col}: {cnt}/{asset_count}", file=stream)

        empty_cols = sorted([col for col, cnt in counts.items() if cnt == 0])
        if empty_cols:
            preview = ", ".join(empty_cols[:20])
            suffix = " ..." if len(empty_cols) > 20 else ""
            print(f"빈 컬럼(0/{asset_count}): {preview}{suffix}", file=stream)

    matches: list[dict[str, str | int]] = []
    for idx, asset in enumerate(assets):
        matches.append(
            {
                "row": idx + 2,  # 1-based, header at row 1
                "id": str(asset.get("id") or ""),
                "title": str(asset.get("title") or asset.get("name") or ""),
            }
        )

    show = matches if print_all_matches else matches[: max(0, match_preview)]
    print("매칭(시트 행 ↔ asset):", file=stream)
    for m in show:
        print(f"- {m['row']}: {m['id']} | {m['title']}", file=stream)
    if not print_all_matches and len(matches) > max(0, match_preview):
        print(f"(미리보기 {len(show)}/{len(matches)}; 전체 출력은 --print-matches)", file=stream)


def main() -> None:
    load_dotenv()
    configure_stdio()
    parser = argparse.ArgumentParser(description="Flatten iconik assets JSON and sync to Google Sheets.")
    parser.add_argument("--json", default=os.getenv("ICONIK_JSON", "assets_test.json"), help="Path to assets JSON")
    parser.add_argument("--sheet", default=os.getenv("GOOGLE_SHEET_ID"), help="Google Spreadsheet ID")
    parser.add_argument("--tab", default=os.getenv("GOOGLE_TAB_NAME", "iconik_export"), help="Tab name to create")
    parser.add_argument("--dry-run", action="store_true", help="Only write CSV to stdout")
    parser.add_argument("--print-matches", action="store_true", help="Print all row↔asset matches (can be noisy)")
    parser.add_argument(
        "--match-preview",
        type=int,
        default=int(os.getenv("ICONIK_MATCH_PREVIEW", "20")),
        help="How many matches to preview when not using --print-matches",
    )
    args = parser.parse_args()

    assets = load_assets(args.json)
    header = build_header(assets)
    rows = flatten_assets(assets, header)

    if args.dry_run:
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerows(rows)
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass
        sys.stdout.write(out.getvalue())
        print_match_report(
            assets=assets,
            header=header,
            rows=rows,
            tab_name=None,
            print_all_matches=args.print_matches,
            match_preview=args.match_preview,
            stream=sys.stderr,
        )
        return

    if not args.sheet:
        print("Missing --sheet (or GOOGLE_SHEET_ID).", file=sys.stderr)
        sys.exit(2)

    creds = build_credentials()
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    tab_name = ensure_tab(service, args.sheet, args.tab)
    write_rows(service, args.sheet, tab_name, rows)
    print(f"Wrote {len(rows)-1} rows to {args.sheet} / tab '{tab_name}'")
    print_match_report(
        assets=assets,
        header=header,
        rows=rows,
        tab_name=tab_name,
        print_all_matches=args.print_matches,
        match_preview=args.match_preview,
        stream=sys.stdout,
    )


if __name__ == "__main__":
    main()
