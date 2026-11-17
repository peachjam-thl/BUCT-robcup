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
             duration=1.0, zero_feedback=False, axis='x', check_silence_stop=False,
             device_timeout=None, expect_notice=None):
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
            return 2 if competing_at is not None and clock.value >= competing_at else 1

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

    error = None
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        try:
            probe.exercise(Node(), Ros, Message,
                           lambda: stop_at is not None and clock.value >= stop_at,
                           0.03, duration, lambda: clock.value, axis=axis,
                           check_silence_stop=check_silence_stop)
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
            assert device_timeout + 0.19 <= gap < device_timeout + 0.30
        else:
            assert 1.49 <= gap <= 1.53
    return motion, error


motion, error = scenario()
assert error is None and motion
assert motion[-1][0] - motion[0][0] >= 0.90
motion, error = scenario(duration=3.0)
assert error is None and motion[-1][0] - motion[0][0] >= 2.90
for axis in ('y', 'yaw'):
    motion, error = scenario(duration=3.0, axis=axis)
    assert error is None and motion[-1][0] - motion[0][0] >= 2.90
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
motion, error = scenario(no_feedback=True)
assert not motion and isinstance(error, RuntimeError)
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
for arguments in (['--speed', 'nan'], ['--speed', '0.06'], ['--speed', '-0.01'],
                  ['--duration', 'inf'], ['--duration', '3.1'], ['--duration', '0'],
                  ['--axis', 'yaw', '--speed', '0.16'],
                  ['--axis', 'y', '--check-silence-stop']):
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
print('PASS: bounded x/y/yaw, zero-odometry warning, Ctrl+C-equivalent stop, '
      'feedback loss, competing publisher, no feedback, 8 invalid arguments, '
      'and silence-stop success/failure/invalid baseline/interruption/stale feedback/competition. '
      'Default duration remains 1s. No ROS or robot used.')
