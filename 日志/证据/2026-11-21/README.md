# 2026-11-21 证据索引

来源为用户本日提供的原始照片、用户标注图和粘贴的终端输出。本目录归档四张代表性图片，逐字节复制并与源文件核对SHA256；未编辑、重绘或压缩。box-identified.png中的红圈由用户提供，用于声明箱子对应的回波。

| 文件 | 内容 / 可支持的结论 | 边界 |
| --- | --- | --- |
| [bench-scene.jpg](bench-scene.jpg) | 小车、箱子和室内场景摆放 | 单张照片不能精确恢复距离、扫描高度或坐标外参 |
| [box-identified.png](box-identified.png) | 用户红圈标出箱子对应回波 | 按操作者对应关系记录，未进行自主目标识别 |
| [front-box-selection.jpg](front-box-selection.jpg) | 前方箱子选中点坐标；卷尺约93cm由用户文字补充 | 图中代表点径向约91.3、91.7、94.1cm；单帧、约数，不是精度标定 |
| [left-box-selection.jpg](left-box-selection.jpg) | 左侧箱子选中点，Y为正、X接近0；用户文字报告100cm | 中心附近回波约90cm，约10cm差异来源未确认，保留待复测；不覆盖原配置 |
| [static-model-startup.md](static-model-startup.md) | 用户粘贴的14:03静态模型启动输出 | 支持原参数读取、URDF解析、进程启动及节点自报发布，不等于实际TF消息查询通过 |
| [static-tf-checks.md](static-tf-checks.md) | 2026-11-21 通过 USB SSH 补测的两项 `tf2_echo`、`/joint_states`、`/tf_static` 发布者与边 | 支持静态 TF 与关节显示值已实际取得；不含动态 TF、RViz 联合显示或相机驱动结论 |
| [rviz-joint-display.jpg](rviz-joint-display.jpg) | 板端 RViz 屏幕照片：Fixed Frame `base_footprint`、RobotModel、TF、LaserScan 同时显示，Global Status Ok | 支持联合显示成立；屏幕翻拍，不能据此做精度标定；不含动态 TF |

## 原图SHA256

```text
6cd383f4ef6b2a2516649aa66a7574bae7b0020bab8ed4661dda002e5c8094a9  bench-scene.jpg
037909538023bb690b46266d9b0a1d71ce3fde30befc198caa4e8ac806b41e75  box-identified.png
81d56713ff712e567ebaf37c15c5a9411b08d9ac943a7924437141e3fae7d246  front-box-selection.jpg
ec78f161a2c42ac8c61dd9d9e77230b6d26b4c61e810f260afde4856478f2d9b  left-box-selection.jpg
```

照片拍摄角度、显示点大小和目标位置会影响观察；未由截图估算完整有效点比例、长时稳定性或全向覆盖。右侧测试被用户跳过；顶部高度19.5cm仅有用户粗测描述。三项静态数据查询已于本日通过 USB SSH 补做并归档到 [static-tf-checks.md](static-tf-checks.md)；仍未归档车上实际导出的 RViz 配置，也未完成 RViz 联合显示。

接续以[当日日志](../../2026-11-21.md)与[原始模型/静态TF执行卡](../../../docs/原始模型与静态TF.md)为准。其他会话照片未全部复制，不把代表性归档写成完整传感器原始数据集。
