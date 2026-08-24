#!/usr/bin/env python3
"""SHX 大字体反编译为 SHP 文本（decompile）。

等价于 AutoCAD 的 DUMPSHX / shx2shp 工具：
- 解析 bigfont SHX 二进制
- 输出 SHP 文本格式（每字符一个定义：*shape_number,count,name + 数据行）

用法:
  python3 shx_decompile.py <字体.shx> [输出.shp]
"""
from __future__ import annotations

import sys
from shxfont import ShxBigFont


def shape_data_str(data: bytes) -> str:
    """将字形数据格式化为 SHP 文本数据行（逗号分隔的十进制数）。"""
    out = []
    line = []
    for b in data:
        line.append(str(b))
        if len(line) >= 20:  # 每行 20 个数
            out.append(",".join(line))
            line = []
    if line:
        out.append(",".join(line))
    return "\n".join(out)


def decompile(font: ShxBigFont) -> str:
    """反编译 bigfont 为 SHP 文本。"""
    lines = []
    # 大字体头：*BIGFONT nchars,nranges,b1,e1,...
    lines.append(f"*BIGFONT {len(font)},1,0A1,0FE")
    lines.append("*0,4,font-name")
    lines.append("0,0,0,0")
    # 每个 shape 一个定义
    for code in sorted(font.shapes):
        data = font.shapes[code]
        if code == 0:
            continue
        # 字符名：取数据前 2 字节的 GBK 码
        ch = font.get_char(code)
        name = ch if ch else f"c{code:04X}"
        lines.append(f"*{code:04X},{len(data)},{name}")
        lines.append(shape_data_str(data))
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: shx_decompile.py <字体.shx> [输出.shp]")
        sys.exit(1)
    font = ShxBigFont(sys.argv[1])
    text = decompile(font)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已反编译: {sys.argv[2]} ({len(font)} shapes)")
    else:
        print(text)


if __name__ == "__main__":
    main()
