import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from typing import Any

from googleapiclient.discovery import build

import sync_to_sheet as s


def normalize_sheet_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("\r\n", "\n").strip()


def sha256_table(rows: list[list[str]]) -> str:
    hasher = hashlib.sha256()
    for row in rows:
        hasher.update("\x1f".join(row).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def read_tab_values(service, spreadsheet_id: str, tab_name: str) -> list[list[Any]]:
    resp = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=tab_name,
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    values = resp.get("values") or []
    return values if isinstance(values, list) else []


def extract_row(
    *,
    row: list[Any],
    cols: list[str],
    col_index: dict[str, int],
) -> list[str]:
    out: list[str] = []
    for col in cols:
        idx = col_index.get(col)
        cell = row[idx] if idx is not None and idx < len(row) else ""
        out.append(normalize_sheet_cell(cell))
    return out


def write_text_report(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main() -> None:
    s.load_dotenv()
    s.configure_stdio()

    parser = argparse.ArgumentParser(
        description="Verify that a Google Sheets tab matches the iconik API export JSON (cell-by-cell)."
    )
    parser.add_argument("--json", default=os.getenv("ICONIK_JSON", "assets_test.json"), help="Path to assets JSON")
    parser.add_argument("--sheet", default=os.getenv("GOOGLE_SHEET_ID"), help="Google Spreadsheet ID")
    parser.add_argument("--tab", required=True, help="Tab name to verify")
    parser.add_argument(
        "--mode",
        choices=["auto", "base", "all", "common"],
        default="auto",
        help="Compare column set: base(BASE_HEADER), all(expected full header), common(intersection), or auto.",
    )
    parser.add_argument(
        "--match-mode",
        choices=["order", "id"],
        default="order",
        help="How to match rows: order(row index) or id(requires unique ids).",
    )
    parser.add_argument("--print-matches", action="store_true", help="Print all row↔asset matches")
    parser.add_argument(
        "--match-preview",
        type=int,
        default=int(os.getenv("ICONIK_MATCH_PREVIEW", "20")),
        help="How many matches to preview when not using --print-matches",
    )
    parser.add_argument("--max-diffs", type=int, default=20, help="How many diffs to print in the report")
    parser.add_argument("--out", help="Write a text proof report to this path (UTF-8)")
    args = parser.parse_args()

    if not args.sheet:
        print("Missing --sheet (or GOOGLE_SHEET_ID).", file=sys.stderr)
        sys.exit(2)

    assets = s.load_assets(args.json)
    expected_header_all = s.build_header(assets)
    expected_header_base = list(s.BASE_HEADER)

    creds = s.build_credentials()
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    tab_values = read_tab_values(service, args.sheet, args.tab)
    if not tab_values:
        print("시트 탭에서 값을 읽지 못했습니다(빈 탭이거나 접근 권한/이름을 확인하세요).", file=sys.stderr)
        sys.exit(2)

    actual_header = [normalize_sheet_cell(v) for v in (tab_values[0] or [])]
    actual_set = set(actual_header)

    mode = args.mode
    if mode == "auto":
        if actual_header == expected_header_all:
            mode = "all"
        elif actual_header == expected_header_base:
            mode = "base"
        else:
            mode = "common"

    if mode == "all":
        cols = expected_header_all
        expected_rows = s.flatten_assets(assets, cols)
        header_ok = actual_header == cols
        if not header_ok:
            print("헤더가 기대값과 다릅니다. (--mode base/common 또는 탭을 확인하세요)", file=sys.stderr)
    elif mode == "base":
        cols = expected_header_base
        expected_rows = s.flatten_assets(assets, cols)
        missing = [c for c in cols if c not in actual_set]
        header_ok = len(missing) == 0
        if not header_ok:
            print(f"시트 헤더에 BASE_HEADER 컬럼이 누락되었습니다: {', '.join(missing)}", file=sys.stderr)
    else:  # common
        cols = [c for c in expected_header_all if c in actual_set]
        expected_rows = s.flatten_assets(assets, cols)
        header_ok = "id" in cols
        if not header_ok:
            print("공통 컬럼에 'id'가 없습니다. 탭 헤더를 확인하세요.", file=sys.stderr)

    actual_col_index = {name: i for i, name in enumerate(actual_header) if name}

    expected_asset_count = len(assets)
    actual_row_count = max(0, len(tab_values) - 1)

    diffs: list[dict[str, Any]] = []
    mismatch_cells = 0

    def compare_rows(expected_row: list[str], actual_row: list[str], row_number: int) -> None:
        nonlocal mismatch_cells
        for col_name, exp, act in zip(cols, expected_row, actual_row):
            exp_n = normalize_sheet_cell(exp)
            act_n = normalize_sheet_cell(act)
            if exp_n != act_n:
                mismatch_cells += 1
                if len(diffs) < max(0, args.max_diffs):
                    diffs.append(
                        {
                            "row": row_number,
                            "col": col_name,
                            "expected": exp_n,
                            "actual": act_n,
                        }
                    )

    matches: list[dict[str, Any]] = []

    if args.match_mode == "id":
        if "id" not in actual_col_index or "id" not in cols:
            print("id 매칭 모드는 'id' 컬럼이 필요합니다.", file=sys.stderr)
            sys.exit(2)

        id_col_pos = cols.index("id")
        expected_ids: list[str] = []
        expected_seen: set[str] = set()
        expected_dupes: set[str] = set()
        for r in expected_rows[1:]:
            asset_id = normalize_sheet_cell(r[id_col_pos])
            expected_ids.append(asset_id)
            if asset_id in expected_seen:
                expected_dupes.add(asset_id)
            expected_seen.add(asset_id)

        sheet_id_pos = actual_col_index["id"]
        sheet_map: dict[str, tuple[int, list[Any]]] = {}
        sheet_dupes: set[str] = set()
        for idx, row in enumerate(tab_values[1:], start=2):
            asset_id = normalize_sheet_cell(row[sheet_id_pos] if sheet_id_pos < len(row) else "")
            if asset_id in sheet_map:
                sheet_dupes.add(asset_id)
            sheet_map[asset_id] = (idx, row)

        if expected_dupes or sheet_dupes:
            msg = []
            if expected_dupes:
                msg.append(f"기준 JSON에 중복 id {len(expected_dupes)}개")
            if sheet_dupes:
                msg.append(f"시트에 중복 id {len(sheet_dupes)}개")
            print("id 매칭 모드는 id가 유일해야 합니다: " + ", ".join(msg), file=sys.stderr)
            sys.exit(2)

        missing_in_sheet = [i for i in expected_ids if i not in sheet_map]
        extra_in_sheet = [i for i in sheet_map.keys() if i not in expected_seen and i != ""]

        for exp_idx, exp_row in enumerate(expected_rows[1:], start=2):
            asset_id = normalize_sheet_cell(exp_row[id_col_pos])
            sheet_row_num, sheet_row = sheet_map.get(asset_id, (None, []))
            if sheet_row_num is None:
                continue
            act_row = extract_row(row=sheet_row, cols=cols, col_index=actual_col_index)
            compare_rows(exp_row, act_row, sheet_row_num)
            matches.append({"row": sheet_row_num, "id": asset_id, "title": exp_row[cols.index("title")] if "title" in cols else ""})

        strict_ok = (
            header_ok
            and (expected_asset_count == actual_row_count)
            and (len(missing_in_sheet) == 0)
            and (len(extra_in_sheet) == 0)
            and (mismatch_cells == 0)
        )
        id_mode_notes = {
            "missing_in_sheet": len(missing_in_sheet),
            "extra_in_sheet": len(extra_in_sheet),
        }
    else:
        compare_n = min(expected_asset_count, actual_row_count)
        for i in range(compare_n):
            row_number = i + 2
            exp_row = expected_rows[i + 1]
            act_row = extract_row(row=tab_values[i + 1] if i + 1 < len(tab_values) else [], cols=cols, col_index=actual_col_index)
            compare_rows(exp_row, act_row, row_number)
            matches.append(
                {
                    "row": row_number,
                    "id": normalize_sheet_cell(exp_row[cols.index("id")]) if "id" in cols else "",
                    "title": normalize_sheet_cell(exp_row[cols.index("title")]) if "title" in cols else "",
                }
            )

        strict_ok = header_ok and (expected_asset_count == actual_row_count) and (mismatch_cells == 0)
        id_mode_notes = None

    expected_norm_table = [[normalize_sheet_cell(v) for v in r] for r in expected_rows]
    actual_norm_table: list[list[str]] = [cols]
    for i in range(1, min(len(tab_values), expected_asset_count + 1)):
        actual_norm_table.append(extract_row(row=tab_values[i], cols=cols, col_index=actual_col_index))

    expected_hash = sha256_table(expected_norm_table)
    actual_hash = sha256_table(actual_norm_table)

    now = dt.datetime.now().isoformat(timespec="seconds")
    summary = {
        "timestamp": now,
        "result": "PASS" if strict_ok else "FAIL",
        "sheet_id": args.sheet,
        "tab": args.tab,
        "json": args.json,
        "mode": mode,
        "match_mode": args.match_mode,
        "assets": expected_asset_count,
        "sheet_rows": actual_row_count,
        "columns_compared": len(cols),
        "header_ok": header_ok,
        "mismatch_cells": mismatch_cells,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "diff_preview": diffs,
        "id_mode": id_mode_notes,
    }

    lines: list[str] = []
    lines.append("구글 시트 ↔ iconik API(JSON) 매칭 검증 리포트")
    lines.append(f"- 시각: {now}")
    lines.append(f"- 시트 ID: {args.sheet}")
    lines.append(f"- 탭: {args.tab}")
    lines.append(f"- 기준 JSON: {args.json}")
    lines.append(f"- 비교 모드: {mode} (컬럼 {len(cols)}개)")
    lines.append(f"- 매칭 모드: {args.match_mode}")
    lines.append(f"- 기준 에셋 수: {expected_asset_count}")
    lines.append(f"- 시트 행 수(헤더 제외): {actual_row_count}")
    lines.append(f"- 헤더 일치: {'예' if header_ok else '아니오'}")
    lines.append(f"- 불일치 셀 수: {mismatch_cells}")
    lines.append(f"- SHA256(expected): {expected_hash}")
    lines.append(f"- SHA256(actual):   {actual_hash}")
    lines.append(f"- 결론: {'PASS' if strict_ok else 'FAIL'}")

    if id_mode_notes:
        lines.append(f"- id 기준 누락: {id_mode_notes['missing_in_sheet']}, 추가: {id_mode_notes['extra_in_sheet']}")

    if diffs:
        lines.append("")
        lines.append(f"불일치 예시 (최대 {max(0, args.max_diffs)}개):")
        for d in diffs:
            lines.append(f"- R{d['row']}C[{d['col']}] expected={json.dumps(d['expected'], ensure_ascii=False)} actual={json.dumps(d['actual'], ensure_ascii=False)}")

    # matches output
    if args.print_matches or args.match_preview > 0:
        lines.append("")
        lines.append("매칭(시트 행 ↔ asset):")
        show = matches if args.print_matches else matches[: max(0, args.match_preview)]
        for m in show:
            lines.append(f"- {m['row']}: {m['id']} | {m['title']}")
        if not args.print_matches and len(matches) > max(0, args.match_preview):
            lines.append(f"(미리보기 {len(show)}/{len(matches)}; 전체 출력은 --print-matches)")

    report_text = "\n".join(lines) + "\n"

    if args.out:
        write_text_report(args.out, report_text)
        print(f"Wrote proof report: {args.out}")

    print(report_text)
    if strict_ok:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
