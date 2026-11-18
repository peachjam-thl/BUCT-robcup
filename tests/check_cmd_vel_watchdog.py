"""Offline checks for the /cmd_vel watchdog decision logic; no ROS import."""
import contextlib
import importlib.util
import io
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'tools' / 'cmd_vel_watchdog.py'
spec = importlib.util.spec_from_file_location('watchdog_under_check', path)
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)

# Startup: no command yet means hold zero, but say so only once.
logic = watchdog.WatchdogLogic(0.4)
assert logic.tick(0.0) == (True, 'startup')
assert logic.tick(0.01) == (True, None)
assert logic.stopping is True

# A moving command releases the hold and forbids zeros while it keeps arriving.
logic.command(1.0, True)
assert logic.stopping is False
assert logic.tick(1.05) == (False, None)
assert logic.tick(1.39) == (False, None)
assert logic.tick(1.41) == (True, 'silence')
assert logic.stopping is True

# While silent, zeros keep being refreshed but the event is not repeated.
assert logic.tick(1.45) == (True, None)
assert logic.tick(1.90) == (True, None)

# Zero-only traffic counts as activity but does not release the stop.
logic.command(2.0, False)
assert logic.stopping is True
assert logic.tick(2.39) == (False, None)
assert logic.tick(2.41) == (True, None)

# The next moving command releases again and a later gap is reported again.
logic.command(3.0, True)
assert logic.stopping is False
assert logic.tick(3.10) == (False, None)
assert logic.tick(3.41) == (True, 'silence')

# Exact boundary is inclusive, and a shorter timeout trips earlier.
logic = watchdog.WatchdogLogic(0.3)
logic.command(0.0, True)
assert logic.tick(0.299) == (False, None)
assert logic.tick(0.300) == (True, 'silence')

# Arguments: bounds, defaults and the topic switch.
for arguments in (['--timeout', '0.05'], ['--timeout', '2.1'], ['--timeout', 'nan'],
                  ['--rate', '4'], ['--rate', '51'], ['--rate', 'inf']):
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            watchdog.arguments(arguments)
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError('invalid bound accepted')
assert watchdog.arguments([]).timeout == 0.4
assert watchdog.arguments([]).rate == 20.0
assert watchdog.arguments([]).topic == '/cmd_vel'
assert watchdog.arguments(['--timeout', '0.1']).timeout == 0.1
assert watchdog.arguments(['--timeout', '2']).timeout == 2.0
assert watchdog.arguments(['--rate', '5']).rate == 5.0
assert watchdog.arguments(['--rate', '50']).rate == 50.0
assert watchdog.arguments(['--topic', '/cmd_vel_raw']).topic == '/cmd_vel_raw'

print('PASS: watchdog startup hold, single stop event, zero refresh while silent, '
      'release only on moving commands, re-trip after release, inclusive boundary, '
      'short timeout, and 6 invalid arguments. No ROS or robot used.')
