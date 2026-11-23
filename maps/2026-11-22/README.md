# 2026-11-22 起始测试检查点

这是11月22日启动SLAM后的起始测试快照，原件来自本机`tmp/field-2026-11-22/field_20261122_152150/`，小车会话为`/home/wheeltec/ros_field_logs/20261122_152150_mapping/`。用户随后将车抬/推至实际场地，另开建图会话，因此本目录不代表正式场地地图，也不用于后续Nav2的默认地图。

当前已验证重载与导航的场地地图见[2026-11-23](../2026-11-23/README.md)。本次仅按用户要求补档，没有新增实车试验。

## 文件与完整性

| 文件 | 字节数 | 用途 |
| --- | --- | --- |
| [start_checkpoint_session.posegraph](start_checkpoint_session.posegraph) | 17,965,345 | 位姿图原件 |
| [start_checkpoint_session.data](start_checkpoint_session.data) | 17,994 | 位姿图配套数据，恢复时与原件同目录、同前缀 |
| [start_checkpoint.pgm](start_checkpoint.pgm) | 5,712 | 起始栅格图，仅作测试快照 |
| [start_checkpoint.yaml](start_checkpoint.yaml) | 135 | 栅格元数据，分辨率0.05m，图像引用与同目录PGM配套 |

文件以原始字节复制；源文件与仓库副本的SHA256一致：

```text
start_checkpoint_session.posegraph  6e58fd8de9dbf3e55e2c3ff389fe5970a9d9bb432137749e6bd586a51a1f2ae0
start_checkpoint_session.data       1f7662eb306ba973b603896a90e3d6624bb0d880da2d62075d8b3046b073e160
start_checkpoint.pgm                5a835240930c9d62985c1002480be3a259d1014a9f04eceb4d2b74f05e1df00a
start_checkpoint.yaml               931eeb6cb844be386893bf426e892f69123cb12b576f6234fafd8d974802ac0b
```

栅格尺寸为37×154，原点及阈值以YAML为准；这只是起始视角的数据，不是完整房间覆盖或尺度质量验收。位姿图恢复前缀为`start_checkpoint_session`，栅格加载入口为`start_checkpoint.yaml`，两者名称不同，不要混用。
