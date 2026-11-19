"""D3 bench entry. Sibling cmd_vel_gate.py is required. No auto arming."""
import os
from pathlib import Path
import subprocess
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, GroupAction, IncludeLaunchDescription
from launch.actions import LogInfo, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import SetRemap


def prepare(context):
    # Refuse to stack a second driver or either older same-topic watchdog.
    result = subprocess.run(['ros2', 'node', 'list'], capture_output=True,
                            text=True, timeout=10, check=True)
    names = {line.strip().rsplit('/', 1)[-1] for line in result.stdout.splitlines()}
    blocked = names & {'wheeltec_robot', 'cmd_vel_watchdog', 'cmd_vel_gate'}
    if blocked:
        raise RuntimeError('Stop existing driver/watchdog first: %s' % sorted(blocked))
    gate_path = Path(__file__).resolve().with_name('cmd_vel_gate.py')
    if not gate_path.is_file():
        raise RuntimeError('Missing sibling cmd_vel_gate.py')
    # Fail before starting the driver if this board's ROS Python API is incompatible.
    subprocess.run([sys.executable, str(gate_path), '--check-imports'],
                   timeout=10, check=True)
    launch_path = os.path.join(get_package_share_directory('turn_on_wheeltec_robot'),
                               'launch', 'base_serial.launch.py')
    gate = ExecuteProcess(cmd=[sys.executable, '-u', str(gate_path)], output='screen')
    driver = GroupAction(actions=[
        SetRemap(src='/cmd_vel', dst='/cmd_vel_safe'),
        # Keep other inspected vendor motion inputs away from default topic names.
        SetRemap(src='/red_vel', dst='/d3_unused/red_vel'),
        SetRemap(src='/robot_recharge_flag', dst='/d3_unused/robot_recharge_flag'),
        SetRemap(src='/set_charge', dst='/d3_unused/set_charge'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(launch_path)),
    ])
    notice = RegisterEventHandler(OnProcessExit(target_action=gate, on_exit=[
        LogInfo(msg='GATE EXITED. USE PHYSICAL MOTOR STOP. Do not continue tests. '
                    'A crashed gate/driver cannot replace MCU timeout protection.')]))
    return [LogInfo(msg='D3 BENCH ONLY: wheels lifted; starts DISARMED; no auto restart.'),
            notice, gate, driver]


def generate_launch_description():
    return LaunchDescription([OpaqueFunction(function=prepare)])
