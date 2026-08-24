# DWG Reader Skill

读取 DWG/DXF 工程图纸，提取图层、实体、文字标注、尺寸信息，支持中英文及多语言编码，输出结构化解析报告供阅读理解。

## 核心能力

- **DWG → DXF 转换**：通过 ODA File Converter 命令行批量转换
- **一站式流水线**：`dwg_read.py` 自动转换 + 结构化报告 + 文字提取，输出 Markdown
- **图纸解析**：实体清单（LINE/CIRCLE/ARC/TEXT/MTEXT/DIMENSION 等）、文字提取、图层信息、尺寸信息
- **块内文字与属性**：INSERT 自动展开（含缩放/旋转/镜像变换）、ATTRIB 属性提取、匿名块主体文字直提
- **表格还原**：`--table` 按几何对齐还原 Markdown 表格（门窗表/材料表）
- **阅读顺序**：几何感知排序（先分栏、栏内上→下左→右），适配多栏图纸
- **按图层聚合**：`--by-layer` 按专业图层分组输出
- **MTEXT 堆叠**：`\S`（分数/公差）解码为 `top/bottom`，剥离 `\H` 高度控制码
- **全字体支持**：内置 322 个 SHX 字体（约 159MB），覆盖中文 GBK、韩文 cp949、日文 shift_jis、西文 unifont
- **自动字体匹配**：解析 DXF 的 STYLE 表，按文本样式自动匹配字体库（支持路径前缀/大小写/后缀容错），无需手动指定
- **符号支持**：AutoCAD `%%` 转义序列（%%C→Ø、%%D→°、%%P→±）、`\U+XXXX` Unicode、`\M+5XXXX` bigfont 符号区
- **SHX 反编译**：大字体 SHX → SHP 文本（等价 DUMPSHX / shx2shp 工具）
- **低内存提取**：大 DXF 逐行流式解析，避免 OOM
- **损坏文件容错**：缺 EOF / 空值 / 嵌套 SECTION / 无 ENTITIES 段等不规范 DXF 均不丢字

## 环境依赖

| 组件 | 说明 |
|------|------|
| ODA File Converter | `/Applications/ODAFileConverter.app`，DWG→DXF 转换 |
| Python 3.13+ | 运行脚本 |
| ezdxf | `pip3 install ezdxf` |
| SHX 解析器 | 内置 `scripts/shxfont.py`（自研，仅依赖标准库，无需第三方包） |

## 快速开始

### 0. 一站式阅读（推荐）

```bash
# DWG 或 DXF 均可，DWG 自动转为同目录 DXF 后解析
python3 scripts/dwg_read.py 图纸.dwg --out 报告.md
python3 scripts/dwg_read.py 图纸.dxf --table          # 表格还原
python3 scripts/dwg_read.py 图纸.dxf --by-layer       # 按图层聚合
```

### 1. 转换 DWG → DXF

```bash
ODA="/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
mkdir -p out
"$ODA" input_dir out ACAD2018 DXF 0 0 "*.dwg"
```

### 2. 提取文字（自动匹配字体）

```bash
python3 scripts/extract_texts_stream.py 图纸.dxf out.txt
# 输出: 自动匹配 N 个大字体
```

### 3. 解析实体/图层/尺寸

```bash
python3 scripts/parse_dxf.py 图纸.dxf --entities --texts --layers
```

### 4. 显式指定字体

```bash
python3 scripts/extract_texts_stream.py 图纸.dxf out.txt --font fonts/gbcbig.shx
```

### 5. SHX 反编译为 SHP

```bash
python3 scripts/shx_decompile.py fonts/gbcbig.shx /tmp/gbcbig.shp
```

## 字体库

`fonts/` 目录内置 322 个 SHX 字体，含 `index.json` 索引（字体名 → 类型/编码/shape 数）。

| 编码 | 数量 | 说明 |
|------|------|------|
| gbk | 198 | 中文简体（gbcbig/hztxt/tssdchn 等） |
| unicode | 88 | unifont 西文字体（tssdeng 等） |
| cp949 | 28 | 韩文（KORdansun 等） |
| shift_jis | 6 | 日文（hsa 等） |
| ascii | 2 | 纯 ASCII |

## 解码原理

DXF 文本中字符的三种存储方式：

| 类型 | 存储方式 | 解码方式 |
|------|---------|---------|
| 纯 ASCII | 直存 | 原样输出 |
| 西文字体 | `\U+XXXX` | `chr(int(XXXX, 16))` |
| 中文字体 | `\M+5XXXX` | SHX 字体映射表 |

关键结论：bigfont 索引表 shape number = 该字体的字符编码。DXF 中 `\M+5BAA3` 去掉前导 `5` 后为 `0xBAA3` = GBK 码 = 「海」。

## 目录结构

```
dwg-reader-skill/
├── SKILL.md              # 技能说明
├── scripts/
│   ├── parse_dxf.py           # 结构化解析（实体/文字/图层/尺寸）
│   ├── extract_texts_stream.py # 流式文字提取（低内存，自动字体匹配）
│   ├── extract_texts.py       # 文字提取（ezdxf）
│   ├── extract_texts_lowmem.py # 文字提取（正则低内存版）
│   ├── shxfont.py             # SHX 大字体解析器（多编码）
│   └── shx_decompile.py       # SHX → SHP 反编译
└── fonts/               # 322 个 SHX 字体 + index.json
```

## License

MIT
