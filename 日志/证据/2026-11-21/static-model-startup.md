# 静态模型启动输出（用户终端转录）

来源：用户粘贴的小车SSH终端输出。时间为板端日志2026-11-21 14:03；转录保留原信息和警告，统一Markdown换行，不是直接取回的ROS日志文件。没有后续TF或关节消息查询输出，用户明确查询尚未执行。

```text
wheeltec@wheeltec:~$ source /opt/ros/humble/setup.bash
source ~/wheeltec_ros2/install/setup.bash
ros2 launch /tmp/vendor_model_static.launch.py
[INFO] [launch]: All log files can be found below /home/wheeltec/.ros/log/2026-11-21-14-03-49-014271-wheeltec-8735
[INFO] [launch]: Default logging verbosity is set to INFO
[INFO] [launch.user]: STATIC MODEL ONLY: installed vendor values; no base driver, lidar, odom or SLAM.
[INFO] [launch.user]: URDF: /home/wheeltec/wheeltec_ros2/install/wheeltec_robot_urdf/share/wheeltec_robot_urdf/urdf/mini_mec_robot.urdf
[INFO] [launch.user]: Vendor base TF: 0 0 0 0 0 0 base_footprint base_link
[INFO] [launch.user]: Vendor scan TF: 0.03163 0.00009 0.09502 0 0 0 base_footprint laser
[INFO] [launch.user]: camera_link and laser_link are owned by the unmodified URDF; scan frame laser is distinct.
[INFO] [robot_state_publisher-1]: process started with pid [8746]
[INFO] [joint_state_publisher-2]: process started with pid [8748]
[INFO] [static_transform_publisher-3]: process started with pid [8750]
[INFO] [static_transform_publisher-4]: process started with pid [8752]
[static_transform_publisher-4] [WARN] [1795241032.239029952] []: Old-style arguments are deprecated; see --help for new-style arguments
[static_transform_publisher-3] [WARN] [1795241032.242261104] []: Old-style arguments are deprecated; see --help for new-style arguments
[static_transform_publisher-4] [INFO] [1795241032.416802190] [vendor_static_base_to_laser]: Spinning until stopped - publishing transform
[static_transform_publisher-4] translation: ('0.031630', '0.000090', '0.095020')
[static_transform_publisher-4] rotation: ('0.000000', '0.000000', '0.000000', '1.000000')
[static_transform_publisher-4] from 'base_footprint' to 'laser'
[static_transform_publisher-3] [INFO] [1795241032.423492326] [vendor_static_base_to_link]: Spinning until stopped - publishing transform
[static_transform_publisher-3] translation: ('0.000000', '0.000000', '0.000000')
[static_transform_publisher-3] rotation: ('0.000000', '0.000000', '0.000000', '1.000000')
[static_transform_publisher-3] from 'base_footprint' to 'base_link'
[robot_state_publisher-1] [WARN] [1795241032.722310267] [kdl_parser]: The root link base_link has an inertia specified in the URDF, but KDL does not support a root link with an inertia.  As a workaround, you can add an extra dummy link to your URDF.
[robot_state_publisher-1] [INFO] [1795241032.722799931] [vendor_static_robot_state_publisher]: got segment base_link
[robot_state_publisher-1] [INFO] [1795241032.723054805] [vendor_static_robot_state_publisher]: got segment camera_link
[robot_state_publisher-1] [INFO] [1795241032.723107555] [vendor_static_robot_state_publisher]: got segment controller_link
[robot_state_publisher-1] [INFO] [1795241032.723144763] [vendor_static_robot_state_publisher]: got segment laser_link
[robot_state_publisher-1] [INFO] [1795241032.723180263] [vendor_static_robot_state_publisher]: got segment lb_wheel_link
[robot_state_publisher-1] [INFO] [1795241032.723215013] [vendor_static_robot_state_publisher]: got segment lf_wheel_link
[robot_state_publisher-1] [INFO] [1795241032.723249596] [vendor_static_robot_state_publisher]: got segment rb_wheel_link
[robot_state_publisher-1] [INFO] [1795241032.723283554] [vendor_static_robot_state_publisher]: got segment rf_wheel_link
[joint_state_publisher-2] [INFO] [1795241034.339036907] [vendor_static_joint_state_publisher]: Waiting for robot_description to be published on the robot_description topic...
```

本输出支持静态入口已在板端启动并读取原参数，不能证明消息查询、唯一TF发布关系、关节消息到达、RViz联合显示或导航功能通过。原厂文件未因两项警告而修改；后续以实际查询结果判断。
