#!/usr/bin/env python3
"""一站式 DWG/DXF 图纸阅读流水线。

自动完成：
  1. 若输入是 DWG，调用 ODA File Converter 转为 DXF（与源文件同目录）
  2. 解析 DXF 输出结构化报告（实体 / 图层 / 块 / 尺寸 / 范围）
  3. 提取全部文字标注（TEXT + MTEXT + 块内文字 + ATTRIB + DIMENSION）
     支持 BigFont/Unicode/%% 解码、阅读顺序还原、表格/图层聚合

用法：
  python3 dwg_read.py <图纸.dwg|图纸.dxf> [--out 报告.md]
                      [--table] [--by-layer] [--no-convert] [--font 字体.shx]

  --table     以 Markdown 表格还原对齐网格（如门窗表）
  --by-layer  按图层聚合输出文字
  --no-convert 跳过 DWG→DXF 转换（输入已是 DXF 时加速）
  --font      显式指定大字体文件（默认按 STYLE 表自动匹配 fonts/）

输出默认打印到 stdout；指定 --out 则写入文件并打印摘要到 stderr。
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ODA = "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
PARSE = os.path.join(HERE, "parse_dxf.py")
STREAM = os.path.join(HERE, "extract_texts_stream.py")


def _run(script, dxf, *extra):
    cmd = [sys.executable, script, dxf, *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"[warn] {os.path.basename(script)} 失败: {r.stderr.strip()}\n")
    return r.stdout


def convert_dwg(dwg):
    """用 ODA 把 DWG 转为同目录下的 DXF，返回 DXF 路径。失败返回 None。"""
    if not os.path.exists(ODA):
        sys.stderr.write(f"[error] 未找到 ODA File Converter: {ODA}\n")
        return None
    indir = os.path.dirname(os.path.abspath(dwg)) or "."
    outdir = indir  # 与源文件同目录
    name = os.path.splitext(os.path.basename(dwg))[0]
    target = os.path.join(outdir, name + ".dxf")
    # ODA 命令行签名：输入目录 输出目录 版本 DXF 递归 审计 过滤器
    cmd = [ODA, indir, outdir, "ACAD2018", "DXF", "0", "0", "*.dwg"]
    sys.stderr.write(f"[info] 调用 ODA 转换 DWG → DXF: {dwg}\n")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"[error] ODA 转换失败: {r.stderr.strip() or r.stdout.strip()}\n")
        return None
    if not os.path.exists(target):
        sys.stderr.write(f"[error] ODA 未生成预期 DXF: {target}\n")
        return None
    sys.stderr.write(f"[info] 已生成 DXF: {target}\n")
    return target


def resolve_dxf(src, no_convert):
    ext = os.path.splitext(src)[1].lower()
    if ext == ".dwg":
        if no_convert:
            dxf = os.path.splitext(src)[0] + ".dxf"
            if not os.path.exists(dxf):
                sys.stderr.write(f"[error] --no-convert 但找不到 {dxf}\n")
                return None
            return dxf
        return convert_dwg(src)
    if ext == ".dxf":
        return src
    sys.stderr.write(f"[error] 不支持的文件类型: {src}（仅支持 .dwg / .dxf）\n")
    return None


def main():
    ap = argparse.ArgumentParser(description="DWG/DXF 图纸阅读一站式流水线")
    ap.add_argument("file", help="DWG 或 DXF 文件路径")
    ap.add_argument("--out", help="报告输出文件（默认打印到 stdout）")
    ap.add_argument("--table", action="store_true", help="Markdown 表格还原")
    ap.add_argument("--by-layer", action="store_true", help="按图层聚合文字")
    ap.add_argument("--no-convert", action="store_true", help="跳过 DWG→DXF 转换")
    ap.add_argument("--font", help="显式指定大字体文件")
    args = ap.parse_args()

    dxf = resolve_dxf(args.file, args.no_convert)
    if not dxf:
        sys.exit(1)

    parts = []
    parts.append("# 图纸解析报告\n")
    parts.append(f"> 源文件: `{os.path.basename(args.file)}`  | 解析文件: `{dxf}`\n")

    # 1. 结构化报告（parse_dxf.py --entities --texts --layers --blocks --limits）
    report = _run(PARSE, dxf, "--entities", "--texts", "--layers",
                  "--blocks", "--limits")
    if report.strip():
        parts.append("## 结构化解析\n")
        parts.append(report.rstrip("\n"))
    else:
        parts.append("## 结构化解析\n")
        parts.append("> ⚠️ ezdxf 严格解析失败（文件可能损坏 / 缺 EOF）。"
                     "已跳过结构化报告，下方文字提取基于流式解析，结果仍可用。")

    # 2. 文字提取（extract_texts_stream.py）
    extra = []
    if args.table:
        extra.append("--table")
    if args.by_layer:
        extra.append("--by-layer")
    if args.font:
        extra += ["--font", args.font]
    texts = _run(STREAM, dxf, *extra)
    if texts.strip():
        title = "## 文字标注提取"
        if args.table:
            title += "（表格）"
        elif args.by_layer:
            title += "（按图层）"
        parts.append("\n" + title + "\n")
        parts.append(texts.rstrip("\n"))

    blob = "\n".join(parts).rstrip("\n") + "\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(blob)
        sys.stderr.write(f"[info] 报告已写入: {args.out}\n")
    else:
        print(blob)


if __name__ == "__main__":
    main()
