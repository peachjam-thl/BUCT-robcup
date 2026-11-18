"""Offline control-flow checks; no ROS imports or robot connection."""
import contextlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / 'tools' / 'base_forward_probe.py'
spec = importlib.util.spec_from_file_location('probe_under_check', path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Message:
    def __init__(self):
        self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)


def scenario(stop_at=None, loss_at=None, competing_at=None, no_feedback=False,
             duration=1.0, zero_feedback=False, axis='x', speed=0.03,
             check_silence_stop=False, device_timeout=None, expect_notice=None,
             silence_window=1.5, log_path=None, ask=None, record=None,
             confirm_wheel_stop=False, allow_watchdog=False, publishers=None):
    clock = SimpleNamespace(value=0.0)
    sent = []
    axis_index = {'x': 0, 'y': 1, 'yaw': 2}[axis]

    class Publisher:
        def get_subscription_count(self):
            return 1

        def publish(self, msg):
            values = (msg.linear.x, msg.linear.y, msg.angular.z)
            assert msg.linear.z == msg.angular.x == msg.angular.y == 0
            assert all(v == 0 for i, v in enumerate(values) if i != axis_index)
            assert abs(values[axis_index]) <= (0.15 if axis == 'yaw' else 0.05)
            sent.append((clock.value, values[axis_index]))

    class Node:
        last_odom_time = None
        last_twist = None
        pub = Publisher()

        def count_publishers(self, topic):
            if publishers is not None:
                return len(publishers)
            return 2 if competing_at is not None and clock.value >= competing_at else 1

    if publishers is not None:
        # Exercise the name-aware publisher check used with a live watchdog.
        def get_name(self):
            return 'base_forward_probe'

        def get_publishers_info_by_topic(self, topic):
            return [SimpleNamespace(node_name=name) for name in publishers]

        Node.get_name = get_name
        Node.get_publishers_info_by_topic = get_publishers_info_by_topic

    class Ros:
        @staticmethod
        def ok():
            return True

        @staticmethod
        def spin_once(node, timeout_sec):
            clock.value += max(timeout_sec, 0.001)
            if not no_feedback and (loss_at is None or clock.value < loss_at):
                node.last_odom_time = clock.value
                values = [0.0, 0.0, 0.0]
                values[axis_index] = sent[-1][1] if sent and not zero_feedback else 0.0
                if (device_timeout is not None and sent
                        and clock.value - sent[-1][0] >= device_timeout):
                    values[axis_index] = 0.0
                node.last_twist = tuple(values)

    def wrapped_ask(question):
        # A prompt must never come before the zero fallback, or answering it
        # would leave the wheels spinning.
        assert sent and sent[-1][1] == 0.0, 'operator prompt before zero fallback'
        return ask(question) if ask is not None else 'unobserved'

    error = None
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        try:
            probe.exercise(Node(), Ros, Message,
                           lambda: stop_at is not None and clock.value >= stop_at,
                           speed, duration, lambda: clock.value, axis=axis,
                           check_silence_stop=check_silence_stop,
                           silence_window=silence_window, log_path=log_path,
                           ask=wrapped_ask, record=record,
                           confirm_wheel_stop=confirm_wheel_stop,
                           allow_watchdog=allow_watchdog)
        except (RuntimeError, InterruptedError) as exc:
            error = exc
    assert sent and sent[-1][1] == 0.0
    motion = [(t, v) for t, v in sent if v]
    if motion:
        last_motion = max(i for i, (_, v) in enumerate(sent) if v)
        assert all(v == 0 for _, v in sent[last_motion + 1:])
        assert sent[-1][0] - sent[last_motion][0] >= 1.9
        assert motion[-1][0] - motion[0][0] <= duration
    if zero_feedback:
        assert 'no nonzero odometry observed' in captured.getvalue()
    if expect_notice:
        observed_output = captured.getvalue() + str(error or '')
        assert expect_notice in observed_output, observed_output
    if check_silence_stop and motion and expect_notice in (
            'SILENCE_STOP_OBSERVED', 'SILENCE_STOP_NOT_OBSERVED'):
        gap = sent[last_motion + 1][0] - sent[last_motion][0]
        if expect_notice == 'SILENCE_STOP_OBSERVED':
            assert device_timeout + 0.19 <= gap <= device_timeout + 0.32, gap
        else:
            assert silence_window - 0.02 <= gap <= silence_window + 0.06, gap
    return motion, error


motion, error = scenario()
assert error is None and motion
assert motion[-1][0] - motion[0][0] >= 0.90
motion, error = scenario(duration=3.0)
assert error is None and motion
assert motion[-1][0] - motion[0][0] >= 2.90
for axis in ('y', 'yaw'):
    motion, error = scenario(duration=3.0, axis=axis)
    assert error is None and motion
    assert motion[-1][0] - motion[0][0] >= 2.90
    motion, error = scenario(zero_feedback=True, axis=axis)
    assert error is None and motion
    motion, error = scenario(stop_at=1.25, axis=axis)
    assert motion and isinstance(error, InterruptedError)
motion, error = scenario(zero_feedback=True)
assert error is None and motion
motion, error = scenario(stop_at=1.25)
assert motion and isinstance(error, InterruptedError)
assert motion[-1][0] < 1.25
motion, error = scenario(loss_at=1.20)
assert motion and isinstance(error, RuntimeError)
assert motion[-1][0] < 1.60
motion, error = scenario(competing_at=1.25)
assert motion and isinstance(error, RuntimeError)
assert motion[-1][0] < 1.25

# The host watchdog is the only extra publisher a run may accept.
motion, error = scenario(competing_at=0.0)
assert isinstance(error, RuntimeError)
motion, error = scenario(competing_at=0.0, allow_watchdog=True)
assert motion and error is None
motion, error = scenario(publishers=['base_forward_probe', 'cmd_vel_watchdog'],
                         allow_watchdog=True)
assert motion and error is None
motion, error = scenario(publishers=['base_forward_probe', 'cmd_vel_watchdog'])
assert isinstance(error, RuntimeError)
motion, error = scenario(publishers=['base_forward_probe', 'teleop_twist'],
                         allow_watchdog=True)
assert isinstance(error, RuntimeError)
motion, error = scenario(no_feedback=True)
assert not motion and isinstance(error, RuntimeError)

# Silence observation: succeeds, fails within the window, invalid baseline.
motion, error = scenario(check_silence_stop=True, device_timeout=0.30,
                         expect_notice='SILENCE_STOP_OBSERVED')
assert motion and error is None
motion, error = scenario(check_silence_stop=True, expect_notice='SILENCE_STOP_NOT_OBSERVED')
assert motion and isinstance(error, RuntimeError)
motion, error = scenario(check_silence_stop=True, zero_feedback=True,
                         expect_notice='SILENCE_CHECK_INVALID')
assert motion and isinstance(error, RuntimeError)
motion, error = scenario(check_silence_stop=True, stop_at=2.25)
assert motion and isinstance(error, InterruptedError)
motion, error = scenario(check_silence_stop=True, loss_at=2.10)
assert motion and isinstance(error, RuntimeError)
motion, error = scenario(check_silence_stop=True, competing_at=2.20)
assert motion and isinstance(error, RuntimeError)

# Silence observation now also covers lateral and yaw commands.
motion, error = scenario(axis='y', speed=0.05, check_silence_stop=True,
                         device_timeout=0.30, expect_notice='SILENCE_STOP_OBSERVED')
assert motion and error is None
motion, error = scenario(axis='yaw', speed=0.15, check_silence_stop=True,
                         device_timeout=0.30, expect_notice='SILENCE_STOP_OBSERVED')
assert motion and error is None
motion, error = scenario(axis='yaw', speed=0.03, check_silence_stop=True,
                         expect_notice='SILENCE_CHECK_INVALID')
assert motion and isinstance(error, RuntimeError)

# A longer observation window can reveal a slower device timeout.
motion, error = scenario(check_silence_stop=True, silence_window=3.0,
                         expect_notice='SILENCE_STOP_NOT_OBSERVED')
assert motion and isinstance(error, RuntimeError)
motion, error = scenario(check_silence_stop=True, silence_window=3.0,
                         device_timeout=2.20, expect_notice='SILENCE_STOP_OBSERVED')
assert motion and error is None

# Operator answers are recorded and survive an aborted run.
record = {}
motion, error = scenario(check_silence_stop=True, device_timeout=0.30,
                         expect_notice='SILENCE_STOP_OBSERVED', record=record,
                         ask=lambda question: 'yes')
assert motion and error is None
assert record['operator_silence_stop'] == 'yes'
assert record['silence_outcome'] == 'silence_stop_observed'
assert record['silence_stop_at'] < 0.60
assert record['zero_fallback'] is True
record = {}
motion, error = scenario(check_silence_stop=True, expect_notice='SILENCE_STOP_NOT_OBSERVED',
                         record=record, ask=lambda question: 'no')
assert isinstance(error, RuntimeError)
assert record['operator_silence_stop'] == 'no'
assert 'silence_stop_not_observed' in record['silence_outcome']
record = {}
motion, error = scenario(record=record)
assert 'operator_silence_stop' not in record
# An invalid baseline never starts the silence window, so it must not ask.
record = {}
motion, error = scenario(check_silence_stop=True, zero_feedback=True,
                         expect_notice='SILENCE_CHECK_INVALID', record=record,
                         ask=lambda question: 'yes')
assert isinstance(error, RuntimeError)
assert 'operator_silence_stop' not in record and 'silence_started' not in record

# Wheel-stop confirmation is asked after the fallback, and skipped on Ctrl+C.
record = {}
motion, error = scenario(confirm_wheel_stop=True, record=record,
                         ask=lambda question: 'yes')
assert motion and error is None
assert record['operator_wheel_stop'] == 'yes'
assert 'operator_silence_stop' not in record
record = {}
motion, error = scenario(stop_at=1.25, confirm_wheel_stop=True, record=record,
                         ask=lambda question: 'yes')
assert isinstance(error, InterruptedError)
assert 'operator_wheel_stop' not in record
record = {}
motion, error = scenario(check_silence_stop=True, device_timeout=0.30,
                         expect_notice='SILENCE_STOP_OBSERVED', confirm_wheel_stop=True,
                         record=record, ask=lambda question: 'yes')
assert record['operator_silence_stop'] == 'yes'
assert record['operator_wheel_stop'] == 'yes'

# CSV logging captures the phases and the feedback used for the decision.
# A fixed path keeps the check runnable under a confined workspace; no temp dirs.
csv_path = Path(__file__).resolve().with_name('probe-test-output.csv')
try:
    motion, error = scenario(check_silence_stop=True, device_timeout=0.30,
                             expect_notice='SILENCE_STOP_OBSERVED', log_path=str(csv_path))
    assert motion and error is None
    rows = csv_path.read_text(encoding='utf-8').strip().splitlines()
    assert rows[0] == 't_s,phase,command,odom_vx,odom_vy,odom_wz'
    phases = {line.split(',')[1] for line in rows[1:]}
    assert {'zero_before:start', 'motion', 'motion:end', 'silence:start'} <= phases
    assert 'zero_after' in phases
    assert len(rows) > 10
finally:
    csv_path.unlink(missing_ok=True)

# Evidence block can be pasted into a log and marks unobserved items.
block = probe.evidence_block(record)
assert '## base_forward_probe 证据' in block
assert 'unobserved' in block or '未记录' in block
assert '不能作为“已确认”的证据' in block
partial = probe.evidence_block({'axis': 'yaw', 'speed': 0.15, 'duration': 3.0,
                                'silence_window': 1.5})
assert 'yaw' in partial and '未记录' in partial

for arguments in (['--speed', 'nan'], ['--speed', '0.06'], ['--speed', '-0.01'],
                  ['--duration', 'inf'], ['--duration', '3.1'], ['--duration', '0'],
                  ['--axis', 'yaw', '--speed', '0.16'],
                  ['--silence-window', '0.4'], ['--silence-window', '5.1'],
                  ['--silence-window', 'nan']):
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            probe.arguments(arguments)
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError('invalid bound accepted')
assert probe.arguments([]).duration == 1.0
assert probe.arguments(['--duration', '3']).duration == 3.0
assert probe.arguments([]).axis == 'x'
assert probe.arguments(['--axis', 'y', '--speed', '0.05']).speed == 0.05
assert probe.arguments(['--axis', 'yaw', '--speed', '0.15']).speed == 0.15
assert not probe.arguments([]).check_silence_stop
assert probe.arguments([]).silence_window == 1.5
assert probe.arguments(['--silence-window', '0.5']).silence_window == 0.5
assert probe.arguments(['--silence-window', '5']).silence_window == 5.0
print('PASS: bounded x/y/yaw, zero-odometry warning, Ctrl+C-equivalent stop, '
      'feedback loss, competing publisher, no feedback, 10 invalid arguments, '
      'silence-stop success/failure/invalid baseline/interruption/stale feedback/competition, '
      'lateral and yaw silence observations, 3 s window, operator answers after the zero '
      'fallback, wheel-stop confirmation, CSV phases, and evidence block. '
      'Default duration remains 1s. No ROS or robot used.')
