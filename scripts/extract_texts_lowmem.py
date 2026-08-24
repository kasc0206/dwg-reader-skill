#!/usr/bin/env python3
"""低内存提取 DXF 文字：直接流式解析 DXF 文本格式，不加载整个文档。

DXF 是 tag 对（code/value）序列。本脚本仅用正则定位 TEXT/MTEXT 实体
的 group code 1（及 MTEXT 的 code 3 续行），避免 ezdxf 全量加载导致 OOM。
"""
import re
import sys

TEXT_ENTITY = re.compile(r"^(\d+)$\s*^0$", re.M)
# group code 1 值（TEXT 正文 / MTEXT 首行内容）
GC1 = re.compile(r"^  1$\n(.*)$", re.M)
GC3 = re.compile(r"^  3$\n(.*)$", re.M)


def main():
    if len(sys.argv) < 2:
        print("用法: extract_texts_lowmem.py <文件.dxf> [输出.txt]")
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None

    with open(src, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()

    # 按实体块切分：每个实体以 "\n  0\n  实体类型\n" 开头
    # 简化：逐段匹配实体类型与 group code 1/3
    texts = []
    # 定位所有实体起点
    entity_starts = [m.start() for m in re.finditer(r"\n  0\n", data)]

    for i, start in enumerate(entity_starts):
        end = entity_starts[i + 1] if i + 1 < len(entity_starts) else len(data)
        block = data[start:end]
        # 实体类型
        em = re.match(r"\n  0\n([A-Z0-9_]+)", block)
        if not em:
            continue
        etype = em.group(1)
        if etype not in ("TEXT", "MTEXT"):
            continue
        # 图层 (code 8) - 可选
        layer = ""
        lm = re.search(r"\n  8\n([^\n]+)", block)
        if lm:
            layer = lm.group(1)
        # group code 1（正文）
        g1 = re.search(r"\n  1\n(.*)", block)
        # MTEXT 可能有 code 3 续行
        content = ""
        if g1:
            content = g1.group(1)
        if etype == "MTEXT":
            for m in re.finditer(r"\n  3\n([^\n]+)", block):
                content += m.group(1)
        # 插入点 (code 10) 坐标
        x = y = 0.0
        for cm in re.finditer(r"\n 10\n([^\n]+)\n 20\n([^\n]+)", block):
            x = float(cm.group(1))
            y = float(cm.group(2))
            break
        if content.strip():
            texts.append((y, x, etype, layer, content))

    texts.sort(key=lambda t: (-t[0], t[1]))
    print(f"共提取 {len(texts)} 条文字", file=sys.stderr)

    lines = [f"[{t[4]}]" for t in texts]
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"已写入: {out}", file=sys.stderr)
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
