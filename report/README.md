# 真实运行结果报告与审计附件

**版本说明：本目录报告与成果包基于修复前的真实运行结果。** 站点身份代码现已修正，见根目录 [STATION_FIX_GUIDE.md](../STATION_FIX_GUIDE.md)。尚未收到修正后全国重跑结果，因此本目录旧报告、原始输入和统计保持不变，不将代码修复等同于全国数据已重新验证。

已根据用户 Windows 电脑的真实 OSM 运行结果生成：

- [Word 报告](deliverables/AI_Railway_Report_Audited.docx)：可编辑，填写封面的姓名、学号等空白项。
- [PDF 报告](deliverables/AI_Railway_Report_Audited.pdf)：16 页，中文字体已嵌入。
- [完整成果 ZIP](deliverables/AI_Railway_Submission.zip)：报告、图表、8 份原始结果表、审计附件与可运行项目源码。
- [在线阅读正文](deliverables/AI_Railway_Report_Audited.md)。

在 GitHub 文件页点击 **Download raw file / 下载原始文件**。直接下载地址：

```text
https://github.com/zyx0309/scutwork/raw/refs/heads/main/report/deliverables/AI_Railway_Report_Audited.docx
https://github.com/zyx0309/scutwork/raw/refs/heads/main/report/deliverables/AI_Railway_Report_Audited.pdf
https://github.com/zyx0309/scutwork/raw/refs/heads/main/report/deliverables/AI_Railway_Submission.zip
```

## 阅读前必须知道的结果边界

本版是带质量审计的实验记录。用户记录的全国底层图为 294,713 节点、296,408 边、1,671 个分量；城市图为 34 节点、351 边、8 个分量。27 个城市形成完全图 K27，其余 7 个城市孤立：南京、福州、海口、西安、乌鲁木齐、台北、澳门。边的宽定义允许轨道绕过其他代表站的单个锚点，不能理解为直达列车。

自动接入为 30 个站。审计确认“福州”误配到了台湾“浮洲”（OSM relation 10658521，距福州布局点约 246.890 km），已在派生审计表中拒绝。剩余 29 个是候选接入，24 个空间匹配仍待人工复核，包含兰州站 38.412 m 的偏移。没有虚构正确福州站坐标，也没有把原始文件静默改写。

广州站→兰州站在当前图上的候选最短几何里程为 **2383.541507726979 km**，显示为 **2383.542 km**。55 段求和、累计值和相邻段节点衔接通过表级核验；对城市图独立运行 Dijkstra 得到相同距离。福州在原始城市图中度为 0，拒绝其错误属性不改变现有城市边表；这不等于修复代码后重新运行了全国图。

全国原始 PBF、完整轨道路径 GeoJSON 和本地生成的实际路线图未成功传入此次报告工作区。因此：

- 原始 PBF 解析、城市边轨道几何重算等结论明确引用用户程序自检记录。
- 本次独立核验仅覆盖 8 份上传结果的城市图、分段表、指纹及匹配语义，不声称再次逐形状点复算。
- 报告的 7 幅图是依据上传 CSV 重绘的网络和诊断图。抽象城市连线、偏移虚线、累计曲线均有明确标识，没有伪装为实际铁路走向图。
- 没有运行 A* 对比、生成 34×34 距离矩阵或编造中间停站、运行时间和官方里程。

## ZIP 内容及位置

解压后进入 `OSM_Railway_Project`：

| 位置 | 内容 |
|---|---|
| `report/deliverables/` | Word、PDF、Markdown 报告 |
| `report/input/` | 用户上传的 8 份原始结果表，保持原始字节 |
| `report/figures/` | 7 幅 PNG 和 7 幅 SVG |
| `report/audited_city_stations.csv` | 保留原始列，另列身份审计和候选锚点；福州错配被拒绝 |
| `report/independent_audit.json` | 表级独立核验结果及检查范围 |
| `report/mst_display_edges.csv` | 展示用最小生成森林 26 条边的完整精度距离 |
| `report/SOURCE_MANIFEST.json` | 8 份输入的独立 SHA-256、原始 PBF 的程序记录指纹、原分析代码版本 |
| `src/`、`tests/`、`tools/` | 完整项目源码、原有测试及 Windows 启动器 |
| `install.bat`、`run.bat`、`WINDOWS_GUIDE.md` | 安装、全国 PBF 处理及 Windows 初学者指南 |

ZIP 不包含 PBF、全国图缓存、虚拟环境、运行日志或完整字体文件。`outputs/` 中的云端检查记录保留最初检查时间和范围，不能当作本次全国结果；此次全国结果统一保存在 `report/input/`。

## 不扫描 PBF，复核本次报告

阅读报告无需安装 Python。若需重新核验：

1. 解压完整成果 ZIP，进入 `OSM_Railway_Project`。项目路径可以包含中文和空格。
2. 按根目录 `WINDOWS_GUIDE.md` 安装 **Python 3.12 64 位**，双击 `install.bat` 安装到项目 `.venv`。
3. 在该目录地址栏输入 `cmd` 后按回车，执行：

```bat
.venv\Scripts\python.exe report\verify_results.py report\input
```

该步骤只核验小型表格，不访问网络、不读取 PBF，不更改原始结果。

如需重建 Word、PDF 和图表，在同一 CMD 窗口执行：

```bat
.venv\Scripts\python.exe -m pip install -r report\requirements.txt
.venv\Scripts\python.exe report\build_report.py
.venv\Scripts\python.exe report\package_submission.py
```

报告依赖安装需要网络。首次重建报告还会从 `raw.githubusercontent.com/notofonts/noto-cjk` 下载 Noto Sans SC 字体并核对固定 SHA-256；已有字体时不重复下载。这是报告排版的独立步骤，不改变主程序已有有效 PBF 时默认离线处理的行为。字体下载失败不会影响已经交付的 Word/PDF；无需重建也可直接使用。

仅下载 GitHub 仓库 ZIP 时，8 份原始输入在 `AI_Railway_Submission.zip` 内；如要重建报告，先解压这个成果包，或把自己的同名结果放入 `report/input/`。本版报告脚本针对本次已完成的运行记录，不是任意数据版本的通用报告模板。

## 来源与许可

原分析源码版本为 `d3a115234a288b57fd46955fb758a882a261f723`。8 份输入由用户提供；PBF 文件哈希及完整解析状态取自用户运行记录，未在云端重新计算。所有距离统一称为“**基于 OSM 铁路线形计算的几何里程**”。

© OpenStreetMap contributors；OSM 派生数据及图件遵循 ODbL 1.0，参见根目录 `DATA_LICENSE.md`。Noto Sans SC 使用 SIL Open Font License 1.1，见 `fonts/OFL.txt`；PDF 嵌入的是字体子集。源码适用根目录 `LICENSE`。Word 与 PDF 使用相同内容，实际分页可因软件而异。
