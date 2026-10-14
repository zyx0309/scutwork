# Windows：从解压到查看结果

本项目的全国真实数据尚未在云端处理。云端验证包括源码编译、依赖检查、小型人工 PBF 测试和文件/绘图导出；这些不证明全国轨道连通、34 站已成功映射，也不提供真实广州至兰州总长度。下面的本地运行才处理你的真实文件。

## 1. 安装 Python

安装 **Python 3.12.x 的 Windows 64 位版本**。初学者可直接打开官方 **Python 3.12.10** 下载页：

https://www.python.org/downloads/release/python-31210/

向下找到 **Files**，点击 **Windows installer (64-bit)**。请勿选择 32-bit、ARM64、embeddable package 或源码压缩包。

打开安装程序后：

1. 在首屏底部勾选 **Add python.exe to PATH**（必须勾选）。
2. 保留 **Install launcher for all users (recommended)** / Python Launcher 选项；如需要管理员权限但没有权限，可用当前用户安装，脚本也能通过 PATH 中的 `python` 找到正确版本。
3. 点击 **Install Now**。不需要 Customize installation，不需要额外安装 Visual Studio。
4. 看到 **Setup was successful** 后点击 Close。如出现 **Disable path length limit**，有权限时可点击；没有权限也可以选择较短的项目解压位置。
5. 如刚安装后旧的命令行窗口还找不到 Python，关闭旧窗口再双击 `install.bat`。

不要使用其他主次版本或 32 位 Python 执行这套固定依赖。脚本会检查 Python 版本及位数，避免误用。

Windows 10/11 通常已带 Microsoft YaHei 中文字体；程序优先使用该字体。你的总内存约 32 GB、当前可用约 16 GB，可以先关闭占内存较多的浏览器、游戏和其他应用再运行，接上电源并避免自动休眠。全国真实数据的峰值内存尚未实测，不保证 16 GB 可用一定足够。预留 20 GB 以上磁盘。首次安装依赖需要访问 PyPI；处理本地地图不需要联网。

## 2. 解压

将 ZIP **全部解压**。不要直接在压缩软件中双击脚本。解压后应有目录 `OSM_Railway_Project`，其中有：

```text
OSM_Railway_Project/
  install.bat
  run.bat
  test_windows.bat
  requirements.txt
  README.md
  WINDOWS_GUIDE.md
  src/
  tools/
  tests/
  data/raw/
  outputs/
```

可以放在 `D:\人工智能作业\铁路 项目\OSM_Railway_Project` 等包含中文和空格的位置；脚本根据自身位置运行，不依赖当前命令行目录。请不要放入只读目录或直接放在压缩包内。

## 3. 安装依赖

双击 `install.bat`。它会建立项目内 `.venv`，安装固定版本依赖并执行 `pip check`。结束时显示成功或失败，并等待按键，窗口不会立即关闭。安装日志在 `logs/install_日期_时间.log`。

也可在 PowerShell 使用：

```powershell
Set-Location -LiteralPath 'D:\人工智能作业\铁路 项目\OSM_Railway_Project'
.\install.bat
```

依赖只装到项目自己的 `.venv`，运行脚本会自动使用 `.venv\Scripts\python.exe`。无需手动激活，不会向系统 Python 安装这些项目依赖。云端已经确认所有直接依赖及其解析出的依赖有 Python 3.12 / Windows x64 wheel，无需在本机编译 C++。该检查不等同于实际 Windows 安装测试。

## 4. 放入两份 PBF

复制已有文件到：

```text
OSM_Railway_Project\data\raw\china-latest.osm.pbf
OSM_Railway_Project\data\raw\taiwan-latest.osm.pbf
```

文件名必须一致；注意资源管理器隐藏扩展名时不要造成 `.pbf.pbf`。不要将网页 HTML、ZIP 或未完成的 `.part` 文件改名为 PBF。

来源：

- https://download.geofabrik.de/asia/china-latest.osm.pbf
- https://download.geofabrik.de/asia/taiwan-latest.osm.pbf

原始 PBF 不进入 Git，也不进入自动生成的成果 ZIP。项目默认使用存在的有效本地文件；不会为了确认它们而强制联网。

## 5. 可选先跑小型测试

双击 `test_windows.bat`，或执行：

```powershell
.\test_windows.bat
```

测试自动在临时目录生成小型人工 PBF，结束后删除。测试不会读取你的大文件，也不会把测试站名、权重和路径当作真实全国成果。

## 6. 正式处理

双击 `run.bat`，或执行：

```powershell
.\run.bat
```

默认完全使用本地 PBF。窗口依次显示：文件检查 → 两遍流式提取 → 车站映射和轨道建图 → 各城市的压缩边搜索 → 路径导出及长度校验 → 中文绘图 → 自动打包。扫描期间会输出已扫描节点和已保留线路数量。

首次可能较久；不要仅因一段时间没有刷新就关闭窗口。任务管理器中 Python 的 CPU/磁盘活动可辅助判断。以后运行会复用有效子集和图缓存；大文件 SHA-256 仍会复核，避免错误复用改动后的地图。

## 7. 成功后查看

先打开 `outputs/run_status.json`：完整数据处理成功时状态为 `completed_real_osm`。再打开 `outputs/RESULTS.md` 查看成功映射数量、城市边数、连通分量、孤立城市以及广州至兰州的可达性和总几何里程。

- 网络图、车站全国/局部检查图：`outputs/figures/`，PNG 可直接双击，SVG 可在浏览器打开。
- 34 城市、代表站映射、连接及距离表：`outputs/*.csv`，UTF-8 BOM，适合 Excel 打开。
- 可追溯线形：`outputs/*.geojson`，可用 QGIS 查看；较大的底层文件不适合用记事本打开。
- 数据质量：`outputs/data_quality.json`，查看未知用途、缺失节点、版本冲突、孤立城市与疑似断点。
- 成果 ZIP：`outputs/submission/OSM_Railway_Results.zip`，不含大型 PBF。

先检查 `station_checks_detail.png` 中广州站、兰州站及 `spatial_match_needs_review` 的城市。空间匹配结果须人工复核，不能仅因程序退出码为 0 就认定所有代表站正确、路径可实际乘车。

如果广州至兰州不可达，仍输出城市图和质量记录；`guangzhou_lanzhou_status.json` 写明原因，不生成路线 CSV/GeoJSON/图冒充有效路线。澳门等城市在此筛选口径下允许孤立。

## 8. 出错时

窗口会保留，显示最新日志路径。查看：

```text
logs/run_日期_时间.log
logs/errors_日期_时间.log
outputs/run_status.json
```

`failed` 表示本次未完成，即使目录中存在前一次的输出也不能当作新结果。将日志内容发回可继续排查，不需要上传 PBF。

- Python 未找到：确认安装 3.12 64 位并启用 PATH/Launcher，再双击安装脚本。
- 缺少文件：核对 `data/raw/` 和两个完整文件名。
- PBF 格式/解析失败：重新核实下载是否完成；保留原文件，勿把 HTML 改名成地图。
- 文件 SHA-256 与旧记录不一致：若是主动更新地图，先备份旧结果与 `sources.json`，确认来源后删除旧 `data/raw/sources.json` 再运行。不要忽略未知文件变化。
- 内存或磁盘不足：释放资源，使用本地磁盘，查看剩余空间；不要添加虚构线路或缩短距离来“修复”结果。
- 中文字体缺失：恢复/安装 Microsoft YaHei 或 Noto Sans CJK 后重跑；SVG 使用转轮廓文字。
- 网络安装失败：检查本机是否能访问 `pypi.org` 和 `files.pythonhosted.org`；保留安装日志，不关闭 TLS 验证。

## 9. 补充广东（确有必要时）

如果质量记录显示港澳区域相关布局节点/车站缺失，可下载：

https://download.geofabrik.de/asia/china/guangdong-latest.osm.pbf

放到 `data/raw/guangdong-latest.osm.pbf` 后，在 PowerShell 执行：

```powershell
.\run.bat --with-guangdong
```

程序统一按 OSM 对象类型与 ID 去重，不因文件区域重叠将同一轨道长度累计两遍；不同日期的对象冲突会记录。该补充不意味着澳门轻轨进入重铁图，也不保证能修复运营或 OSM 拓扑缺口。
