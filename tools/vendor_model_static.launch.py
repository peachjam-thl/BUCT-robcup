"""Static model inspection only: read installed vendor values, never start motors."""
import ast
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


def assignment(tree, name):
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == 'generate_launch_description']
    if len(functions) != 1:
        raise ValueError('Expected one vendor generate_launch_description')
    values = [n.value for n in functions[0].body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    if len(values) != 1:
        raise ValueError('Vendor assignment missing or ambiguous: ' + name)
    return values[0]


def keyword(call, name):
    if not isinstance(call, ast.Call):
        raise ValueError('Expected vendor call for ' + name)
    values = [k.value for k in call.keywords if k.arg == name]
    if len(values) != 1:
        raise ValueError('Vendor keyword missing or ambiguous: ' + name)
    return values[0]


def transform(values):
    if len(values) != 8 or not all(isinstance(v, str) for v in values):
        raise ValueError('Expected six numeric strings and two frame names')
    if not all(math.isfinite(float(v)) for v in values[:6]):
        raise ValueError('Non-finite vendor transform')
    if not all(v.strip() for v in values[6:]):
        raise ValueError('Empty vendor frame name')
    return values


def load_vendor_config(bringup_share, urdf_share):
    """Read literals/XML only. Do not import or execute the vendor launch files."""
    launch_dir = Path(bringup_share) / 'launch'
    main_path = launch_dir / 'turn_on_wheeltec_robot.launch.py'
    model_path = launch_dir / 'robot_mode_description_minibot.launch.py'
    main = ast.parse(main_path.read_text(encoding='utf-8-sig'))
    model = ast.parse(model_path.read_text(encoding='utf-8-sig'))
    selector = keyword(assignment(main, 'minibot_type'), 'launch_arguments')
    if not (isinstance(selector, ast.Call) and isinstance(selector.func, ast.Attribute)
            and selector.func.attr == 'items'
            and ast.literal_eval(selector.func.value) == {'mini_mec': 'true'}):
        raise ValueError('Installed vendor model is not the inspected mini_mec selection')
    base = transform(ast.literal_eval(keyword(assignment(main, 'base_to_link'), 'arguments')))
    actions = keyword(assignment(model, 'mini_mec_'), 'actions')
    if not isinstance(actions, ast.List):
        raise ValueError('Unsupported vendor model action list')
    robot_files, statics = [], []
    for action in actions.elts:
        if not isinstance(action, ast.Call) or not isinstance(action.func, ast.Name):
            raise ValueError('Unsupported vendor model action')
        args = [ast.literal_eval(arg) for arg in action.args]
        if action.func.id == 'generate_robot_node':
            robot_files.append(args[0])
        elif action.func.id == 'generate_static_transform_publisher_node':
            if len(args) != 4:
                raise ValueError('Unsupported vendor transform helper')
            statics.append(transform(args[0] + args[1] + args[2:]))
        else:
            raise ValueError('Unexpected vendor helper: ' + action.func.id)
    if robot_files != ['mini_mec_robot.urdf']:
        raise ValueError('Unexpected vendor URDF selection')
    urdf_path = Path(urdf_share) / 'urdf' / robot_files[0]
    xml = urdf_path.read_text(encoding='utf-8-sig')
    robot = ET.fromstring(xml)
    links = {n.attrib['name'] for n in robot.findall('link')}
    parents = {}
    for joint in robot.findall('joint'):
        parent, child = joint.find('parent').attrib['link'], joint.find('child').attrib['link']
        if parent not in links or child not in links or child in parents:
            raise ValueError('Invalid or repeated URDF child frame: ' + child)
        parents[child] = parent
    if base[6:] != ['base_footprint', 'base_link'] or 'base_link' in parents:
        raise ValueError('Unexpected vendor base connection')
    lasers = [v for v in statics if v[7] == 'laser']
    if len(lasers) != 1 or lasers[0][6] != 'base_footprint':
        raise ValueError('Expected one vendor base_footprint -> laser transform')
    # URDF owns camera_link and laser_link; the distinct scan frame is laser.
    if parents.get('camera_link') != 'base_link':
        raise ValueError('Expected inspected URDF camera_link ownership')
    for values in (base, lasers[0]):
        if values[7] in parents:
            raise ValueError('Duplicate TF child: ' + values[7])
        parents[values[7]] = values[6]
    for child in parents:
        seen = set()
        cursor = child
        while cursor in parents:
            if cursor in seen:
                raise ValueError('Cycle in TF tree')
            seen.add(cursor)
            cursor = parents[cursor]
        if cursor != 'base_footprint':
            raise ValueError('Disconnected vendor TF root: ' + cursor)
    return {'xml': xml, 'urdf_path': urdf_path, 'base': base, 'laser': lasers[0],
            'sources': [main_path, model_path, urdf_path]}


def ensure_no_static_publishers():
    result = subprocess.run(['ros2', 'topic', 'info', '/tf_static'],
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    match = re.search(r'Publisher count:\s*(\d+)', output)
    if match is not None and result.returncode == 0:
        if int(match.group(1)) != 0:
            raise RuntimeError('Existing /tf_static publishers: inspect and stop duplicate model TF first')
    elif 'Unknown topic' not in output:
        raise RuntimeError('Cannot inspect /tf_static publishers: ' + output.strip())


def generate_launch_description():
    from ament_index_python.packages import get_package_share_directory
    from launch import LaunchDescription
    from launch.actions import LogInfo
    from launch_ros.actions import Node
    from launch_ros.parameter_descriptions import ParameterValue

    config = load_vendor_config(get_package_share_directory('turn_on_wheeltec_robot'),
                                get_package_share_directory('wheeltec_robot_urdf'))
    # Static bench preflight only; discovery is not atomic. Check the live graph too.
    ensure_no_static_publishers()
    description = ParameterValue(config['xml'], value_type=str)
    return LaunchDescription([
        LogInfo(msg='STATIC MODEL ONLY: installed vendor values; no base driver, lidar, odom or SLAM.'),
        LogInfo(msg='URDF: ' + str(config['urdf_path'])),
        LogInfo(msg='Vendor base TF: ' + ' '.join(config['base'])),
        LogInfo(msg='Vendor scan TF: ' + ' '.join(config['laser'])),
        LogInfo(msg='camera_link and laser_link are owned by the unmodified URDF; scan frame laser is distinct.'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name='vendor_static_robot_state_publisher', output='screen',
             parameters=[{'robot_description': description}]),
        # Display-only default wheel joint angles; these are not encoder measurements.
        Node(package='joint_state_publisher', executable='joint_state_publisher',
             name='vendor_static_joint_state_publisher', output='screen'),
        Node(package='tf2_ros', executable='static_transform_publisher',
             name='vendor_static_base_to_link', arguments=config['base'], output='screen'),
        Node(package='tf2_ros', executable='static_transform_publisher',
             name='vendor_static_base_to_laser', arguments=config['laser'], output='screen'),
    ])
