# AGENT.md — 面向 AI Agent 的使用说明

本文件供 **AI Agent**（而非人类终端用户）调用本 skill 时参考。它定义了触发条件、
唯一入口命令、输入输出契约、决策树与已知陷阱。面向人类的完整说明见 `SKILL.md` /
`README.md`，本文件是其"操作手册"精简版。

---

## 1. 这是什么

一个读取 DWG / DXF 工程图纸（建筑、结构、机电、给排水等）并提取结构化信息的技能。

- **输入**：一个 `.dwg` 或 `.dxf` 文件的**绝对路径**。
- **输出**：文字标注、图层、实体清单、尺寸等**结构化文本**（Markdown / 纯文本）。
- **不渲染图像**：只做解析提取，不产出 PNG/SVG 图纸图片。
- **核心依赖**：ODA File Converter（DWG→DXF）+ ezdxf（解析）。两者均已预装在运行环境。

---

## 2. 触发条件

当用户消息满足以下任一特征时，应使用本 skill：

- 提供了 `.dwg` / `.dxf` 文件路径，并要求"读取 / 看 / 理解 / 提取 / 分析"图纸。
- 要求从 CAD 图纸中提取**文字标注、尺寸、图层、表格**（如门窗表、材料表）。
- 要求把 DWG 转为可读文本 / DXF。
- 关键词：DWG、DXF、CAD 图纸、工程图、图纸标注、图层、看图。

> 若用户只是要"画一张图"或"生成 CAD 文件"，本 skill 不适用（它是只读解析器）。

---

## 3. 唯一推荐入口

**绝大多数情况只用这一条命令：**

```bash
python3 <skill目录>/scripts/dwg_read.py <图纸绝对路径> [选项]
```

- `<skill目录>` 即本 AGENT.md 所在目录（即 `dwg-drawing-reader/`）。
- DWG 会自动经 ODA 转为同目录 DXF 后再解析；DXF 直接解析。
- 默认把结构化 Markdown 报告打印到 **stdout**；用 `--out 报告.md` 写入文件。

### 选项速查

| 选项 | 作用 | 何时用 |
|------|------|--------|
| `--out 报告.md` | 写文件而非 stdout | 报告较长、需留档时 |
| `--table` | 把对齐工整的网格文字还原为 Markdown 表格 | 提取门窗表 / 材料表 / 明细表时 |
| `--by-layer` | 按图层分组输出文字 | 想按专业（建筑/结构/水电）分读时 |
| `--no-convert` | 跳过 DWG→DXF（输入已是 DXF） | 已知源为 DXF、想加速时 |
| `--font 字体.shx` | 显式指定大字体 | 自动匹配失败时（罕见） |

**示例：**

```bash
# 读取 DWG，打印报告
python3 ~/.workbuddy/skills/dwg-drawing-reader/scripts/dwg_read.py /Users/kylin/test/图纸.dwg

# 提取门窗表为表格并保存到文件
python3 ~/.workbuddy/skills/dwg-drawing-reader/scripts/dwg_read.py /path/图.dxf --table --out 门窗表.md
```

---

## 4. 决策树（Agent 应如何选择）

```
收到图纸路径 + 读取意图
        │
        ├─ 想要"整张图全部文字 + 图层 + 实体概览"
        │       → dwg_read.py（默认，无额外选项）
        │
        ├─ 想要"表格类内容"（门窗表/材料表/明细表）
        │       → dwg_read.py --table
        │
        ├─ 想要"按专业/图层分开看文字"
        │       → dwg_read.py --by-layer
        │
        ├─ 只想要"纯文字列表、超低内存、超大文件"
        │       → scripts/extract_texts_stream.py 图.dxf out.txt
        │
        └─ 需要"实体几何清单 / 尺寸 / 块定义细节"
                → scripts/parse_dxf.py 图.dxf --entities --texts --layers --blocks --limits
```

> 经验法则：**先 `dwg_read.py` 默认跑一次**，看输出是否够用；不够再叠加 `--table` /
> `--by-layer`，或换底层脚本。**不要一上来就手动调 ODA 或 ezdxf**。

---

## 5. 输出契约（Agent 如何消费结果）

`dwg_read.py` 的 stdout 是一份 Markdown 报告，通常包含以下小节（按文件实际情况出现）：

- **文字提取**：按几何阅读顺序（上→下、左→右、分栏）排列的全部 TEXT/MTEXT 文本。
  - 已自动解码：BigFont 中文（`\M+5XXXX`）、Unicode（`\U+XXXX`）、`%%` 转义
    （`%%C`→Ø、`%%D`→°、`%%P`→±）、MTEXT 堆叠（`\S a^b`）、`\P` 换行。
  - Agent **无需再手动清理**这些转义码；若仍残留 `\` 开头的控制码，可视为 MTEXT
    格式残留，用正则 `re.sub(r'\\[A-Za-z][^\\;]*;|\\[A-Za-z]', '', s)` 清理。
- **图层列表**：图层名、颜色、开关/冻结状态。
- **实体统计**：LINE/CIRCLE/ARC/TEXT/MTEXT/DIMENSION/INSERT 等的计数与关键属性。
- **尺寸信息**：DIMENSION 的测量值。
- **降级提示**：若 DWG→DXF 或 ezdxf 解析失败，报告顶部会出现"降级为流式提取"等
  字样，**此时文字提取仍可用，但以流式提取为准**。

Agent 应把报告内容直接用于回答用户问题（如"这张图有哪些房间""梁的标注是什么"）。

---

## 6. 已知陷阱与注意事项（务必读）

1. **路径必须绝对路径**：`<file>` 参数传绝对路径。相对路径可能因 cwd 不对而找不到文件。
2. **DWG 转换会生成同目录 DXF**：`dwg_read.py` 处理 `.dwg` 时会在源文件同目录落一个
   同名 `.dxf`。这是预期行为，不是报错。转换过程约数秒，需等待进程退出。
3. **ODA 是 Qt GUI 程序但命令行模式下会自动退出**：带完整参数调用时不弹窗；若你看到
   它在等待输入，说明参数不完整（必须是 7 个位置参数，本 skill 已封装好，无需你手动调）。
4. **字体已内置且自动匹配**：`fonts/` 目录含 322 个 SHX 字体与 `index.json` 索引。
   解码按 DXF 的 STYLE 表自动匹配，**默认无需 `--font`**。只有自动匹配明显出错
   （如整段中文变乱码）才显式指定。
5. **中文乱码排查顺序**：
   - 先看报告是否有"自动匹配 N 个大字体"——有则基本正常；
   - 若中文全丢/变问号，多半是 STYLE 表字体名未被索引覆盖，试 `--font fonts/gbcbig.shx`；
   - 若整段是 `??` 且非中文，可能是 codepage 问题（已默认 UTF-8 优先，罕见回退 GBK）。
6. **超大文件（>100MB）**：优先 `extract_texts_stream.py`（逐行流式、低内存），
   或 `dwg_read.py`（内部已用流式降级）。避免对超大文件用 `parse_dxf.py` 全量加载。
7. **不规范 DXF（缺 EOF、匿名块存主体文字）**：`dwg_read.py` 已做容错——ezdxf 失败会
   自动降级流式提取，且会补提取未被 INSERT 引用的块内文字，**一般不丢字**。
8. **坐标无单位**：输出的是原始坐标数值，比例关系需结合图纸尺寸标注自行判断；
   不要擅自假设单位为 mm 或 m。
9. **不渲染**：本 skill 不产出图片。若用户要看"图长什么样"，只能描述几何/文字，
   不能给渲染图。

---

## 7. 进阶（仅当默认入口不够用时）

底层脚本（均在 `scripts/`）：

- `parse_dxf.py` — 结构化报告（实体/文字/图层/块/尺寸），支持 `--entities --texts
  --layers --blocks --limits` 组合开关。
- `extract_texts_stream.py` — 流式提取全部文字（低内存），支持 `--table` / `--by-layer`
  / `--font`。
- `extract_texts.py` — 基于 ezdxf 的全量文字提取（虚拟实体展开块属性）。
- `shxfont.py` — SHX 大字体解析器（shape number → 字符映射），仅标准库依赖。
- `shx_decompile.py` — SHX 反编译为 SHP 文本。

> 这些脚本通常**不需要** Agent 直接调用；`dwg_read.py` 已聚合它们的能力。

---

## 8. 最小可用示例（Agent 可直接复制）

```bash
SKILL=~/.workbuddy/skills/dwg-drawing-reader
python3 "$SKILL/scripts/dwg_read.py" "/绝对/路径/图纸.dwg"
```

拿到 stdout 的 Markdown 报告后，按用户问题从中摘取/归纳答案即可。
若为表格类图纸，加上 `--table`；若需按图层分读，加 `--by-layer`。
