# 原始模型与静态TF执行卡

日期：2026-11-21。原文件盘点及电脑离线检查完成；14:03新增入口已在小车启动，两个静态节点打印发布日志、URDF解析出各部件。**三项实际数据查询已于 2026-11-21 由 USB SSH 补执行并归档（见下节）；RViz联合显示仍待验收**，不能仅由进程启动记为通过。

**暂停点：用户已明确下面的三项实际数据验证在 14:03 时尚未执行。** 后续已在同一日通过 USB SSH 补做，结果见下一节与[证据](证据/2026-11-21/static-tf-checks.md)。是否已经退出各终端进程尚未回传；不要假定进程一直运行或已自动停止。

## 2026-11-21 实采结果（本会话执行）

板子重启后 ROS 图为空（`ros2 node list` 无输出、`/tf_static` unknown）。重新上传并启动[静态入口](../tools/vendor_model_static.launch.py)后采集，原始输出存于[证据](证据/2026-11-21/static-tf-checks.md)。

| 检查 | 实际输出 |
| --- | --- |
| `base_footprint→laser` | Translation `[0.032, 0.000, 0.095]`，单位四元数；与 `0.03163 / 0.00009 / 0.09502` 一致（打印三位小数） |
| `base_footprint→camera_link` | Translation `[0.107, 0.000, 0.076]`，单位四元数；与 `0.1070947 / 0.0003171 / 0.076204` 一致 |
| `/joint_states` | `lf/lb/rb/rf_wheel_joint`，`position` 全 `0.0`，`velocity`/`effort` 空 |
| `/tf_static` 发布者 | 3 个，边不重复：`base_footprint→base_link`、`base_footprint→laser`、`base_link→camera_link/controller_link/laser_link` |

两次 `tf2_echo` 首行都出现 `Invalid frame ID "base_footprint"`，随后才输出变换——`tf_static` 晚于查询到达的瞬态，不是失败；全过程已保留。`laser` 与 `laser_link` 同时存在不构成重复发布（父帧不同）。本轮无 `odom→base_footprint` 动态 TF。

## 配置采用原则

用户明确要求：已有车身原始文件详细记录的数据，按原文件执行。因此已有尺寸、外参、坐标关系和机型选择以车上安装版文件为基线，不要求重复人工测量，不用粗测结果覆盖。只在缺失、文件冲突或运行异常时针对问题核查。19.5cm保留为用户提供的雷达顶部离地高度，不自动用作TF的Z值。

## 已核对来源

- `turn_on_wheeltec_robot/launch/turn_on_wheeltec_robot.launch.py`：已复制源文件选择mini_mec，并含base_footprint到base_link的零变换；完整入口还启动底盘、IMU/EKF，不用于本轮静态试验。新工具会在板端重新读取安装版并核对机型。
- 用户回传安装版`robot_mode_description_minibot.launch.py`：mini_mec使用mini_mec_robot.urdf，base_footprint到laser平移为0.03163 / 0.00009 / 0.09502m，旋转为0 / 0 / 0。
- 用户回传安装版`mini_mec_robot.urdf`：根为base_link，含四轮关节、controller_link、laser_link与camera_link。laser_link关节保留原始yaw=pi；它与实际LaserScan的laser不是同名帧。
- 启动模型前的ROS图：只有雷达、RViz等，/tf_static发布者0。随后14:03模型入口已启动；实际消息查询还未执行。

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

在已加载Humble和wheeltec_ros2环境的新小车SSH终端执行，原雷达终端保持运行：

```bash
ros2 launch /tmp/vendor_model_static.launch.py
```

若启动失败，保留原始错误，不改为运行完整整车launch。14:03启动日志已归档在[静态模型启动输出](../日志/证据/2026-11-21/static-model-startup.md)，包含旧式参数及KDL根link惯性警告；当前不为消除警告修改原文件。

## 下次第一项：验证实际数据（明确未执行）

先读取GitHub最新记录，连接小车后在空闲SSH终端加载环境、查看当前节点：

```bash
source /opt/ros/humble/setup.bash
source ~/wheeltec_ros2/install/setup.bash
ros2 node list
```

应核对雷达节点及vendor_static_robot_state_publisher、vendor_static_joint_state_publisher、两个vendor_static_base_to_*是否仍在。若雷达和静态模型都在运行，不重复启动，直接查询；若已退出或小车重启，则按本页原入口恢复对应进程。/tmp文件可能需要从GitHub仓库重新上传。部分模型节点残留或未知TF发布者时先核对原终端，不强行叠加。

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

前两项为持续查询，6秒结束可能返回124；依据此前是否输出正确变换判断。第三项应收到一条后自行结束，若只超时未收到消息则尚未通过。若最初等待发现、随后读到变换，保留全过程。joint_state_publisher的Waiting日志仍需由消息检查确认后续结果。

能查询到变换不等于已经排除重复发布来源；随后结合实际TF关系、节点和启动配置核对各子帧发布职责。关节默认显示值不证明编码器、轮速或里程计，相机TF正常也不证明相机驱动正常。

**三项验证有实际结果后**，再在RViz把Fixed Frame改为base_footprint、启用RobotModel/TF，检查/scan可转换并与模型对应，保存配置并回填日志。此时仍没有odom到base的动态TF，不能据此开始移动建图。本次归档不执行上述步骤。

## 检查与边界

`python tests/check_vendor_model_static.py`检查原参数读取、URDF保持、laser/laser_link区别、机型冲突、重复子帧、非法值及启动节点白名单；Python语法检查通过。电脑无ROS，测试使用最小原文件结构和接口替身，不代表实机导入、DDS或TF已验收。

接口核对：[Humble robot_state_publisher](https://github.com/ros/robot_state_publisher/blob/humble/README.md)、[Humble joint_state_publisher](https://github.com/ros/joint_state_publisher/blob/humble/joint_state_publisher/README.md)。后续运动时不把默认显示关节角作为真实轮速数据使用。
