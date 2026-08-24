#!/usr/bin/env python3
"""稳健低内存提取 DXF 全部文字：逐行解析 DXF tag 对，支持 MTEXT 多段。

DXF 文本格式：每两行一个 tag，code 行/value 行。本脚本逐行扫描，
跟踪实体起点（code 0），收集 TEXT/MTEXT 的 code 1 和 code 3 内容。

支持大字体（BigFont）解码：
- `\\U+XXXX` : Unicode 码点
- `\\M+5XXXX`: 优先用 SHX 大字体映射表（--font 参数），回退 GBK 启发式
"""
import re
import sys


def decode_bigfont(s, font=None):
    """解码 CAD 大字体编码。

    格式:
    - \\U+XXXX     : Unicode 码点 (int(s,16))
    - \\M+5XXXX    : BigFont/GBK 编码, 后 4 位为 GBK 两字节码
      (\\M+5A1DD + 数字800 这种相邻文本不会被误吞)

    font: ShxBigFont 实例或 None。提供时优先用字体映射表验证/解码。
    """
    def repl_u(m):
        try:
            return chr(int(m.group(1), 16))
        except Exception:
            return m.group(0)

    def repl_m(m):
        hexstr = m.group(1)
        try:
            code = int(hexstr, 16)
        except ValueError:
            return m.group(0)
        # 优先用字体映射表
        if font is not None:
            ch = font.get_char(code)
            if ch is not None:
                return ch
        # 回退: GBK 启发式
        try:
            return bytes([(code >> 8) & 0xFF, code & 0xFF]).decode("gbk", errors="replace")
        except Exception:
            return m.group(0)

    s = re.sub(r"\\U\+([0-9A-Fa-f]{4})", repl_u, s)
    s = re.sub(r"\\M\+5([0-9A-Fa-f]{4})", repl_m, s)
    s = decode_percent_escapes(s)
    return s


# AutoCAD %% 转义序列 → Unicode（key 为 %% 后的单个字母，小写）
PERCENT_ESCAPES = {
    "c": "Ø",
    "d": "°",
    "p": "±",
    "%": "%",
    "u": "",
    "o": "",
}


def decode_percent_escapes(s):
    """解码 AutoCAD `%%` 转义序列（%%C/%%D/%%P/%%%/%%数字，大小写不敏感）。"""
    def repl(m):
        code = m.group(1).lower()
        if code in PERCENT_ESCAPES:
            return PERCENT_ESCAPES[code]
        try:
            n = int(m.group(1), 10)
            if n < 256:
                return chr(n)
        except ValueError:
            pass
        return m.group(0)

    return re.sub(r"%%([A-Za-z%]|\d{1,3})", repl, s)


def load_font(font_arg):
    """加载字体，返回 ShxBigFont 或 None。"""
    if not font_arg:
        return None
    try:
        from shxfont import ShxBigFont
        return ShxBigFont(font_arg)
    except Exception as e:
        print(f"字体加载失败({font_arg}): {e}", file=sys.stderr)
        return None


def extract_font_map(src):
    """从 DXF 的 STYLE 表提取字体映射。

    返回 {style_name: bigfont_name}，供解码时按文本样式选用字体。
    大字体文件名常含 `\\M+` 编码，需一并解码。
    """
    font_map = {}
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        # 解析 STYLE 表条目: code 2=样式名, code 3=字体, code 4=大字体
        entries = re.findall(
            r"\n  0\nSTYLE\n(.*?)(?=\n  0\n)", data, re.S
        )
        for block in entries:
            name = re.search(r"\n  2\n([^\n]+)", block)
            bigfont = re.search(r"\n  4\n([^\n]+)", block)
            if name and bigfont:
                style = name.group(1)
                bf = bigfont.group(1)
                if bf and bf.lower() != "txt.shx":
                    # 解码样式名/字体名中的 \M+ 编码
                    style = decode_bigfont(style)
                    bf = decode_bigfont(bf)
                    font_map[style] = bf
    except Exception as e:
        print(f"STYLE 表解析失败: {e}", file=sys.stderr)
    return font_map


def resolve_font(font_path, src):
    """解析字体：优先 --font 参数，否则从 STYLE 表自动匹配。"""
    if font_path:
        return load_font(font_path), None
    # 自动模式：解析 STYLE 表，收集所需大字体
    font_map = extract_font_map(src)
    if not font_map:
        return None, None
    from shxfont import get_font
    cache = {}
    for style, bf in font_map.items():
        if bf:
            cache[style] = get_font(bf)
    return None, cache


def main():
    if len(sys.argv) < 2:
        print("用法: extract_texts_stream.py <文件.dxf> [输出.txt] [--font 字体.shx]")
        sys.exit(1)
    src = sys.argv[1]
    out = None
    font_path = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--font" and i + 1 < len(sys.argv):
            font_path = sys.argv[i + 1]
            i += 2
        else:
            out = sys.argv[i]
            i += 1

    # 解析字体：--font 显式指定 或 从 STYLE 表自动
    font = None
    font_cache = None  # {style_name: ShxBigFont}
    if font_path:
        font = load_font(font_path)
    else:
        font, font_cache = resolve_font(None, src)
        if font_cache:
            n = sum(1 for v in font_cache.values() if v is not None)
            print(f"自动匹配 {n} 个大字体", file=sys.stderr)

    texts = []
    cur_entity = None
    cur_content = []
    cur_x = cur_y = 0.0
    cur_point_done = False  # 是否已捕获本实体的第一对 (10,20) 插入点
    cur_layer = ""
    cur_style = ""
    cur_type = ""
    cur_code = None
    cur_value = None

    def flush():
        nonlocal cur_entity, cur_content, cur_x, cur_y, cur_layer, cur_type, cur_style, cur_point_done
        if cur_entity and cur_content:
            # 按文本样式选择字体（自动模式）
            entity_font = font
            if entity_font is None and font_cache and cur_style in font_cache:
                entity_font = font_cache[cur_style]
            content = decode_bigfont("".join(cur_content), entity_font)
            if content.strip():
                texts.append((cur_y, cur_x, cur_type, cur_layer, content))
        cur_entity = None
        cur_content = []
        cur_type = ""
        cur_x = cur_y = 0.0
        cur_point_done = False
        cur_layer = ""
        cur_style = ""

    with open(src, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\n").strip()
            if cur_code is None:
                cur_code = s
                continue
            cur_value = s
            try:
                code = int(cur_code)
            except ValueError:
                cur_code = None
                continue

            if code == 0:
                flush()
                cur_entity = cur_value
                cur_type = cur_value
                cur_point_done = False
            elif code == 8:
                cur_layer = cur_value
            elif code == 7:
                # 文本样式名（TEXT/MTEXT 的 style 属性）
                if cur_entity in ("TEXT", "MTEXT"):
                    cur_style = cur_value
            elif code == 10 and not cur_point_done:
                # 捕获本实体的第一对 (10,20) 作为插入点；
                # 不判断是否为零，避免 X=0 时 Y 被清零
                try:
                    cur_x = float(cur_value)
                except ValueError:
                    pass
            elif code == 20 and not cur_point_done:
                try:
                    cur_y = float(cur_value)
                except ValueError:
                    pass
                cur_point_done = True
            elif code in (1, 3):
                if cur_entity in ("TEXT", "MTEXT"):
                    # code 1: TEXT 正文 / MTEXT 首段; code 3: MTEXT 后续段
                    if code == 1 or cur_content:
                        cur_content.append(cur_value)
            cur_code = None

    flush()
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
