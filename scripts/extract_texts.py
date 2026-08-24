#!/usr/bin/env python3
"""提取 DXF 全部文字（TEXT+MTEXT），按位置排序输出，供阅读理解。

自动解码 CAD 大字体（\\M+）、Unicode（\\U+）与 %% 转义；MTEXT 内嵌格式码
（\\P 换行、\\f 字体、\\H 高度等）在解码后清理。
"""
import sys
import re
import ezdxf

try:
    from extract_texts_stream import resolve_font, decode_bigfont
    _HAVE_DECODE = True
except Exception:
    _HAVE_DECODE = False


def clean_mtext_format(s: str) -> str:
    """解码后的 MTEXT 清理：仅去除 CAD 格式控制码，保留可读文本。"""
    s = s.replace("\\P", "\n").replace("\\p", "\n")
    s = re.sub(r"\{[^}]*\}", "", s)
    s = re.sub(r"\\[A-Za-z][^;\\\n]*;?", "", s)
    s = s.replace("~", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def main():
    if len(sys.argv) < 2:
        print("用法: extract_texts.py <文件.dxf> [输出.txt]")
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None

    doc = ezdxf.readfile(src)
    msp = doc.modelspace()

    # 样式→字体缓存，用于解码 BigFont
    _font = None
    _font_cache = None
    if _HAVE_DECODE:
        try:
            _font, _font_cache = resolve_font(None, src)
        except Exception:
            _font, _font_cache = None, None

    def dec(text, style=""):
        if not _HAVE_DECODE or not text:
            return text
        f = _font
        if f is None and _font_cache and style in _font_cache:
            f = _font_cache[style]
        return decode_bigfont(text, f)

    texts = []
    for e in msp.query("TEXT MTEXT"):
        try:
            pos = e.dxf.insert
            style = getattr(e.dxf, "style", "")
            if e.dxftype() == "MTEXT":
                content = clean_mtext_format(dec(e.text, style))
            else:
                content = dec(e.dxf.text, style).strip()
            if content:
                texts.append((pos.y, pos.x, content))
        except Exception:
            pass

    texts.sort(key=lambda t: (-t[0], t[1]))
    print(f"共提取 {len(texts)} 条文字", file=sys.stderr)

    lines = [f"[{t}]" for _, _, t in texts]
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"已写入: {out}", file=sys.stderr)
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
