"""Offline source-extraction / TF ownership regression; no ROS or hardware."""
import importlib.util
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'tools' / 'vendor_model_static.launch.py'
spec = importlib.util.spec_from_file_location('vendor_model_static', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

main = '''def generate_launch_description():
    minibot_type = IncludeLaunchDescription(source, launch_arguments={'mini_mec': 'true'}.items())
    base_to_link = Node(arguments=['0','0','0','0','0','0','base_footprint','base_link'])
'''
model = '''def generate_launch_description():
    mini_mec_ = GroupAction(actions=[
        generate_robot_node('mini_mec_robot.urdf','mini_mec'),
        generate_static_transform_publisher_node(['0.03163','0.00009','0.09502'],['0','0','0'],'base_footprint','laser'),
        generate_static_transform_publisher_node(['0.10709','0.00032','0.0762'],['0','0','0'],'base_footprint','camera_link')])
'''
xml = '''<robot name="mini_mec_robot">
<link name="base_link"/><link name="camera_link"/><link name="laser_link"/>
<joint name="camera_joint" type="fixed"><parent link="base_link"/><child link="camera_link"/>
<origin xyz="0.10709468678297 0.000317092708037946 0.076204" rpy="0 0 0"/></joint>
<joint name="laser_joint" type="fixed"><parent link="base_link"/><child link="laser_link"/>
<origin xyz="0.0316310367407428 0.0000905810809802502 0.095024183741431" rpy="0 0 3.14159265358979"/></joint>
</robot>'''

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    launch = root / 'launch'
    urdf = root / 'urdf'
    launch.mkdir()
    urdf.mkdir()
    main_path = launch / 'turn_on_wheeltec_robot.launch.py'
    model_path = launch / 'robot_mode_description_minibot.launch.py'
    urdf_path = urdf / 'mini_mec_robot.urdf'

    def write(main_text=main, model_text=model, xml_text=xml):
        main_path.write_text(main_text, encoding='utf-8')
        model_path.write_text(model_text, encoding='utf-8')
        urdf_path.write_text(xml_text, encoding='utf-8')

    def reject(**kwargs):
        write(**kwargs)
        try:
            module.load_vendor_config(root, root)
        except ValueError:
            return
        raise AssertionError('Malformed/conflicting vendor configuration accepted')

    write()
    config = module.load_vendor_config(root, root)
    assert config['laser'] == ['0.03163','0.00009','0.09502','0','0','0','base_footprint','laser']
    assert config['xml'] == xml and '3.14159265358979' in config['xml']
    assert config['base'] == ['0','0','0','0','0','0','base_footprint','base_link']
    # Configuration edits are read afresh, rather than hidden behind hard-coded offsets.
    write(model_text=model.replace('0.03163', '0.04163'))
    assert module.load_vendor_config(root, root)['laser'][0] == '0.04163'
    reject(main_text=main.replace("'mini_mec': 'true'", "'mini_akm': 'true'"))
    reject(model_text=model.replace('0.09502', 'nan'))
    reject(xml_text=xml.replace('name="laser_link"', 'name="laser"').replace('link="laser_link"', 'link="laser"'))
    reject(xml_text=xml.replace('link="camera_link"', 'link="base_link"'))
    reject(xml_text=xml.replace('link="base_link"', 'link="unknown_parent"', 1))

    # Verify the public launch path can create only the four display/TF nodes.
    write()
    modules = {}
    def stub(name, **members):
        mod = ModuleType(name)
        mod.__path__ = []
        mod.__dict__.update(members)
        modules[name] = mod
    stub('ament_index_python')
    stub('ament_index_python.packages', get_package_share_directory=lambda package: str(root))
    stub('launch', LaunchDescription=lambda actions: actions)
    stub('launch.actions', LogInfo=lambda **kwargs: ('log', kwargs))
    stub('launch_ros')
    stub('launch_ros.actions', Node=lambda **kwargs: ('node', kwargs))
    stub('launch_ros.parameter_descriptions', ParameterValue=lambda value, **kwargs: value)
    with patch.dict('sys.modules', modules), patch.object(module, 'subprocess') as process:
        process.run.return_value = SimpleNamespace(returncode=0, stdout='Publisher count: 0', stderr='')
        actions = module.generate_launch_description()
        nodes = [action[1] for action in actions if action[0] == 'node']
        assert [n['package'] for n in nodes] == ['robot_state_publisher', 'joint_state_publisher', 'tf2_ros', 'tf2_ros']
        assert nodes[0]['parameters'][0]['robot_description'] == xml
        assert nodes[2]['arguments'] == config['base']
        assert nodes[3]['arguments'] == config['laser']
        for returncode, output, allowed in ((0, 'Publisher count: 2', False),
                                            (1, "Unknown topic '/tf_static'", True),
                                            (1, 'ROS daemon failed', False)):
            process.run.return_value = SimpleNamespace(returncode=returncode, stdout=output, stderr='')
            try:
                module.ensure_no_static_publishers()
            except RuntimeError:
                assert not allowed
            else:
                assert allowed
print('PASS: installed-source literals, unchanged URDF and scan-frame rotation, source edits, '
      'duplicate/missing parents, model mismatch, non-finite transforms, publisher preflight '
      'and display-only launch node allowlist. Offline only.')
