把以下两个文件放在本目录；请勿重命名或上传到 Git：
china-latest.osm.pbf
taiwan-latest.osm.pbf

默认运行只读本地文件，不强制联网。
首次运行记录 SHA-256、OSM PBF 文件头和数据日期（如文件头提供）。
完整解析成功后才在 sources.json 中标记 full_pbf_parse_completed。
没有联网核对的本地文件不会被标为已通过上游 MD5 校验。

可选：guangdong-latest.osm.pbf；运行 run_windows.bat --with-guangdong 时使用。
