#!/usr/bin/env python3
"""解析 DXF 文件并输出结构化报告。

用法:
  python3 parse_dxf.py <file.dxf> [--entities] [--texts] [--layers] [--blocks] [--limits] [--explode-blocks]
"""
import argparse
import sys

try:
    from extract_texts_stream import resolve_font, decode_bigfont
    _HAVE_DECODE = True
except Exception:
    _HAVE_DECODE = False


def main():
    parser = argparse.ArgumentParser(description="解析 DXF 并输出结构化报告")
    parser.add_argument("file", help="DXF 文件路径")
    parser.add_argument("--entities", action="store_true", help="列出所有实体")
    parser.add_argument("--texts", action="store_true", help="提取全部文字标注")
    parser.add_argument("--layers", action="store_true", help="列出图层信息")
    parser.add_argument("--blocks", action="store_true", help="列出块定义")
    parser.add_argument("--limits", action="store_true", help="输出图纸范围")
    parser.add_argument("--explode-blocks", action="store_true", help="展开块引用实体")
    args = parser.parse_args()

    try:
        import ezdxf
    except ImportError:
        print("错误: 未安装 ezdxf，请执行 pip3 install ezdxf", file=sys.stderr)
        sys.exit(1)

    doc = ezdxf.readfile(args.file)
    msp = doc.modelspace()

    # 建立 样式→字体 缓存，用于解码 BigFont(\M+) / \U+ / %% 转义
    _font = None
    _font_cache = None
    if _HAVE_DECODE:
        try:
            _font, _font_cache = resolve_font(None, args.file)
        except Exception:
            _font, _font_cache = None, None

    import re as _re

    def _dec(text, style=""):
        """解码文字：\\M+ 大字体 / \\U+ Unicode / %% 转义；并清理 MTEXT 格式码。"""
        if not _HAVE_DECODE or not text:
            return text
        f = _font
        if f is None and _font_cache and style in _font_cache:
            f = _font_cache[style]
        s = decode_bigfont(text, f)
        # 清理 MTEXT 残留格式码：\P 换行，\...; 格式指令删除
        s = s.replace("\\P", "\n").replace("\\p", "\n")
        s = _re.sub(r"\\[A-Za-z][^;\\\n]*;?", "", s)
        return s.strip()

    # 基础信息
    print(f"== 图纸信息 ==")
    print(f"文件: {args.file}")
    print(f"DXF 版本: {doc.dxfversion}")
    print(f"模型空间实体数: {len(msp)}")

    # 实体类型统计
    counts = {}
    for e in msp:
        t = e.dxftype()
        counts[t] = counts.get(t, 0) + 1
    if counts:
        print(f"实体类型统计: {counts}")

    if args.limits:
        from ezdxf import bbox
        try:
            ext = bbox.extents(msp)
            print(f"图纸范围: min=({ext.extmin.x:.2f},{ext.extmin.y:.2f}) "
                  f"max=({ext.extmax.x:.2f},{ext.extmax.y:.2f})")
        except Exception as e:
            print(f"范围计算失败: {e}")

    if args.layers:
        print(f"\n== 图层 ==")
        for layer in doc.layers:
            print(f"  {layer.dxf.name}: color={layer.dxf.color}, "
                  f"linetype={layer.dxf.linetype}, "
                  f"off={layer.is_off()}, frozen={layer.is_frozen()}")

    if args.blocks:
        print(f"\n== 块定义 ==")
        for block in doc.blocks:
            if block.name.startswith("*"):
                continue
            ents = list(block)
            print(f"  {block.name}: {len(ents)} 个实体, 基点=({block.block_layout.block.dxf.base_point})")

    if args.texts:
        print(f"\n== 文字标注 ==")
        n = 0
        for e in msp.query("TEXT MTEXT"):
            n += 1
            style = getattr(e.dxf, "style", "")
            if e.dxftype() == "MTEXT":
                content = _dec(e.text, style).replace("\n", "\\n")
                pos = e.dxf.insert
                print(f"  MTEXT@{pos}: {content[:200]}")
            else:
                content = _dec(e.dxf.text, style)
                pos = e.dxf.insert
                print(f"  TEXT@{pos}: {content[:200]}")
        if n == 0:
            print("  (无文字实体)")

    if args.entities:
        print(f"\n== 实体清单 ==")
        for e in msp:
            t = e.dxftype()
            layer = e.dxf.layer
            if t == "LINE":
                print(f"  LINE[{layer}] ({e.dxf.start[0]:.2f},{e.dxf.start[1]:.2f}) -> ({e.dxf.end[0]:.2f},{e.dxf.end[1]:.2f})")
            elif t == "CIRCLE":
                print(f"  CIRCLE[{layer}] 圆心=({e.dxf.center[0]:.2f},{e.dxf.center[1]:.2f}) 半径={e.dxf.radius:.2f}")
            elif t == "ARC":
                print(f"  ARC[{layer}] 圆心=({e.dxf.center[0]:.2f},{e.dxf.center[1]:.2f}) 半径={e.dxf.radius:.2f} "
                      f"角度={e.dxf.start_angle:.1f}->{e.dxf.end_angle:.1f}")
            elif t == "TEXT":
                print(f"  TEXT[{layer}] \"{_dec(e.dxf.text, getattr(e.dxf, 'style', ''))}\" @({e.dxf.insert[0]:.2f},{e.dxf.insert[1]:.2f}) 高度={e.dxf.height}")
            elif t == "MTEXT":
                print(f"  MTEXT[{layer}] \"{_dec(e.text, getattr(e.dxf, 'style', ''))[:100]}\" @({e.dxf.insert[0]:.2f},{e.dxf.insert[1]:.2f})")
            elif t == "DIMENSION":
                meas = e.dxf.get("text", "")
                print(f"  DIMENSION[{layer}] 测量值={e.get_measurement():.2f} 文字=\"{meas}\"")
            elif t == "LWPOLYLINE":
                pts = list(e.get_points())
                print(f"  LWPOLYLINE[{layer}] {len(pts)} 顶点 闭合={e.closed} 顶点0=({pts[0][0]:.2f},{pts[0][1]:.2f})")
            elif t == "INSERT":
                print(f"  INSERT[{layer}] 块={e.dxf.name} @({e.dxf.insert[0]:.2f},{e.dxf.insert[1]:.2f}) 缩放={e.dxf.xscale:.2f}")
                if args.explode_blocks:
                    vcp = e.virtual_entities()
                    for ve in vcp:
                        print(f"    ├─ {ve.dxftype()}")
            else:
                print(f"  {t}[{layer}]")


if __name__ == "__main__":
    main()
