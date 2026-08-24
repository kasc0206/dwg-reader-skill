---
name: dwg-drawing-reader
description: "当用户提供 DWG/DXF 工程图纸文件（建筑、机械、电气、结构、给排水等），需要阅读、解析、分析图纸内容时触发此技能。DWG 是 Autodesk 专有二进制格式，本技能通过 ODA File Converter 将 DWG 转换为 DXF 文本格式，再用 ezdxf 解析图层、实体（LINE/CIRCLE/ARC/TEXT/MTEXT/DIMENSION 等）、文字标注和尺寸信息，供用户阅读理解图纸内容。典型触发场景：读取 DWG 图纸、提取图纸文字标注、分析图纸尺寸、查看图纸图层结构、DWG 转 DXF、图纸内容问答。关键词：DWG、DXF、图纸、CAD 图纸、autocad、工程图、看图、图纸标注、图层。"
---

# DWG 图纸阅读

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
| shxparser | pip 包（SHX 线字体解析辅助） | 已安装 |
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
- `parse_dxf.py` — 解析 DXF 并输出结构化报告（实体清单、文字、图层、块、尺寸）
- `extract_texts_stream.py` — 流式提取全部文字（低内存），支持 BigFont 解码
- `shxfont.py` — SHX 大字体解析器（建立 shape number → 字符映射）
- `shx_decompile.py` — SHX 反编译为 SHP 文本（等价 DUMPSHX / shx2shp）

### 用法

```bash
python3 <skill目录>/scripts/parse_dxf.py <文件.dxf> [--entities] [--texts] [--layers] [--blocks] [--limits]
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
- bigfont 234 个：中文 GBK（gbcbig/hztxt/tssdchn 等）、韩文 cp949、日文 shift_jis、繁中 big5
- unifont 88 个：Unicode 编码（tssdeng 等）
- 支持常见别名：gbcbig/hztxt/tssdchn/tssdeng 等，大小写不敏感，自动补 `.shx`

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
2. **中文字体**：DXF 文字中若含中文，解析时按 UTF-8 处理，可直接输出中文文本。
3. **块引用**：INSERT 实体默认只显示块名和位置；如需展开块内容，可在脚本中启用 `--explode-blocks`。
4. **大文件**：超大图纸（>100MB）解析耗时，建议先转 DXF 再用脚本提取。
5. **批量转换**：ODA 支持整个目录批量转换，把多个 DWG 放进一个目录即可一次转换。
6. **坐标单位**：DWG 无强制单位约定，解析时输出原始坐标值，比例关系需结合图纸尺寸标注判断。
7. **不渲染图片**：按用户偏好，本 skill 只做解析提取（实体/文字/图层/尺寸），不输出 SVG/PNG 渲染图。
