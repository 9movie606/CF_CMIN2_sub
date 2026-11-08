#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate region-labelled IP lists and a static GitHub Pages website.

Input:  data/ip_list.txt
Output: dist/ (ready to publish with GitHub Pages)
Requires Python 3.9+; standard library only.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "ip_list.txt"
DEFAULT_OUTPUT = ROOT / "dist"

# Canonical simplified-Chinese province-level names accepted by the data file.
PROVINCE_SLUGS = {
    "北京": "beijing", "天津": "tianjin", "上海": "shanghai", "重庆": "chongqing",
    "河北": "hebei", "山西": "shanxi", "辽宁": "liaoning", "吉林": "jilin",
    "黑龙江": "heilongjiang", "江苏": "jiangsu", "浙江": "zhejiang", "安徽": "anhui",
    "福建": "fujian", "江西": "jiangxi", "山东": "shandong", "河南": "henan",
    "湖北": "hubei", "湖南": "hunan", "广东": "guangdong", "海南": "hainan",
    "四川": "sichuan", "贵州": "guizhou", "云南": "yunnan", "陕西": "shaanxi",
    "甘肃": "gansu", "青海": "qinghai", "内蒙古": "neimenggu", "广西": "guangxi",
    "西藏": "xizang", "宁夏": "ningxia", "新疆": "xinjiang", "香港": "hongkong",
    "澳门": "macau", "台湾": "taiwan",
}
PROVINCES = set(PROVINCE_SLUGS)
INVALID_MARKERS = ("待测", "未知", "无", "待確認", "待确认")


class DataError(ValueError):
    """An input-data validation error with source line context."""


def parse_endpoint(raw: str, line_no: int) -> tuple[tuple[str, int], str]:
    """Return canonical uniqueness key and display endpoint.

    IPv4:port and IPv4 are accepted. IPv6 must be bracketed when a port is
    supplied (for example [2001:db8::1]:443); bare IPv6 defaults to 443.
    """
    raw = raw.strip()
    if not raw:
        raise DataError(f"第 {line_no} 行：缺少 IP")

    if raw.startswith("["):
        close = raw.find("]")
        if close < 0:
            raise DataError(f"第 {line_no} 行：IPv6 格式错误：{raw}")
        ip_text = raw[1:close]
        suffix = raw[close + 1:]
        if suffix and not suffix.startswith(":"):
            raise DataError(f"第 {line_no} 行：IP/端口格式错误：{raw}")
        port_text = suffix[1:] if suffix else None
        if suffix == ":":
            raise DataError(f"第 {line_no} 行：端口不能为空")
    elif raw.count(":") > 1:
        ip_text, port_text = raw, None
    elif ":" in raw:
        ip_text, port_text = raw.rsplit(":", 1)
        if not port_text:
            raise DataError(f"第 {line_no} 行：端口不能为空")
    else:
        ip_text, port_text = raw, None

    try:
        ip_obj = ipaddress.ip_address(ip_text)
    except ValueError as exc:
        raise DataError(f"第 {line_no} 行：IP 地址无效：{ip_text}") from exc

    if port_text is None or port_text == "":
        port = 443
    else:
        if not port_text.isdecimal():
            raise DataError(f"第 {line_no} 行：端口必须是整数：{port_text}")
        port = int(port_text)
    if not 1 <= port <= 65535:
        raise DataError(f"第 {line_no} 行：端口必须介于 1 至 65535：{port}")

    ip = ip_obj.compressed
    endpoint = f"[{ip}]:{port}" if ip_obj.version == 6 else f"{ip}:{port}"
    return (ip, port), endpoint


def parse_regions(raw: str, line_no: int) -> list[tuple[str, str | None]]:
    """Parse region tokens, promoting 2+ cities in one province to province scope.

    A record may cover a province and a city in another province, e.g.
    广东,江苏/南京. A province and a city within the *same* province in one
    record is contradictory and rejected.
    """
    raw = raw.strip().replace("，", ",").replace("、", ",").replace("；", ",")
    if not raw:
        raise DataError(f"第 {line_no} 行：缺少适用地区")

    tokens = [part.strip() for part in raw.split(",")]
    if any(not token for token in tokens):
        raise DataError(f"第 {line_no} 行：地区列表中有空项目")
    if len(tokens) != len(set(tokens)):
        raise DataError(f"第 {line_no} 行：同一地区重复标注")

    province_scopes: set[str] = set()
    city_scopes: dict[str, set[str]] = defaultdict(set)
    for token in tokens:
        if token.count("/") > 1:
            raise DataError(f"第 {line_no} 行：地区格式错误：{token}")
        if "/" in token:
            province, city = (part.strip() for part in token.split("/", 1))
            if province not in PROVINCES:
                raise DataError(f"第 {line_no} 行：未知省级地区：{province}")
            if not city or any(mark in city for mark in INVALID_MARKERS) or "?" in city or "？" in city:
                raise DataError(f"第 {line_no} 行：城市名称为空或含不确定标记：{token}")
            if any(ch in city for ch in "|,#/\\"):
                raise DataError(f"第 {line_no} 行：城市名称含非法字符：{city}")
            city_scopes[province].add(city)
        else:
            if token not in PROVINCES:
                raise DataError(f"第 {line_no} 行：未知省级地区：{token}")
            province_scopes.add(token)

    for province in list(city_scopes):
        if province in province_scopes:
            raise DataError(f"第 {line_no} 行：同一记录不能同时标注 {province} 省级和 {province} 城市级范围")
        if len(city_scopes[province]) >= 2:
            # Per the agreed rule, coverage in two or more cities means province-wide.
            province_scopes.add(province)
            del city_scopes[province]

    regions = [(province, None) for province in sorted(province_scopes)]
    regions.extend((province, city) for province in sorted(city_scopes)
                   for city in sorted(city_scopes[province]))
    if not regions:
        raise DataError(f"第 {line_no} 行：没有有效地区")
    return regions


def load_records(input_path: Path) -> dict[tuple[str, int], dict]:
    """Load and validate input. Duplicate IP:port records are rejected."""
    records: dict[tuple[str, int], dict] = {}
    errors: list[str] = []
    try:
        lines = input_path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise DataError("输入文件不是有效 UTF-8 编码，请另存为 UTF-8。") from exc

    for line_no, line in enumerate(lines, 1):
        content = line.strip()
        if not content or content.startswith("#"):
            continue
        if "|" not in content:
            errors.append(f"第 {line_no} 行：缺少 | 分隔符")
            continue
        endpoint_text, region_text = content.split("|", 1)
        try:
            key, endpoint = parse_endpoint(endpoint_text, line_no)
            regions = parse_regions(region_text, line_no)
            if key in records:
                first = records[key]
                errors.append(
                    f"第 {line_no} 行：重复节点 {endpoint}（首次出现在第 {first['line']} 行）；"
                    "请将适用地区合并到同一行"
                )
                continue
            records[key] = {"endpoint": endpoint, "regions": regions, "line": line_no}
        except DataError as exc:
            errors.append(str(exc))

    if errors:
        raise DataError("\n".join(errors))
    if not records:
        raise DataError("没有找到任何有效节点。")
    return records


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT) -> dict:
    records = load_records(input_path)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    province_records: dict[str, set[str]] = defaultdict(set)
    city_records: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_output: list[str] = []
    all_json: list[dict] = []

    for record in records.values():
        endpoint = record["endpoint"]
        regions = record["regions"]
        labels = [province if city is None else f"{province}/{city}"
                  for province, city in regions]
        all_output.append(f"{endpoint}#{','.join(labels)}")
        all_json.append({"endpoint": endpoint, "regions": labels})
        for province, city in regions:
            if city is None:
                province_records[province].add(endpoint)
            else:
                city_records[(province, city)].add(endpoint)

    # Province lists intentionally contain province-wide nodes only.
    for province, endpoints in province_records.items():
        slug = PROVINCE_SLUGS[province]
        write_lines(output_dir / "province" / f"{slug}.txt",
                    [f"{endpoint}#{province}" for endpoint in sorted(endpoints)])

    index_regions = []
    all_provinces = sorted(set(province_records) | {province for province, _ in city_records})
    for province in all_provinces:
        province_slug = PROVINCE_SLUGS[province]
        province_endpoints = province_records.get(province, set())
        city_list = []
        city_names = sorted(city for p, city in city_records if p == province)
        for city in city_names:
            own = city_records[(province, city)]
            combined = province_endpoints | own
            city_file = output_dir / "city" / province_slug / f"{city}.txt"
            write_lines(city_file,
                        [f"{endpoint}#{province}-{city}" for endpoint in sorted(combined)])
            url_city = quote(city, safe="")
            city_list.append({
                "name": city,
                "id": city,
                "city_count": len(own),
                "province_count_included": len(province_endpoints),
                "total_count": len(combined),
                "url": f"city/{province_slug}/{url_city}.txt",
            })

        province_url = f"province/{province_slug}.txt" if province_endpoints else None
        index_regions.append({
            "name": province,
            "id": province_slug,
            "province_count": len(province_endpoints),
            "province_url": province_url,
            "cities": city_list,
        })

    write_lines(output_dir / "all.txt", sorted(all_output))
    (output_dir / "all.json").write_text(
        json.dumps(all_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    index = {
        "updated": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "total": len(records),
        "province_total": len(province_records),
        "city_total": len(city_records),
        "regions": index_regions,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    web_dir = ROOT / "web"
    for filename in ("index.html", "style.css", "app.js"):
        shutil.copy2(web_dir / filename, output_dir / filename)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="生成地区 IP TXT 订阅和静态查询网页")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="原始资料 TXT 路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="生成目录，默认 dist/")
    args = parser.parse_args()
    try:
        index = build(args.input, args.output)
    except (DataError, OSError) as exc:
        print(f"生成失败：\n{exc}", file=sys.stderr)
        return 1
    city_count = sum(len(region["cities"]) for region in index["regions"])
    print("生成成功")
    print(f"唯一节点：{index['total']}")
    print(f"有省级订阅的省份：{index['province_total']}")
    print(f"有城市专用资料的城市：{city_count}")
    print(f"输出目录：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
