# 第二轮真实结果：交通方式审计版

- [Word 报告](deliverables/AI_Railway_Report_Audited.docx)
- [PDF 报告（18 页）](deliverables/AI_Railway_Report_Audited.pdf)
- [报告、源码与复核材料 ZIP](deliverables/AI_Railway_Submission.zip)
- [在线正文](deliverables/AI_Railway_Report_Audited.md)

本版依据本次上传的 `Station_Diagnostics.zip`，不混用第一轮输入。对应用户 Windows 全国真实运行：完成时间北京时间 **2026-10-15 10:47:07**，`graph_version=5`、`station_identity_version=2`。原始结果及图片保持原始字节，封面姓名、学号等保留待填写。

## 可以支持的结论

独立根据本轮 `city_edges.csv` 构图：34 城市、351 条边、8 个分量，主体为 K27；孤立城市为南京、福州、海口、西安、乌鲁木齐、台北、澳门。城市图 Dijkstra 得到广州→兰州 **2383.541507726979 km**，与程序底层图记录一致；55 段求和及节点衔接通过。全部距离为“基于 OSM 铁路线形计算的几何里程”，不是官方客运、计价里程或可乘坐列车方案。

站点自动接入数为 30，包含已确认错误的福州模式映射；派生审计拒绝后为 **29 个候选接入**，其中 **24 个空间匹配仍待复核**。不是 29 个已全部验收的站点。

此前台湾“浮洲”候选已经拒绝。本轮新误选对象 relation 19659201 的停靠节点 9521844144 明确带 `subway=yes`，位于滨海快线；国铁福州站另有 `train=yes` 的 node 6999105218。新报告详述这个交通方式漏检，不将同城同名的地铁站当成国铁代表站。派生审计表拒绝错误锚点，并列出已识别国铁对象，但不补造其新轨道节点。

南京仅能证实锚点在“1道”siding股道、分量7；不能凭一条轨道判断完整断连原因。海口、西安、乌鲁木齐有真实国铁站对象，仍未找到规则内可靠锚点。西宁、贵阳、天津的大偏移及站场股道应优先核验。报告附34站原始记录、55段距离、9幅正文图和原始34站局部PNG。

## 图件及独立验证边界

完整城市图、展示用最小生成森林和统计图由本轮 CSV 重绘。福州模式图、六站轨道片段检查图使用诊断 JSON 的真实节点坐标、完整 refs 与标签。它们只覆盖诊断所涉片段，不能代表完整站场。

用户本地生成的广州→兰州实际路线 PNG 原样纳入报告，未编辑或从图像反推坐标。本次没有重新读取全国 PBF，也未收到完整轨道路径 GeoJSON。全部城市边逐点几何验证仍引用用户程序自检；本地片段的模式核验和城市/分段表的独立复算分别标注。详见 `independent_audit.json` 与 `SOURCE_MANIFEST.json`。

此 ZIP 是**报告、源码和可核验小型结果材料**，不替代 Windows 的完整全国成果包。`edge_paths.geojson`、`railway_tracks.geojson`、`guangzhou_lanzhou_path.geojson` 等大型文件仍保存在用户电脑 `outputs`，没有伪造、删减后冒充完整轨道路径。请保留本机完整输出与原始地图。

## 新代码和本轮结果分开

本轮实际运行源码为提交 `a27a4e833922ef6dd0f138316452ac92c9daffe5`。包内源码已另外修正交通方式漏检，版本为图6/身份3，并保留未接入站的名称、OSM ID、坐标和完整标签。**新代码尚未全国重跑；报告统计不是新代码的运行结果。** 新代码通过31项测试，包括本包真实福州片段回归，以及小型PBF全流程、绘图和自动诊断打包。

若继续修正全国结果，按根目录 [STATION_MODE_FIX_GUIDE.md](../../STATION_MODE_FIX_GUIDE.md) 更新，双击 `run_mode_fixed.bat`；它备份旧输出、复用有效提取缓存、重建图并自动生成新的小型诊断 ZIP。没有提高150 m阈值、添加虚构连接或将同城多站零距离合并。

## 复现本报告

解压本页的报告材料 ZIP，在 `OSM_Railway_Project` 中使用项目 Python 3.12 虚拟环境：

```bat
.venv\Scripts\python.exe -m pip install -r report\requirements.txt
.venv\Scripts\python.exe report\verify_results.py report\v2\input
.venv\Scripts\python.exe report\build_report.py --input report\v2\input --output-root report\v2
.venv\Scripts\python.exe report\package_submission.py --report-root report\v2
```

阅读现成 Word/PDF 无需 Python。依赖安装、首次重建字体时需要网络；已有依赖/字体后，核验导出表不访问网络、不扫描 PBF。本报告脚本针对本轮已核验快照，不是任意新结果的通用报告模板；新的全国结果必须重新审阅后更新内容。

原始小型输入在 ZIP 的 `report/v2/input`；为避免冗余，它们不另行直接提交到 Git。完整字体不入包，PDF嵌入字体子集，Noto Sans SC 的OFL许可在 `report/fonts/OFL.txt`。OSM数据及派生图件署名 © OpenStreetMap contributors / ODbL 1.0，源码按根目录LICENSE适用。
