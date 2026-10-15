# 第3版：模式修正后的真实结果

- [Word 报告](deliverables/AI_Railway_Report_Audited.docx)：可编辑，封面个人信息待填写。
- [PDF 报告](deliverables/AI_Railway_Report_Audited.pdf)：17页，中文字体已嵌入。
- [报告、源码与复核材料 ZIP](deliverables/AI_Railway_Submission.zip)
- [在线正文](deliverables/AI_Railway_Report_Audited.md)

在GitHub文件页点击 **Download raw file / 下载原始文件**。直接下载：

```text
https://github.com/zyx0309/scutwork/raw/refs/heads/main/report/v3/deliverables/AI_Railway_Report_Audited.docx
https://github.com/zyx0309/scutwork/raw/refs/heads/main/report/v3/deliverables/AI_Railway_Report_Audited.pdf
https://github.com/zyx0309/scutwork/raw/refs/heads/main/report/v3/deliverables/AI_Railway_Submission.zip
```

## 本轮结果

输入只来自本次同一份 `Station_Diagnostics.zip` 的13个文件，含两张原始PNG。用户Windows真实运行完成于 **北京时间2026-10-15 11:35:58**，`graph_version=6`、`station_identity_version=3`；复用指纹相同的有效提取缓存并重建全国图。前两版结果保持历史快照，不混用。

| 项目 | 本轮结果 |
|---|---|
| 城市图 | 34节点、378条边、7个分量，主体为K28 |
| 自动接入代表站 | 30，其中拓扑/关系5、空间匹配待复核25 |
| 孤立城市 | 南京、海口、西安、乌鲁木齐、台北、澳门 |
| 无可靠轨道锚点 | 海口、西安、乌鲁木齐；另澳门无本口径重铁代表站 |
| 广州站→兰州站 | 可达；2383.541507726979 km；55段 |
| 清晰展示图 | 最小生成森林27条边；完整计算图仍保留378条边 |

全部距离为“**基于OSM铁路线形计算的几何里程**”，不是官方客运、计价里程或已验证可乘坐行程。城市边表示不通过第三代表锚点的最短铁路通路，不是直达列车。

福州现选国铁站node 6999105218（`train=yes`），锚点2451343981，偏移34.333 m。锚点出现在真实way 699510241“福平线”和775888938“合福高速线”中，已进入主体分量。前两轮已确认的浮洲/地铁误选未在本轮所选映射中重现，拒绝表保留相关对象及理由。福州仍为空间匹配待核，不称其股道已全部验收。

独立核验城市图与Dijkstra距离、55段求和/累计/节点衔接、30个站点偏移、当前选中对象的模式标签，以及焦点锚点相关way的完整坐标与长度。底层图为294,604节点、296,299边、1,671分量，来源于用户程序记录。全国PBF与完整城市边/路线GeoJSON没有在云端重读；全部城市路径逐点重算明确引用用户程序自检。

南京锚点仍在分量7的siding“1道”，现有片段不足以认定完整断连原因。西宁、贵阳、天津的大偏移及站场股道、兰州的空间接入仍应结合完整站场复核。未知用途、异常usage标签、达到500条上限的近邻断点诊断也有局限，不自动补线。

## ZIP与图件

解压进入 `OSM_Railway_Project`：

- `report/v3/deliverables/`：Word、PDF、在线正文。
- `report/v3/input/`：本次上传13个原始文件，保留字节；直接克隆源码时不含这份忽略目录，请从本页成果ZIP取得。
- `report/v3/figures/`：完整城市图、带km展示图、统计与局部真实轨道图的PNG/SVG；两张用户原始PNG也原样保留。
- `report/v3/audited_city_stations.csv`：原始列加审计状态，不修改真实锚点。
- `report/v3/independent_audit.json`、`SOURCE_MANIFEST.json`、`REVIEWED_SNAPSHOT.json`：独立核验、来源指纹与本轮审阅输入锁定。
- `src/`、`tests/`、`tools/`、Windows脚本：完整可运行源码与安装/运行工具。

此ZIP是**报告、源码和小型复核材料包**，不替代用户本机完整全国输出。`edge_paths.geojson`、`railway_tracks.geojson`、`guangzhou_lanzhou_path.geojson`等大型完整几何仍在Windows的 `outputs`，本包没有伪造或以局部线段代替。请保留本机完整成果与原始PBF。包内不含大型PBF、全国缓存、虚拟环境或日志。

图版本6/身份3对应发布提交 `8c97b8f3dc5490baadd86613dd3e17152b868abc`。运行状态记录了这两个版本，但没有源码提交哈希；因此不声称已独立核对用户全部源码字节。本轮真实数据已在Windows重建，不能继续沿用第2版“新模式代码尚未全国重跑”的旧状态。源码已有31项测试及小型PBF验证记录；Windows CMD本身未在云端执行。

## 重新核验和排版

直接阅读Word/PDF无需安装Python。若需要复算，在解压后的项目目录地址栏输入 `cmd`，项目已有Python 3.12虚拟环境时执行：

```bat
.venv\Scripts\python.exe -m pip install -r report\requirements.txt
.venv\Scripts\python.exe report\verify_results.py report\v3\input
.venv\Scripts\python.exe report\build_report.py --input report\v3\input --output-root report\v3
.venv\Scripts\python.exe report\package_submission.py --report-root report\v3
```

首次安装可按根目录 `WINDOWS_GUIDE.md` 双击 `install.bat`。表格核验与已有字体后的排版不需要PBF和网络；安装依赖及首次重建字体需要网络。报告输入哈希锁定到本轮已审阅快照，新运行结果必须先审阅，再更新报告配置，不能自动套用旧结论。

OSM及派生图件 © OpenStreetMap contributors / ODbL 1.0；见根目录 `DATA_LICENSE.md`。PDF嵌入Noto Sans SC字体子集，OFL许可见 `report/fonts/OFL.txt`；完整字体不入包。源代码适用根目录 `LICENSE`。
