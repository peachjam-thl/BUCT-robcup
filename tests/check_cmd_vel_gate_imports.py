"""Import-only preflight regression with a strict Humble-shaped module surface.

This tests the no-node/no-motion branch, not the availability of ROS on a board.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'tools' / 'cmd_vel_gate.py'
spec = importlib.util.spec_from_file_location('gate_import_check', path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

modules = {}
def module(name, **values):
    result = ModuleType(name)
    result.__path__ = []
    result.__dict__.update(values)
    modules[name] = result
    return result

def forbidden(*args, **kwargs):
    raise AssertionError('import preflight must not initialize ROS or construct nodes')

module('rclpy', init=forbidden)
module('rclpy.clock', Clock=forbidden,
       ClockType=SimpleNamespace(STEADY_TIME='STEADY_TIME'))
module('rclpy.node', Node=forbidden)
module('rclpy.signals', SignalHandlerOptions=SimpleNamespace(NO=0))
for package, member, name in [('geometry_msgs', 'msg', 'Twist'),
                              ('nav_msgs', 'msg', 'Odometry'),
                              ('std_msgs', 'msg', 'String'),
                              ('std_srvs', 'srv', 'Trigger')]:
    module(package)
    module(package + '.' + member, **{name: forbidden})

captured = io.StringIO()
with patch.dict(sys.modules, modules), contextlib.redirect_stdout(captured):
    assert gate.main(['--check-imports']) == 0
assert 'ROS imports OK' in captured.getvalue()
print('PASS: Humble clock import surface; import-only preflight creates no ROS node. '
      'Board runtime still needs validation.')
