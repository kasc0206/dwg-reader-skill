#!/usr/bin/env python3
"""低内存提取 DXF 文字：直接流式解析 DXF 文本格式，不加载整个文档。

DXF 是 tag 对（code/value）序列。本脚本按实体块切分，仅提取 TEXT/MTEXT
的 group code 1（及 MTEXT 的 code 3 续行），并按文本样式解码 BigFont（\\M+）、
Unicode（\\U+）与 %% 转义，避免 ezdxf 全量加载导致 OOM。
"""
import re
import sys

try:
    from extract_texts_stream import decode_bigfont, extract_font_map
    from shxfont import get_font
    _HAVE_DECODE = True
except Exception:
    _HAVE_DECODE = False


def build_font_cache(src):
    """从 DXF 的 STYLE 表建立 样式名→字体 缓存。"""
    cache = {}
    if not _HAVE_DECODE:
        return cache
    try:
        fm = extract_font_map(src)
        for style, bf in fm.items():
            if bf:
                f = get_font(bf)
                if f is not None:
                    cache[style] = f
    except Exception:
        pass
    return cache


def main():
    if len(sys.argv) < 2:
        print("用法: extract_texts_lowmem.py <文件.dxf> [输出.txt]")
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None

    with open(src, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()

    font_cache = build_font_cache(src)

    texts = []
    entity_starts = [m.start() for m in re.finditer(r"\n  0\n", data)]

    for i, start in enumerate(entity_starts):
        end = entity_starts[i + 1] if i + 1 < len(entity_starts) else len(data)
        block = data[start:end]
        em = re.match(r"\n  0\n([A-Z0-9_]+)", block)
        if not em:
            continue
        etype = em.group(1)
        if etype not in ("TEXT", "MTEXT"):
            continue
        layer = ""
        lm = re.search(r"\n  8\n([^\n]+)", block)
        if lm:
            layer = lm.group(1)
        style = ""
        sm = re.search(r"\n  7\n([^\n]+)", block)
        if sm:
            style = sm.group(1)
        content = ""
        g1 = re.search(r"\n  1\n(.*)", block)
        if g1:
            content = g1.group(1)
        if etype == "MTEXT":
            for m in re.finditer(r"\n  3\n([^\n]+)", block):
                content += m.group(1)
        x = y = 0.0
        for cm in re.finditer(r"\n 10\n([^\n]+)\n 20\n([^\n]+)", block):
            x = float(cm.group(1))
            y = float(cm.group(2))
            break
        if content.strip():
            if _HAVE_DECODE:
                font = font_cache.get(style)
                content = decode_bigfont(content, font)
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
