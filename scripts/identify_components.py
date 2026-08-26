#!/usr/bin/env python3
"""识别图纸中的构件（门/窗/梁/柱/钢筋/楼梯/电梯/墙/板/基础/管道/设备/家具/轴线/标高/详图）。

匹配依据：
  1. INSERT 块名正则（component_rules.json 的 block_re）
  2. 图层名正则（layer_re）
  3. 两者取并集；按构件类型聚合输出（类型/数量/图层/示例块名/位置范围）

用法：
  python3 identify_components.py <文件.dxf> [--rules 自定义.json] [--json] [--out 输出.md]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RULES = os.path.join(HERE, "component_rules.json")


def load_rules(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = data.get("rules", []) if isinstance(data, dict) else data
    compiled = []
    for r in rules:
        try:
            compiled.append({
                "name": r["name"],
                "block_re": re.compile(r["block_re"], re.IGNORECASE),
                "layer_re": re.compile(r["layer_re"], re.IGNORECASE),
            })
        except re.error as e:
            sys.stderr.write(f"[warn] 规则 {r.get('name')} 正则错误: {e}\n")
    return compiled


def main():
    ap = argparse.ArgumentParser(description="识别图纸中的构件")
    ap.add_argument("file", help="DXF 文件路径")
    ap.add_argument("--rules", default=DEFAULT_RULES, help="规则 JSON 文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    ap.add_argument("--out", help="输出文件（默认 stdout）")
    args = ap.parse_args()

    rules = load_rules(args.rules)

    try:
        import ezdxf
    except ImportError:
        print("错误: 未安装 ezdxf", file=sys.stderr)
        sys.exit(1)

    try:
        doc = ezdxf.readfile(args.file, errors="ignore")
    except Exception as e:
        # 降级流式提取 INSERT 与图层
        sys.stderr.write(f"[warn] ezdxf 解析失败（{e}），降级为流式提取。\n")
        comps = _stream_extract_components(args.file, rules)
        _emit(args, comps, degraded=True)
        return

    msp = doc.modelspace()
    comps = {}  # name -> {"count":int, "layers":set, "blocks":set, "positions":[]}
    unmatched_inserts = 0

    # 收集所有要扫描的实体：模型空间 + 非匿名 block 定义内实体
    # （某些不规范图纸把主体内容放在 block 定义里，模型空间无 INSERT 引用）
    scan_iter = list(msp)
    for b in doc.blocks:
        if b.name.startswith("*"):
            continue
        try:
            scan_iter.extend(list(b))
        except Exception:
            pass

    for e in scan_iter:
        t = e.dxftype()
        layer = ""
        try:
            layer = e.dxf.layer
        except Exception:
            pass
        block_name = ""
        is_insert = (t == "INSERT")
        if is_insert:
            try:
                block_name = e.dxf.name or ""
            except Exception:
                pass

        # 跳过 DEFPOINTS 和纯几何实体（LINE/LWPOLYLINE）的图层匹配，避免误判
        if layer.upper() == "DEFPOINTS" or t in ("LINE", "LWPOLYLINE", "CIRCLE", "ARC", "POINT"):
            # 但 INSERT 在 DEFPOINTS 上仍处理
            if not is_insert:
                continue

        matched = False
        for r in rules:
            hit_block = bool(block_name and r["block_re"].search(block_name))
            hit_layer = bool(layer and r["layer_re"].search(layer))
            if hit_block or hit_layer:
                matched = True
                entry = comps.setdefault(r["name"], {
                    "count": 0, "layers": set(), "blocks": set(), "positions": []
                })
                entry["count"] += 1
                if layer:
                    entry["layers"].add(layer)
                if block_name:
                    entry["blocks"].add(block_name)
                try:
                    p = e.dxf.insert
                    entry["positions"].append((round(p[0], 1), round(p[1], 1)))
                except Exception:
                    pass
                break  # 一个实体只归入第一个命中的规则
        if not matched and is_insert and block_name and not block_name.startswith("*"):
            unmatched_inserts += 1

    # 整理输出结构
    out_comps = []
    for name, e in sorted(comps.items(), key=lambda kv: -kv[1]["count"]):
        xs = [p[0] for p in e["positions"]]
        ys = [p[1] for p in e["positions"]]
        bbox = None
        if xs:
            bbox = {
                "xmin": round(min(xs), 1), "xmax": round(max(xs), 1),
                "ymin": round(min(ys), 1), "ymax": round(max(ys), 1),
            }
        out_comps.append({
            "name": name,
            "count": e["count"],
            "layers": sorted(e["layers"]),
            "blocks": sorted(e["blocks"])[:5],  # 示例最多5个
            "bbox": bbox,
        })

    result = {
        "file": args.file,
        "total_components": sum(c["count"] for c in out_comps),
        "by_type": out_comps,
        "unmatched_inserts": unmatched_inserts,
    }
    _emit(args, result, degraded=False)


def _emit(args, result, degraded):
    if args.json:
        # 处理 set 不可序列化
        def safe(o):
            if isinstance(o, set):
                return sorted(o)
            if isinstance(o, dict):
                return {k: safe(v) for k, v in o.items()}
            if isinstance(o, list):
                return [safe(x) for x in o]
            return o
        out = json.dumps(result, ensure_ascii=False, indent=2, default=safe)
    else:
        out = _to_markdown(result, degraded)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"已写入: {args.out}", file=sys.stderr)
    else:
        print(out)


def _to_markdown(result, degraded=False):
    lines = [f"# 构件识别 — {os.path.basename(result.get('file',''))}", ""]
    lines.append(f"**文件**: `{result.get('file','')}`")
    lines.append(f"**已识别构件总数**: {result.get('total_components', 0)}")
    if degraded:
        lines.append("> _注：ezdxf 解析失败，已降级为流式提取；结果可能不完整。_")
    lines.append("")
    by_type = result.get("by_type", [])
    if by_type:
        lines.append("## 按构件类型")
        lines.append("| 构件 | 数量 | 图层 | 示例块名 | 位置范围 |")
        lines.append("|------|------|------|----------|----------|")
        for c in by_type:
            layers = ", ".join(c["layers"]) or "—"
            blocks = ", ".join(c["blocks"]) or "—"
            bbox = c.get("bbox")
            if bbox:
                bbox_str = f"X:{bbox['xmin']}~{bbox['xmax']} Y:{bbox['ymin']}~{bbox['ymax']}"
            else:
                bbox_str = "—"
            lines.append(f"| {c['name']} | {c['count']} | {layers} | {blocks} | {bbox_str} |")
        lines.append("")
    um = result.get("unmatched_inserts", 0)
    if um:
        lines.append(f"_另有 {um} 个未匹配规则的 INSERT 块参照（可扩展 component_rules.json 覆盖更多类型）。_")
    if not by_type:
        lines.append("_未识别到任何构件。可检查 component_rules.json 或扩展规则。_")
    return "\n".join(lines)


def _stream_extract_components(path, rules):
    """ezdxf 失败时的流式降级：仅按 INSERT 块名 + 图层名匹配。"""
    try:
        from extract_texts_stream import _read_text
    except Exception:
        def _read_text(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    text = _read_text(path)
    lines = text.splitlines()
    comps = {}
    unmatched = 0
    i = 0
    cur_block = None
    cur_layer = ""
    cur_insert = None
    while i < len(lines) - 1:
        code_str = lines[i].strip()
        value = lines[i + 1]
        try:
            code = int(code_str)
        except ValueError:
            i += 1
            continue
        if code == 0:
            # flush 上一个 INSERT
            if cur_insert is not None:
                _match_insert(comps, rules, cur_block, cur_layer)
                if cur_block and not cur_block.startswith("*") and not any(
                    r["block_re"].search(cur_block) or r["layer_re"].search(cur_layer)
                    for r in rules
                ):
                    unmatched += 1
            if value.strip() == "INSERT":
                cur_insert = True
                cur_block = ""
                cur_layer = ""
            else:
                cur_insert = None
        elif cur_insert is not None:
            if code == 2:
                cur_block = value.strip()
            elif code == 8:
                cur_layer = value.strip()
        i += 2
    # flush 最后
    if cur_insert is not None and cur_block:
        _match_insert(comps, rules, cur_block, cur_layer)
    out = []
    for name, e in sorted(comps.items(), key=lambda kv: -kv[1]["count"]):
        out.append({
            "name": name,
            "count": e["count"],
            "layers": sorted(e["layers"]),
            "blocks": sorted(e["blocks"])[:5],
            "bbox": None,
        })
    return {
        "file": path,
        "total_components": sum(c["count"] for c in out),
        "by_type": out,
        "unmatched_inserts": unmatched,
    }


def _match_insert(comps, rules, block_name, layer):
    for r in rules:
        hit_block = bool(block_name and r["block_re"].search(block_name))
        hit_layer = bool(layer and r["layer_re"].search(layer))
        if hit_block or hit_layer:
            entry = comps.setdefault(r["name"], {
                "count": 0, "layers": set(), "blocks": set()
            })
            entry["count"] += 1
            if layer:
                entry["layers"].add(layer)
            if block_name:
                entry["blocks"].add(block_name)
            break


if __name__ == "__main__":
    main()
