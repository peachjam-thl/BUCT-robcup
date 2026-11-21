# 原始模型与静态TF执行卡

日期：2026-11-21。原文件盘点、离线检查、三项实际数据查询及RViz联合显示均有记录；[原始数据](../日志/证据/2026-11-21/static-tf-checks.md)、[配置](../tools/rviz/static_check.rviz)与[截图](../日志/证据/2026-11-21/rviz-joint-display.jpg)已入库。动态里程计TF未验证。

**当前收尾：门控、底盘驱动、静态模型、雷达和RViz均已退出，节点列表为空；四轮架空、USB仍连接。** 14:03的“三项未执行”是历史暂停点，同日后续已完成。下次先读[最新日志](../日志/2026-11-21.md)，查本轮供电/USB、时间和节点；本页保留静态检查复现步骤，运动相关接续先按[D3入口](D3门控与统一启动.md)执行。

## 2026-11-21 实采结果（本会话执行）

板子重启后 ROS 图为空（`ros2 node list` 无输出、`/tf_static` unknown）。重新上传并启动[静态入口](../tools/vendor_model_static.launch.py)后采集，原始输出存于[证据](../日志/证据/2026-11-21/static-tf-checks.md)。

| 检查 | 实际输出 |
| --- | --- |
| `base_footprint→laser` | Translation `[0.032, 0.000, 0.095]`，单位四元数；与 `0.03163 / 0.00009 / 0.09502` 一致（打印三位小数） |
| `base_footprint→camera_link` | Translation `[0.107, 0.000, 0.076]`，单位四元数；与 `0.1070947 / 0.0003171 / 0.076204` 一致 |
| `/joint_states` | `lf/lb/rb/rf_wheel_joint`，`position` 全 `0.0`，`velocity`/`effort` 空 |
| `/tf_static` 发布者 | 3 个，边不重复：`base_footprint→base_link`、`base_footprint→laser`、`base_link→camera_link/controller_link/laser_link` |

两次 `tf2_echo` 首行都出现 `Invalid frame ID "base_footprint"`，随后才输出变换，符合查询初期尚未收到静态TF的现象；全过程已保留，按后续实际输出判定。`laser`与`laser_link`是不同子帧，各自发布职责已核对。本轮未取得里程计父帧到`base_footprint`的动态TF证据。

## 配置采用原则

用户明确要求：已有车身原始文件详细记录的数据，按原文件执行。因此已有尺寸、外参、坐标关系和机型选择以车上安装版文件为基线，不要求重复人工测量，不用粗测结果覆盖。只在缺失、文件冲突或运行异常时针对问题核查。19.5cm保留为用户提供的雷达顶部离地高度，不自动用作TF的Z值。

## 已核对来源

- `turn_on_wheeltec_robot/launch/turn_on_wheeltec_robot.launch.py`：已复制源文件选择mini_mec，并含base_footprint到base_link的零变换；完整入口还启动底盘、IMU/EKF，不用于本轮静态试验。新工具会在板端重新读取安装版并核对机型。
- 用户回传安装版`robot_mode_description_minibot.launch.py`：mini_mec使用mini_mec_robot.urdf，base_footprint到laser平移为0.03163 / 0.00009 / 0.09502m，旋转为0 / 0 / 0。
- 用户回传安装版`mini_mec_robot.urdf`：根为base_link，含四轮关节、controller_link、laser_link与camera_link。laser_link关节保留原始yaw=pi；它与实际LaserScan的laser不是同名帧。
- 历史启动前ROS图：只有雷达、RViz等，/tf_static发布者0。14:03模型入口启动，随后同日已取得实际消息；收尾时所有相关节点退出。

原URDF通过robot_state_publisher发布base_link到camera_link；原模型launch另有base_footprint到camera_link的静态发布，会争用同一个子帧。新入口保留URDF中的camera_link发布，省略额外的相机静态节点。**只整理新入口的发布职责，不改厂商文件或其中的数值。**

laser与laser_link是不同子帧，共存本身不构成重复发布；不把laser_link的原始pi旋转追加到扫描帧laser。检查目标是每个子帧具有唯一父帧和明确、无冲突的发布来源，不是要求整个/tf_static只有一个发布者。新入口的robot_state_publisher和两个静态节点分别负责不同边，多个话题发布者本身正常；启动前拒绝已有发布者只是本工具防止叠加启动的约束。

## 静态入口

[vendor_model_static.launch.py](../tools/vendor_model_static.launch.py)在板端读取已安装的原始launch字面参数及完整URDF，不导入或执行原整车launch。仅启动robot_state_publisher、joint_state_publisher和两条静态变换：

```text
base_footprint
├── base_link                 原完整launch的base_to_link值
│   ├── camera_link           原URDF
│   ├── laser_link            原URDF，保留原始pi旋转
│   ├── controller_link       原URDF
│   └── 四轮link              默认关节角，仅用于静态模型显示
└── laser                     原mini_mec模型launch的扫描外参
```

入口不启动底盘、雷达、相机驱动、里程计、EKF、SLAM或导航，不发布速度。轮子关节值来自静态显示工具，不是编码器反馈。不会伪造map/odom TF。原数据文件缺失、形式不支持、机型不符或子帧重复则停止，不猜默认参数。启动前若检测到已有/tf_static发布者则拒绝叠加；发现有延迟，启动后仍需检查真实发布关系。

Windows PowerShell上传：

```powershell
scp "D:\Personal\Desktop\LETSROS\tools\vendor_model_static.launch.py" wheeltec@192.168.128.10:/tmp/vendor_model_static.launch.py
```

复现静态显示时，在已加载Humble和wheeltec_ros2环境的新小车SSH终端执行。先查现有TF发布者，避免与包含同一模型的完整入口叠加；当前收尾后没有原雷达进程可沿用，需显示扫描时按[雷达执行卡](雷达静态验收.md)单独恢复：

```bash
ros2 launch /tmp/vendor_model_static.launch.py
```

若启动失败，保留原始错误，不改为运行完整整车launch。14:03启动日志已归档在[静态模型启动输出](../日志/证据/2026-11-21/static-model-startup.md)，包含旧式参数及KDL根link惯性警告；当前不为消除警告修改原文件。

## 静态数据复现步骤（2026-11-21已执行）

先读取GitHub最新记录，连接小车后在空闲SSH终端加载环境、查看当前节点：

```bash
source /opt/ros/humble/setup.bash
source ~/wheeltec_ros2/install/setup.bash
ros2 node list
```

最后一次收尾已确认节点为空；恢复时仍以新输出为准，核对雷达及vendor_static_*节点。需要复现静态显示时按本页恢复缺少的进程；若其他会话已启动则先核对职责，不重复启动。/tmp文件可能需要重新上传；部分节点残留或未知TF发布者时先核对原终端，不强行叠加。

确认对应进程运行后，在空闲SSH终端依次执行：

```bash
timeout 6s ros2 run tf2_ros tf2_echo base_footprint laser
timeout 6s ros2 run tf2_ros tf2_echo base_footprint camera_link
timeout 6s ros2 topic echo /joint_states --once
```

应回传全部实际输出，而不是只写“成功”：

- [x] base_footprint→laser：能查询到约(0.03163,0.00009,0.09502)m和单位旋转。—— 2026-11-21 实测 `[0.032, 0.000, 0.095]` + 单位四元数。
- [x] base_footprint→camera_link：能查询到原URDF相机变换（当前base连接为零，预期平移约0.1070947/0.0003171/0.076204m），不等于相机驱动验收。—— 实测 `[0.107, 0.000, 0.076]` + 单位四元数。
- [x] /joint_states：收到四轮关节名称与默认显示位置；它们不是编码器或轮速反馈。—— 实测四轮关节名，`position` 全 `0.0`，`velocity`/`effort` 为空。

复现时，前两项为持续查询，6秒结束可能返回124；依据此前是否输出正确变换判断。第三项应收到一条后自行结束，若只超时未收到消息则该次未通过。若最初等待发现、随后读到变换，保留全过程。11月21日已收到/joint_states，早期Waiting日志不能覆盖后续消息结果。

能查询到变换不等于已经排除重复发布来源；随后结合实际TF关系、节点和启动配置核对各子帧发布职责。关节默认显示值不证明编码器、轮速或里程计，相机TF正常也不证明相机驱动正常。

**三项验证有实际结果后**，再在RViz把Fixed Frame改为base_footprint、启用RobotModel/TF，检查/scan可转换并与模型对应，保存配置并回填日志。此时仍没有odom到base的动态TF，不能据此开始移动建图。

### RViz 联合显示（2026-11-21 已执行）

用[静态检查配置](../tools/rviz/static_check.rviz)在板端 `DISPLAY=:0` 启动 RViz（`rviz2 -d`），配置内容：Fixed Frame `base_footprint`、RobotModel（`/robot_description`）、TF、LaserScan（`/scan`，Points，5 px，白色）、Grid 0.5 m。板端副本在 `~/rviz/static_check.rviz`，日志 `/tmp/rviz.log`。

结果：`Global Status: Ok`，四轮与机身可分辨，白色扫描点围成墙/箱体轮廓，模型与扫描同时显示正常（屏幕照片：[rviz-joint-display.jpg](../日志/证据/2026-11-21/rviz-joint-display.jpg)）。

距离粗测：当时前方最近扫描点在车体坐标 `x=0.389 m, y=0.034 m`（离激光 0.359 m、偏轴 5.5°）；用户用卷尺从**车头外沿**量到同一障碍约 **26 cm**，差值约 13 cm 与车头外沿到车体中心的距离属同一量级。**这是粗测一致性，不作标定精度结论**；该 13 cm 未单独实测，扫描点偏轴也说明障碍面可能略斜。

仍未做：动态里程计TF、多传感器联合负载和重启后完整流程的稳定复现。RViz配置已随仓库版本管理；板端副本是运行副本，持久工具目录和统一环境入口仍待整理。静态关节值不代表编码器，相机TF不代表相机驱动验收。

## 检查与边界

`python tests/check_vendor_model_static.py`检查原参数读取、URDF保持、laser/laser_link区别、机型冲突、重复子帧、非法值及启动节点白名单；Python语法检查通过。电脑无ROS，测试使用最小原文件结构和接口替身，不代表实机导入、DDS或TF已验收。

接口核对：[Humble robot_state_publisher](https://github.com/ros/robot_state_publisher/blob/humble/README.md)、[Humble joint_state_publisher](https://github.com/ros/joint_state_publisher/blob/humble/joint_state_publisher/README.md)。后续运动时不把默认显示关节角作为真实轮速数据使用。
