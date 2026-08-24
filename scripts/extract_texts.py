#!/usr/bin/env python3
"""提取 DXF 全部文字（TEXT+MTEXT），按位置排序输出，供阅读理解。"""
import sys
import re
import ezdxf


def clean_mtext(raw):
    """清理 MTEXT 内嵌格式代码，保留可读文本。"""
    s = raw
    s = s.replace("\\P", "\n").replace("\\p", "\n")
    s = re.sub(r"\{[^}]*\}", "", s)
    s = re.sub(r"\\[A-Za-z][^;\\\n]*;?", "", s)
    s = re.sub(r"\\[A-Za-z]", "", s)
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

    texts = []
    for e in msp.query("TEXT MTEXT"):
        try:
            pos = e.dxf.insert
            if e.dxftype() == "MTEXT":
                content = clean_mtext(e.text)
            else:
                content = e.dxf.text.strip()
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
