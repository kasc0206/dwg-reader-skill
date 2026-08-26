---
name: dwg-drawing-reader
description: "当用户提供 DWG/DXF 工程图纸文件（建筑、机械、电气、结构、给排水等），需要阅读、解析、分析图纸内容时触发此技能。DWG 是 Autodesk 专有二进制格式，本技能通过 ODA File Converter 将 DWG 转换为 DXF 文本格式，再用 ezdxf 解析图层、实体（LINE/CIRCLE/ARC/TEXT/MTEXT/DIMENSION 等）、文字标注和尺寸信息，供用户阅读理解图纸内容。典型触发场景：读取 DWG 图纸、提取图纸文字标注、分析图纸尺寸、查看图纸图层结构、DWG 转 DXF、图纸内容问答。关键词：DWG、DXF、图纸、CAD 图纸、autocad、工程图、看图、图纸标注、图层。"
tags:
  - dwg
  - dxf
  - cad
  - 图纸
  - engineering
tools:
  - Read
  - Shell
compatibility:
  os:
    - macOS
    - Linux
    - Windows
  platforms:
    - macos-arm64
    - macos-x86_64
    - linux-x86_64
    - windows-x86_64
  runtime: "Python 3.10+，需预先安装 ezdxf（pip3 install ezdxf）与 ODA File Converter（DWG→DXF）。SHX 大字体解析器为内置脚本，仅依赖 Python 标准库。"
  network: "无需联网。ODA / ezdxf 均为本地运行。"
---

# DWG 图纸阅读

## When to Use

使用本 skill 当且仅当用户意图满足以下之一：

- 提供 `.dwg` / `.dxf` 文件路径，并要求"读取 / 看 / 理解 / 提取 / 分析"图纸内容。
- 要求从 CAD 图纸提取文字标注、尺寸、图层、表格（门窗表 / 材料表）。
- 要求把 DWG 转为可读文本 / DXF。
- 要求批量处理多个 DWG/DXF、按图层筛选、识别构件（门/窗/梁/柱等）、精读尺寸标注。

关键词：DWG、DXF、CAD 图纸、工程图、图纸标注、图层、看图、算量。

## Do Not Use

- **不要**用于"画一张图 / 生成 CAD / 修改图纸几何"——本 skill 是只读解析器，不写回 DXF/DWG。
- **不要**用于渲染图片（PNG/SVG）——本 skill 只输出结构化文本，不生成图纸图像。
- **不要**用于非 CAD 的 PDF/图片图纸——那是 OCR/光栅识别任务，不在本 skill 范围。

## Prerequisites

| 组件 | 版本 / 路径 | 状态 | 安装 |
|------|-------------|------|------|
| Python | 3.10+ | 已安装 | 系统自带 |
| ezdxf | v1.4+ | 可能需安装 | `pip3 install ezdxf` |
| ODA File Converter | `/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter`（macOS） | 需安装 | https://www.opendesign.com/guestfiles/oda_file_converter ；安装后 `xattr -dr com.apple.quarantine "/Applications/ODAFileConverter.app"` |
| 中文字体库 | `fonts/`（322 个 SHX + `index.json`） | 已内置 | 无需操作 |
| 大字体解析器 | `scripts/shxfont.py` | 已内置 | 仅依赖标准库 |

> 唯一硬依赖是 ezdxf 与 ODA（处理 DWG 时）。其余均为内置脚本与字体。

## Supported Formats

| 格式 | 输入支持 | 备注 |
|------|----------|------|
| `.dxf` | ✅ 直接解析 | 文本格式，ezdxf 原生支持 |
| `.dwg` | ✅ 经 ODA 转 DXF | 自动调用 ODA 转为同目录 DXF 后解析 |
| `.shx` | ✅ 字体解析 | 作为字体库被引用，不直接作为图纸输入 |
| `.dgn` / `.step` / 3D 实体 | ❌ | 本 skill 面向 2D 工程图，不做 3D CAD 转换（见下方 Platform Support 注） |

## Platform Support

| 能力 | macOS arm64 | macOS x86_64 | Linux x86_64 | Windows x86_64 |
|------|-------------|--------------|--------------|----------------|
| 解析 DXF | ✅ | ✅ | ✅ | ✅ |
| DWG→DXF（ODA） | ✅ | ✅ | ✅（需安装 ODA Linux 版） | ✅（需安装 ODA Win 版） |
| 字体解码（SHX） | ✅ | ✅ | ✅ | ✅ |

> 注：本 skill 与 NVIDIA `usd-convert-cad`（用于 3D CAD→USD 仿真）定位不同——本 skill 专注 2D 工程图（DWG/DXF）的文本/几何解析，不处理 3D 实体建模或仿真就绪资产。二者互补而非替代。

## Implementation Contract

- **唯一入口**：`scripts/dwg_read.py <文件> [选项]`，返回码 `0` 表示成功，非 0 表示失败。
- **输出契约**：默认打印 Markdown 报告到 stdout；`--out` 写入文件并打印进度到 stderr。
- **降级行为**：若 ezdxf 严格解析失败（缺 EOF / 损坏），`dwg_read.py` 自动降级为流式提取，报告顶部出现 `⚠️` 提示，文字提取仍可用。
- **DWG 副作用**：处理 `.dwg` 会在源文件同目录落一个同名 `.dxf`（预期行为，非报错）。
- **底层脚本**：`parse_dxf.py` / `extract_texts_stream.py` / `extract_dimensions.py` / `identify_components.py` 均为返回码驱动的 CLI，可被外部调用。

## Troubleshooting

| 现象 | 原因 | 处理 |
|------|------|------|
| `未找到 ODA File Converter` | ODA 未安装或路径不符 | 安装 ODA（见 Prerequisites），或传 `.dxf` 并加 `--no-convert` |
| `DXF 解析失败（missing EOF tag）` | 文件缺 EOF | 自动降级流式提取；结果见 `⚠️` 提示下文字章节 |
| 中文全变 `?` / 乱码 | 字体未匹配 | 加 `--font fonts/gbcbig.shx` 强制指定；或检查 `fonts/index.json` |
| 报告全空（实体数 0） | 内容在匿名块定义内 | 已自动补提取未引用块文字；若仍空，文件可能无文字实体 |
| DWG 转换卡住 / 弹窗 | ODA 参数不完整 | 不应手动调 ODA；统一用 `dwg_read.py` 入口 |
| `未安装 ezdxf` | 环境缺包 | `pip3 install ezdxf` |

## 概述

| 项目 | 内容 |
|------|------|
| **能力名称** | DWG 图纸阅读与解析 |
| **核心功能** | 读取 DWG/DXF 图纸，提取图层、实体、文字标注、尺寸信息，输出结构化解析报告供阅读理解 |
| **输入** | DWG 或 DXF 文件路径 |
| **输出** | 结构化解析报告（实体清单、文字提取、图层列表、尺寸信息） |
| **依赖** | ODA File Converter（DWG→DXF）+ ezdxf（解析） |

## 工作原理

```
DWG (二进制) → [ODA File Converter] → DXF (纯文本) → [ezdxf] → 解析提取
```

- DWG 是 Autodesk 专有二进制格式，无法直接读取，必须先转换为 DXF。
- DXF 是纯文本格式，ezdxf 库可完整解析。
- 转换是无损的，实体、图层、文字、尺寸、块引用全部保留。
- **不渲染图片**：只做解析提取，通过文字、实体、图层信息阅读理解图纸内容。

## 环境依赖

| 组件 | 路径/版本 | 状态 |
|------|-----------|------|
| ODA File Converter | `/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter` | 已安装 |
| Python | python3 (3.13+) | 已安装 |
| ezdxf | pip 包，v1.4+ | 已安装 |
| SHX 大字体解析器 | 内置 `scripts/shxfont.py`（自研，仅依赖 Python 标准库，无需第三方包） | 已内置 |
| 中文字体库 | `fonts/`（322 个 SHX，含 index.json 编码索引） | 已内置 |

> 如果 ezdxf 未安装，执行：`pip3 install ezdxf`
> 如果 ODA 未安装，从 https://www.opendesign.com/guestfiles/oda_file_converter 下载 macOS arm64 dmg，拖入 /Applications，并执行 `xattr -dr com.apple.quarantine "/Applications/ODAFileConverter.app"`。

## 转换命令（DWG→DXF）

### 方式一：命令行调用 ODA（推荐用于脚本）

```bash
ODA="/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
mkdir -p <输出目录>
"$ODA" <输入目录> <输出目录> ACAD2018 DXF 0 0 "*.dwg"
```

参数说明（位置参数，无命名参数）：
| 位置 | 参数 | 说明 |
|------|------|------|
| 1 | 输入目录 | 含 DWG/DXF 的源目录 |
| 2 | 输出目录 | 转换结果存放目录（需已存在） |
| 3 | 输出版本 | 如 `ACAD2018`、`ACAD2013`、`ACAD2007`、`ACAD2000`、`ACAD12` |
| 4 | 输出类型 | `DXF` 或 `DWG` |
| 5 | 递归标志 | `0`=不递归，`1`=递归处理子目录 |
| 6 | 审计标志 | `0`=关闭，`1`=加载时审计修复 |
| 7 | 文件过滤器 | 如 `"*.dwg"`、`"*.dxf"` |

> 注意：ODA 是 Qt GUI 程序，无参数启动会打开窗口；必须带完整 7 个位置参数以命令行模式运行。转换完成后进程自动退出。

### 方式二：ezdxf 插件（ODA 装好后可用）

```python
from ezdxf.addons.dwg import dwg2dxf
dwg2dxf("input.dwg", "output.dxf")
```

## 解析脚本

项目内置脚本位于 `scripts/` 目录：
- `dwg_read.py` — **一站式流水线**（推荐）：自动 DWG→DXF 转换 + 结构化报告 + 文字提取 + 可选尺寸精读 / 构件识别 / 批量处理，输出 Markdown 报告
- `parse_dxf.py` — 解析 DXF 并输出结构化报告（实体清单、文字、图层、块、尺寸），支持 `--layer-filter`
- `extract_texts_stream.py` — 流式提取全部文字（低内存），支持 BigFont 解码、块展开、表格/图层聚合、`--layer-filter` / `--layer-alias`
- `extract_texts.py` — 基于 ezdxf 的全量文字提取（含块属性 virtual_entities 展开）
- `extract_dimensions.py` — **尺寸标注精读**：按类型（线性/对齐/角度/半径/直径/坐标/弧长）分类，关联最近几何，输出表格 + 可选 JSON
- `identify_components.py` — **构件识别**：按块名/图层规则匹配门/窗/梁/柱/钢筋/楼梯/设备/道路/渠道等，输出构件清单（规则见 `component_rules.json`）
- `shxfont.py` — SHX 大字体解析器（建立 shape number → 字符映射）
- `shx_decompile.py` — SHX 反编译为 SHP 文本（等价 DUMPSHX / shx2shp）

> **解码一致性**：BigFont（`\M+`）/ Unicode（`\U+`）/ `%%` 转义 / MTEXT 堆叠（`\S`）解码已接入全部提取脚本
> （`dwg_read.py`、`parse_dxf.py`、`extract_texts.py`、`extract_texts_stream.py`），
> 均会自动按文本样式匹配 `fonts/` 字体库；无需手动指定字体或预处理。

### 一站式流水线（推荐）

```bash
# 单文件（DWG 或 DXF 均可，DWG 自动转 DXF）
python3 scripts/dwg_read.py <图纸.dwg|图纸.dxf> [--out 报告.md]
                      [--table] [--by-layer] [--no-convert] [--font 字体.shx]
                      [--dimensions] [--components]
                      [--layer-filter "WALL|BEAM"] [--layer-alias 别名.json]

# 批量目录：遍历目录下所有 .dwg/.dxf，每张图一份报告 + 总览 index.md
python3 scripts/dwg_read.py --batch <目录> --out-dir <输出目录>
                      [--table] [--by-layer] [--dimensions] [--components]

# 选项
#   --out 报告.md        写入 Markdown 报告文件（默认打印到 stdout）
#   --table              以 Markdown 表格还原对齐网格（如门窗表）
#   --by-layer           按图层聚合输出文字
#   --no-convert         跳过 DWG→DXF 转换（输入已是 DXF 时加速）
#   --font               显式指定大字体文件（默认按 STYLE 表自动匹配 fonts/）
#   --dimensions         追加「尺寸标注精读」章节（按类型分类 + 关联几何）
#   --components         追加「构件识别」章节（门/窗/梁/柱等清单）
#   --layer-filter       按图层名关键词/正则过滤（仅保留匹配图层；逗号分隔多词）
#   --layer-alias        图层别名表 JSON（{用户词: 实际图层片段}），中文词映射到实际图层
#   --batch              批量模式：扫描目录下所有 .dwg/.dxf
#   --out-dir            批量模式的输出目录（每张图一个 .md + 总览 index.md）
```

### 用法（单脚本）

```bash
# 结构化报告
python3 <skill目录>/scripts/parse_dxf.py <文件.dxf> [--entities] [--texts] [--layers] [--blocks] [--limits] [--layer-filter WALL]

# 尺寸标注精读
python3 <skill目录>/scripts/extract_dimensions.py <文件.dxf> [--json] [--out 尺寸.md]

# 构件识别
python3 <skill目录>/scripts/identify_components.py <文件.dxf> [--rules 自定义.json] [--json] [--out 构件.md]
```

### 快速阅读理解（推荐）

对于整张图纸的快速理解，用一段内联 Python 按位置排序提取全部文字（TEXT + MTEXT），还原图纸的阅读顺序（左上到右下）：

```python
import ezdxf
doc = ezdxf.readfile('图纸.dxf')
msp = doc.modelspace()
texts = []
for e in msp.query('TEXT MTEXT'):
    pos = e.dxf.insert
    content = e.text if e.dxftype() == 'MTEXT' else e.dxf.text
    texts.append((pos.y, pos.x, content))
texts.sort(key=lambda t: (-t[0], t[1]))  # y 从大到小（上到下），x 从小到大（左到右）
for y, x, t in texts:
    print(t)
```

> 注：MTEXT 内容含内嵌格式代码（`\P` 换行、`\f` 字体、`\H` 高度、`\W` 宽度等），输出时可先用正则 `re.sub(r'\\[A-Za-z][^\\;]*;|\\[A-Za-z]', '', content)` 清理，再阅读理解。

### 大字体编码解码（BigFont）

天正/探索者（TSSD）图纸的中文文字常以 CAD 大字体编码存储，需解码：

- `\M+5XXXX` → 去掉前导 `5`，后 4 位 `XXXX` 是 SHX 大字体 shape number（即该字体的字符编码，中文字体为 GBK 两字节码）：`bytes([hi, lo]).decode('gbk')`
- `\U+XXXX` → Unicode 码点：`chr(int(XXXX, 16))`

示例：`\M+5BAA3` = 海、`\M+5C4CF` = 南、`\M+5BDE1` = 结、`\M+5B9B9` = 构 → "海南结构"

> 注意：`\M+5XXXX` 与相邻数字文本（如 `\M+5A1DD800` = "≥800"）之间不要贪婪匹配，用 `\\M\+5([0-9A-Fa-f]{4})` 精确匹配 5 位。

### 英文与西文支持

英文/数字/符号完整支持，分三种情况：

| 文本类型 | 存储方式 | 解码方式 |
|---------|---------|---------|
| 纯英文/数字（ASCII） | 直存 | 原样输出，无需解码 |
| 西文字体字符（unifont） | `\U+XXXX` | `chr(int(XXXX, 16))` |
| 中文字符（bigfont） | `\M+5XXXX` | SHX 字体映射表（gbk 等） |

- **ASCII 直存**：`HELLO WORLD 123`、`GB50017-2017`、`kN/m`、`MPa` 等原样提取
- **Unicode 码点**：`\U+0041`→A、`\U+00D7`→×（乘号）、`\U+006D2`→m²、`\U+00A0`→不换行空格
- **西文 unifont 字体**：tssdeng.shx 等（unifont 类型，shape number 即 Unicode 码点）直接 `chr()` 解码
- **中英混排**：一条文本中英文、Unicode 符号、中文同时正确解码（如 `C30混凝土 \U+00D7 250` → `C30混凝土 × 250`）
- **中英文共用字体**：bigfont 中 ASCII 区（0x20-0x7F）字符直接按 `chr()` 映射

### 符号支持

图纸中的专业符号完整支持，分三类：

**1. AutoCAD `%%` 转义序列**（自动解码，大小写不敏感）

| 转义 | 符号 | 含义 |
|------|------|------|
| `%%C`/`%%c` | `Ø` | 直径（如 `%%C20` → `Ø20`） |
| `%%D`/`%%d` | `°` | 度（如 `45%%d` → `45°`） |
| `%%P`/`%%p` | `±` | 正负（如 `%%P0.5` → `±0.5`） |
| `%%%` | `%` | 百分号 |
| `%%u`/`%%o` | （移除标记） | 下划线/上划线开-关 |
| `%%数字` | 单字节字符 | 如 `%%130` → `\x82` |

**2. `\U+XXXX` Unicode 符号**：`\U+00B1`→±、`\U+00B0`→°、`\U+00D7`→×、`\U+00B2`→²、`\U+00B3`→³、`\U+00B5`→µ

**3. `\M+5XXXX` bigfont 符号区**（GBK A1 区）：`\M+5A1DD`→≥、`\M+5A1E3`→°、`\M+5A1A2`→、等

实测：结构图纸中 `栓钉 Ø19 间距@200`、`吊索夹角45°`、`±0.000`、`±3mm` 等全部正确解码。

### SHX 大字体解析（全字体支持）

内置 SHX 大字体解析器（`scripts/shxfont.py`），从 SHX 字体文件直接建立
shape number → 字符映射，支持多语言编码自动识别：

```python
from shxfont import ShxBigFont
font = ShxBigFont("fonts/gbcbig.shx")   # 7019 shapes
font.get_char(0xBAA3)   # → '海'
```

**关键结论**：bigfont 索引表 shape number = 该字体的字符编码。gbcbig.shx /
hztxt.shx / tssdchn.shx（中文 GBK）、KORdansun.shx（韩文 cp949）、hsa.shx
（日文 shift_jis）等均验证成立。DXF 中 `\M+5XXXX` 的 `XXXX` 就是 shape
number，解码时会按字体编码自动匹配（gbk/cp949/shift_jis/big5），解码失败
时多编码回退。

### 自动字体匹配（默认模式）

`extract_texts_stream.py` 无 `--font` 参数时会**自动解析 DXF 的 STYLE 表**，
按每个文本实体的样式名匹配 `fonts/` 字体库中的大字体文件，逐样式正确解码：

```bash
python3 scripts/extract_texts_stream.py 图纸.dxf out.txt
# 输出: 自动匹配 N 个大字体
```

### 反编译 SHX → SHP

`scripts/shx_decompile.py` 将大字体 SHX 反编译为 SHP 文本（等价于
AutoCAD DUMPSHX / shx2shp 工具）：

```bash
python3 scripts/shx_decompile.py fonts/gbcbig.shx /tmp/gbcbig.shp
# 输出格式: *BIGFONT 7019,1,0A1,0FE / *BAA3,124,海 / 数据行...
```

### 低内存提取

大 DXF（>15MB）用 ezdxf 全量加载可能 OOM，改用 `scripts/extract_texts_stream.py`
逐行解析 DXF tag 对，仅收集 TEXT/MTEXT 的 code 1/3 内容，支持 BigFont 解码
（自动匹配或 `--font` 显式指定）：

```bash
# 自动模式（推荐）：按 STYLE 表匹配字体
python3 scripts/extract_texts_stream.py 图纸.dxf out.txt
# 显式指定字体
python3 scripts/extract_texts_stream.py 图纸.dxf out.txt --font fonts/gbcbig.shx
```

### 字体库（全量）

`fonts/` 目录内置 322 个 SHX 字体（约 159MB，来自 AutoCAD SHX 字体集合），
含 `index.json` 索引（字体名 → 类型/编码/shape 数）：
- bigfont 234 个：中文 GBK（gbcbig/hztxt/tssdchn 等）、韩文 cp949、日文 shift_jis
- unifont 88 个：Unicode 编码（tssdeng 等）
- 支持常见别名：gbcbig/hztxt/tssdchn/tssdeng 等，大小写不敏感，自动补 `.shx`
- STYLE 表字体名带路径前缀（如 `fonts/tssdchn.shx`、`C:\...\x.shx`）会自动取 basename 匹配

### 表格结构化还原（`--table`）

对对齐工整的网格文字（如门窗表、材料表），`extract_texts_stream.py` / `dwg_read.py`
可用几何聚类（`--table`）还原为 Markdown 表格：

```bash
python3 scripts/extract_texts_stream.py 图纸.dxf --table
# 或
python3 scripts/dwg_read.py 图纸.dxf --table
```

算法：按 Y 相近聚类出行、X 相近聚类出列，顶部行在上；不足 2×2 时自动回退平铺输出。

### 阅读顺序还原（默认）

文字默认按**几何感知排序**（`reorder_by_columns`）：先按栏（X 聚类）分组，栏内按
Y 降序（上→下）、X 升序（左→右）。比纯 `(-Y, X)` 更适合多栏图纸，避免左栏与
右栏同 Y 行交错。

### 按图层聚合（`--by-layer`）

`--by-layer` 按 DXF LAYER 分组输出文字，便于按专业（建筑/结构/水电）分读：

```bash
python3 scripts/extract_texts_stream.py 图纸.dxf --by-layer
```

### 块内文字与属性（INSERT / ATTRIB）

- INSERT 块参照自动展开：块定义内 TEXT/MTEXT 按块基点 + 缩放/旋转/镜像变换到世界坐标
- ATTRIB 块属性随块展开提取
- 未被 INSERT 引用的块（图纸主体常置于 `*Model_Space` 等匿名块）其内部文字也直接提取，
  保证无独立 ENTITIES 段或不规范文件不丢字

### MTEXT 堆叠文字（`\S`）

MTEXT 的堆叠分数/公差（`\S top^bottom`、`\S top/bottom`、`\S top#bottom`）解码为
可读形式（`top/bottom`、`top#bottom`），`{...}` 内的高度控制码（`\H`）自动剥离。

### 损坏 / 不规范 DXF 容错

- 缺 EOF 标签、`0` 后空值（空字符串合法值）等导致 ezdxf 严格解析失败时，
  `dwg_read.py` 自动降级为流式提取（结果仍可用）
- BLOCKS 段内游离实体、嵌套 SECTION 均按实体提取，不丢字
- 文本编码：优先 UTF-8（现代 CAD 通用），失败回退 `$DWGCODEPAGE` 指示的编解码器

### 尺寸标注精读（`--dimensions`）

针对 DIMENSION 实体，按 AutoCAD 类型分类并关联被标注几何：

- **类型分类**：线性（0）、对齐（1）、角度（2/6）、直径（3）、半径（4）、坐标（5）、弧长（8），来自 `dimtype` 低 4 位。
- **标注值**：优先覆盖文字（code 1），否则用 `get_measurement()` 测量值；已自动解码 `%%` / `\U+` / BigFont。
- **几何关联**：对每条尺寸取插入点，匹配最近的 k 个 LINE/ARC/CIRCLE/LWPOLYLINE，给出类型/图层/距离/描述，便于核对"尺寸标在谁身上"。
- **输出**：Markdown 明细表（类型/标注值/图层/位置/关联几何）+ 可选 `--json` 机器可读格式。
- **降级**：ezdxf 严格解析失败时，流式提取 DIMENSION 的 code 1/10/70 关键字段（类型/位置），关联几何不可用，报告顶部标 `⚠️`。

```bash
python3 scripts/extract_dimensions.py 图.dxf --json
# 或经一站式入口
python3 scripts/dwg_read.py 图.dxf --dimensions
```

### 构件识别（`--components`）

按**块名正则 + 图层名正则**匹配常见构件，输出按类型聚合的清单：

- **覆盖类型**：门、窗、梁、柱、钢筋、楼梯、电梯、墙、板、基础、管道、设备、家具、轴线/轴号、标高、索引/详图、标注、图签/图框、指北针、道路、渠道、排水沟、建筑物、等高线、桩号、断面（共 26 类，规则见 `scripts/component_rules.json`）。
- **匹配来源**：模型空间 INSERT 块参照 + 非匿名 BLOCK 定义内实体（兼容主体内容放在块定义里的不规范图纸）。
- **聚合输出**：每类构件的数量、涉及图层、示例块名、位置范围（X/Y 包围盒）；可选 `--json`。
- **可扩展**：`--rules 自定义.json` 覆盖默认规则；新增构件类型只需加一条 `{name, block_re, layer_re}`。
- **降级**：ezdxf 失败时用流式提取 INSERT 块名 + 图层名匹配。

```bash
python3 scripts/identify_components.py 图.dxf --rules scripts/component_rules.json
# 或经一站式入口
python3 scripts/dwg_read.py 图.dxf --components
```

### 图层规则智能过滤（`--layer-filter` / `--layer-alias`）

仅保留匹配图层的实体与文字，便于聚焦单一专业：

- `--layer-filter "WALL|BEAM|DIMS"`：逗号分隔，支持正则片段，不区分大小写。
- `--layer-alias 别名.json`：`{"墙":"WALL","梁":"BEAM"}`，把中文词映射为实际图层片段后并入过滤。
- 作用于全链路：`parse_dxf.py`（实体/文字）与 `extract_texts_stream.py`（文字，含块内文字继承块图层）同时过滤。
- 块内文字继承其所属 BLOCK 定义的图层（实测部分图纸 BLOCK 不带图层，则降级为不过滤该块）。

### 批量处理目录（`--batch`）

一次处理一个目录下的所有 `.dwg` / `.dxf`：

```bash
python3 scripts/dwg_read.py --batch /path/to/drawings --out-dir /path/to/reports \
        [--table] [--by-layer] [--dimensions] [--components]
```

- 每张图生成 `<图名>.md` 报告到 `--out-dir`；
- 额外生成 `index.md` 总览（图数/成功失败数/每张图的实体数、文字条数、报告链接）；
- 处理进度打印到 stderr，总览打印到 stdout。

## 解析输出内容

### 1. 实体清单（Entities）
模型空间中所有实体，按类型统计并列出关键属性：
- `LINE`: 起点/终点坐标
- `CIRCLE`: 圆心/半径
- `ARC`: 圆心/半径/起始角度/终止角度
- `TEXT`/`MTEXT`: 文字内容/插入点/高度/旋转
- `DIMENSION`: 尺寸标注（测量值/文字/位置）
- `LWPOLYLINE`: 顶点序列/闭合状态
- `INSERT`(块引用): 块名/插入点/缩放/旋转

### 2. 文字提取（Texts）
提取图纸中所有文字标注（TEXT + MTEXT），用于理解图纸含义。MTEXT 需要解析内嵌格式代码（`\A`、`\P`、`\f` 等）。

### 3. 图层信息（Layers）
图层名、颜色、线型、开关/冻结状态、可见性。

### 4. 尺寸信息
DIMENSION 实体的测量值，对应图纸的尺寸标注。

## 注意事项

1. **版本兼容性**：ODA 输出 ACAD2018 DXF 时，ezdxf 可读所有版本（含 R12）。若源文件是 2018+ 版本，仍可无损转换。
2. **中文字体**：DXF 文字优先按 UTF-8 解码，失败回退到 `$DWGCODEPAGE` 编码；含中文可正确输出。
3. **块引用**：INSERT 默认自动展开块内文字与属性；`parse_dxf.py` 另有 `--explode-blocks` 展开实体清单。
4. **大文件**：超大图纸（>100MB）建议用 `extract_texts_stream.py` / `dwg_read.py`（逐行流式，低内存）。
5. **批量转换**：ODA 支持整个目录批量转换，把多个 DWG 放进一个目录即可一次转换。
6. **坐标单位**：DWG 无强制单位约定，解析时输出原始坐标值，比例关系需结合图纸尺寸标注判断。
7. **不渲染图片**：按用户偏好，本 skill 只做解析提取（实体/文字/图层/尺寸），不输出 SVG/PNG 渲染图。
8. **一站式入口**：日常使用直接 `python3 scripts/dwg_read.py 图纸.dwg`，自动转换+报告，无需分步操作。
