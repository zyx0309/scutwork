# 修正福州误匹配：Windows 更新及重跑

此前程序将福州匹配到台湾浮洲站，是代码缺陷。旧版允许英文罗马化别名进入候选，又把拓扑关系放在名称身份之前；约 247 km 的城市偏移只警告而没有拒绝。不能通过直接改 CSV 站名、将匹配距离阈值调大或把孤立城市强行连边来修正。

## 1. 下载小型修正包

[下载 Station_Matching_Fix.zip](https://github.com/zyx0309/scutwork/raw/refs/heads/main/updates/Station_Matching_Fix.zip)

本包只有代码、脚本和说明，不含 PBF、虚拟环境、缓存和全国结果。已有 Python 3.12 与 `.venv` 可以继续使用，依赖没有变化。

## 2. 覆盖原项目中的代码

1. 先关闭正在运行的项目窗口。
2. 将修正包全部解压到一个临时文件夹，不要在压缩软件内直接运行。
3. 打开解压后的 `Station_Matching_Fix` 文件夹，直到可以看见 `src`、`tools`、`tests` 和 `run_fixed.bat`。
4. 选中该文件夹内的全部内容，复制到原项目根目录，例如 **`E:\scutwork-main`**。
5. Windows 提示同名文件时，选择替换目标文件，并允许合并目录。完成后，应有 **`E:\scutwork-main\run_fixed.bat`**；不要多套一层 `Station_Matching_Fix`。

保留原项目的 `data` 和 `.venv`。本包不包含这些目录，也不会用空文件覆盖它们。无需重新下载或移动两个大型 PBF。

## 3. 双击 run_fixed.bat

在原项目目录双击 **`run_fixed.bat`**。它会：

- 将旧 `outputs` 整个移动到 `backups\outputs_日期_时间`，保留旧结果，不复制大型几何文件。
- 自动使用原项目 `.venv\Scripts\python.exe`；本地处理不自动联网。
- 检查原有 PBF 和 SHA-256，继续使用有效的铁路子集缓存。
- 拒绝复用旧的车站/轨道图缓存，重新映射代表站、建图、计算城市边和广州→兰州路径。
- 在新的 `outputs` 中生成 CSV、GeoJSON、图表和成果 ZIP，记录日志并在结束或报错后保留窗口。

**不要删除整个 `data/cache`**。其中的 `rail_subset.sqlite` 和 `extraction.json` 在输入与提取规则未变时可复用，通常能省去两遍全国 PBF 扫描。旧图缓存由版本自动失效，手动删除缓存不是必要步骤。

大文件 SHA 校验、建图、城市边搜索及导出仍需要时间。若运行窗口显示 `Using cached railway subset`，表示复用了提取子集；本次首次更新不应显示“使用已缓存的轨道图和车站映射”。中途失败时先保留日志，不要移动原始 PBF。

如果 PBF 目前已经使用 `china-latest.osm.pbf`、`taiwan-latest.osm.pbf`，保持现有文件名可避免文件名变化使提取缓存失效。现在也支持唯一一份 `china-261013.osm.pbf` / `china-20261013.osm.pbf` 等日期版，不再必须重命名。存在多份日期版而没有 `latest` 时会报错要求明确选择，不擅自猜最新版本。

## 4. 检查是否使用了修正版

打开新 `outputs/run_status.json`，成功运行应有：

```json
{
  "status": "completed_real_osm",
  "graph_version": 5,
  "station_identity_version": 2
}
```

这是关键字段的节选，文件实际还有时间和路径状态等内容。再检查：

| 文件 | 检查内容 |
|---|---|
| `outputs/city_stations.csv` | 福州不能再是“浮洲”；若没有可靠福州候选，允许留空并标记拒绝/未接入 |
| `outputs/station_candidate_rejections.csv` | 拒绝对象的 OSM ID、原始名称标签、命中别名、坐标、城市距离、来源及原因 |
| `outputs/data_quality.json` | `station_identity_policy.version` 为 2；连通分量、未映射站、空间匹配及其他质量问题 |
| `outputs/figures/station_checks_detail.png` | 广州、兰州和所有空间匹配的局部轨道检查 |
| `outputs/guangzhou_lanzhou_status.json` | 新规则下是否可达、具体锚点和新计算的总长度 |
| `outputs/RESULTS.md` | 本次城市接入、边数、分量、孤立城市和拒绝候选数 |

不要把新结果强制改为旧的 351 条边或 2383.542 km。代表站锚点改变可能影响距离、城市连接和孤立状态；必须以本次运行输出为准。

## 本次修正和仍需复核的事项

修正规则：中文规范别名优先；仅英文命中但中文名称冲突的对象直接拒绝；车站距已识别 OSM 城市布局点超过 80 km 时直接拒绝；仅英文候选没有独立 OSM 城市位置时拒绝。80 km 是城市身份的安全上限，不是轨道吸附阈值，也不能证明范围内每个站都正确。股道空间匹配阈值仍为 **150 m**，匹配结果继续标为 `spatial_match_needs_review`。

新 CSV 另存名称匹配依据和原始名称标签。中文精确匹配但缺少独立城市布局点时仍明确标为待审，不把它称为人工核准。没有可靠候选时保留城市节点并记录原因，不换成同城另一个车站。

此次修正只处理已确认的站点身份缺陷和缓存更新。**24 个空间匹配待复核、南京等站的局部分量问题，不会因为名称规则修正而自动变成已确认正确。** 海口、西安、乌鲁木齐等未接入站仍应检查实际站点关系与轨道拓扑，不应扩大吸附阈值或自动补线。后续如需指定某条真实股道，应先依据本地 PBF/QGIS 和站场关系确认 OSM 节点 ID，再作为有记录的配置修改并重建图。

## 重跑后用于继续核对的文件

可上传以下小文件及图片，不需要全国 PBF 或大型底层 GeoJSON：

- `city_stations.csv`、`cities.csv`、`city_edges.csv`
- `station_candidate_rejections.csv`、`data_quality.json`、`run_status.json`、`RESULTS.md`
- `guangzhou_lanzhou_status.json`、`guangzhou_lanzhou_segments.csv`（可达时）
- `figures/station_checks_detail.png`、`figures/guangzhou_lanzhou_route.png`（可达时）

已有 Word/PDF 和报告成果 ZIP 是**修复前真实运行的审计版**，仍保留原始结果，不会随代码更新自动变成重跑后的报告。只有收到新的真实结果后，才能更新统计和报告结论。

## 云端验证范围

25 项小型数据测试已通过，覆盖名称冲突、同中文名跨地域拒绝、中文优先、英文候选城市约束、繁简与“火车站”后缀、旧图缓存重建、日期文件名、离线处理和旧输出备份等。另进行含误名站点的小型 PBF 全流程及绘图导出验证。小型数据明确标为人工测试，不能当作修正后全国成果。

全国 PBF 和 Windows CMD 未在云端运行。修正后福州能否成功接入、全国城市边数及广州→兰州里程仍须在你的电脑上实际运行验证。
