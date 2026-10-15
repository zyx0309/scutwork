# 导出本地车站证据：无需重新处理全国 PBF

2026-10-15 的三份重跑文件表明：台湾“浮洲”候选已被拒绝；福州现在选择 relation 19659201“福州火车站”，锚点 9521844144，位于分量 1109。它没有接入主体分量。南京锚点属于分量 7，也仍然孤立。图上位置和站名不能独自证明是目标重铁站及正确股道，需要查看原始交通方式标签、成员关系和轨道 way。

无需再双击 `run_fixed.bat` 或删除缓存。本工具只读取已有 SQLite 子集，不读取大型 PBF、不加载全国图、不联网、不重选车站、不添加连接。会收集原始完整标签和节点/线路证据，并将当前小型结果及两张检查图打包，方便继续核对和更新报告。

## Windows 操作

1. [下载诊断工具 ZIP](https://github.com/zyx0309/scutwork/raw/refs/heads/main/updates/Station_Diagnostics_Tool.zip)。
2. 全部解压，打开 `Station_Diagnostics_Tool` 文件夹。
3. 将里面的 `tools` 文件夹、`diagnose_stations.bat` 和说明复制到原项目 **`E:\scutwork-main`**。提示同名文件时允许合并并替换。保留原有 `data`、`.venv` 和 `outputs`。
4. 在原项目目录双击 **`diagnose_stations.bat`**。无需安装新依赖。窗口显示 4 阶段进度，并按每 50,000 条缓存线路刷新；完成或出错后等待按键。
5. 上传新生成的 **`E:\scutwork-main\outputs\submission\Station_Diagnostics.zip`**。不需要上传 PBF 或缓存数据库。

只打包小文件，通常远小于原来的全国成果 ZIP。若提示超过 30 MiB，可先上传 `outputs/station_diagnostics.json`，其他 CSV/JSON 与图片分开发送。错误日志在 `logs/diagnostics_日期_时间.log`。

## 收集哪些信息

重点城市为福州、南京、海口、西安、乌鲁木齐、兰州、西宁、天津、贵阳：

- 当前选定对象及锚点的完整原始 OSM 标签，而不只是名称字段。
- 同名站候选、OSM 对象类型/ID、来源、站场成员关系及其原始标签；用于检查同名地铁站、候选歧义和缺少停靠关系等可能性，不预先断言具体原因。
- 锚点、候选和实际停靠节点涉及的轨道 way，完整 refs、usage/service/access 等标签及当前筛选分类。
- 这些 way 的现有节点坐标、所选分量对应的疑似断点记录。
- 新一轮完整 `cities.csv`、`city_edges.csv`、路线状态和分段 CSV，以及原有的车站局部图、路线 PNG（存在时）。这些文件用于后续报告，避免混入上一轮输出。

缓存来源指纹必须与当前 `data_quality.json` 一致，且最近运行必须完成，否则停止并保留日志。SQLite 以只读模式打开，原有 CSV、图和数据库保持不变；新增 `station_diagnostics.json` 及诊断 ZIP。

提取子集没有保存的对象无法由本工具补造。如果仍缺关键交通方式证据，会明确指出并进一步限定结果；不会通过扩大 150 m 阈值或自动补线来让全国连通。

已在云端用小型人工 PBF 实际验证只读诊断和 ZIP 生成；Windows CMD 及本机全国缓存上的运行仍需由上述步骤完成。
