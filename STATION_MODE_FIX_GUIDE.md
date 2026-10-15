# 修正站场交通方式漏检：一次重跑并自动打包

本次 `Station_Diagnostics.zip` 的原始标签已经证明：福州所选 relation 19659201 的停靠节点 9521844144 带 `subway=yes`，轨道为滨海快线；国铁站另有 node 6999105218，带 `train=yes`。先前仅做名称、距离消歧不足以排除同名地铁停靠点。新的代码修正此漏检，不通过扩大阈值或补线制造连接。

## 操作步骤

1. [下载 Station_Mode_Fix.zip](https://github.com/zyx0309/scutwork/raw/refs/heads/main/updates/Station_Mode_Fix.zip)。它只包含源码、测试、脚本及说明，没有 PBF、缓存、虚拟环境或全国结果。
2. 全部解压，打开 `Station_Mode_Fix` 文件夹，将里面的内容复制到原项目 **`E:\scutwork-main`**。同名文件允许替换、目录允许合并。不要把整个文件夹再套到原项目里面。
3. 保留原有 `data`、`.venv`。不需要重新安装 Python、依赖或下载地图；保持现有 PBF 文件名，不删除 `data/cache`。
4. 双击原项目中的 **`run_mode_fixed.bat`**。它先移动备份旧 `outputs`，然后重建车站映射和轨道图，重新计算、导出及绘图；成功后自动生成小型诊断包。结束或报错后窗口保留。
5. 完成后上传 **`outputs\submission\Station_Diagnostics.zip`**。这一次脚本会自动收集完整的新一轮小文件和图，不必再单独双击诊断脚本。

只要输入和提取规则没有变，`rail_subset.sqlite` 仍可复用；旧车站图自动失效。仍需要大文件 SHA 校验及城市路径搜索，运行时间取决于机器和磁盘。程序处理本地文件不自动联网。

## 如何确认使用了新版

新 `outputs/run_status.json` 成功时应有：

```json
{
  "status": "completed_real_osm",
  "graph_version": 6,
  "station_identity_version": 3
}
```

福州不能再选用 `subway=yes` 的停靠点。若国铁站没有可靠轨道锚点，新版会保留真实车站的名称、OSM ID 和坐标，标为未接入，不转用同名地铁站。不要为了得到旧的 30 个接入或旧距离而改结果。

`city_stations.csv` 新增完整站点标签、轨道节点标签和 `station_transport_evidence`。未接入的海口、西安、乌鲁木齐等站也保留已识别对象，便于在局部图中查看，不再只输出空白名称/坐标。`station_candidate_rejections.csv` 记录模式拒绝原因及相关停靠节点 ID。

## 规则与验证范围

- 除了 `station=subway`，也检查 `subway=yes`、轻轨/有轨电车/单轨等明确交通方式以及 `train=no`。
- 站场关系逐个检查实际停靠成员；纯地铁停靠关系即使名称为“火车站”也不能压过国铁站。混合关系只使用符合重铁口径的成员。
- 明确 `train=yes` 的站点或合法成员优先于交通方式未知候选。可靠身份的站点无法接入时保留未接入状态，不用较弱身份的已连通候选替换。
- 轨道空间匹配仍限制在 150 m 内，仍待人工核验；没有添加任何线路或车站间零距离连接。

31 项测试通过，包含从本次真实诊断包抽取的福州标签/几何回归用例；它能阻止误选滨海快线停靠点。小型 PBF 全流程、CSV/图导出和自动诊断打包也进行实际验证。Windows CMD 及修正后全国数据仍需本机运行，云端没有据局部样本推断新的全国接入数、边数或总里程。

南京目前只证实锚点落在 `service=siding` 的“1道”，无法仅凭一条轨道判断完整站场的断连原因。海口、西安、乌鲁木齐有真实车站对象，但缺可靠锚点的具体原因仍需本地完整站场检查；本补丁不会自动宣布这些问题已解决。

日志：`logs/run_日期_时间.log`；旧成果：`backups/outputs_日期_时间`。处理失败时保留日志，不删除 PBF。若诊断包超过 30 MiB，先上传 `outputs/station_diagnostics.json`，其他 CSV/JSON 与 PNG 可分开发送。
