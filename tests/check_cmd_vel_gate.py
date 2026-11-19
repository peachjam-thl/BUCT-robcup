"""Offline D3 gate fault/rearm checks. Does not import ROS or command hardware."""
import contextlib
import importlib.util
import io
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'tools' / 'cmd_vel_gate.py'
spec = importlib.util.spec_from_file_location('gate_under_test', path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
ZERO = gate.ZERO
FORWARD = (0.05, 0.0, 0.0, 0.0, 0.0, 0.0)


def ready():
    logic = gate.GateLogic()
    logic.feedback(0.0, (1, 1), (0.0, 0.0, 0.0))
    assert logic.arm(0.0) == (True, 'WAITING_FOR_NEW_REQUEST')
    return logic


# Startup and request traffic never arm the robot implicitly.
logic = gate.GateLogic()
for i in range(100):
    assert logic.request(i * 0.05, FORWARD) == ZERO
    assert logic.tick(i * 0.05) == ZERO
assert not logic.armed and logic.last_request is None
assert not logic.arm(5.0)[0]

# Armed idle holds zero while awaiting a *new* controller, not an old velocity.
logic = ready()
for i in range(20):
    now = (i + 1) * 0.05
    logic.feedback(now, (1, i + 2), (0.0, 0.0, 0.0))
    assert logic.tick(now) == ZERO
assert logic.armed

# Valid x/y/yaw forward; timer never generates nonzero motion.
for command in (FORWARD, (0.0, -0.05, 0.0, 0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 0.0, 0.0, -0.15)):
    logic = ready()
    assert logic.request(0.0, command) == command
    assert logic.tick(0.10) is None
    logic.feedback(0.4, (1, 100), (0.04, 0.0, 0.0))
    assert logic.tick(0.4) == ZERO
    assert logic.reason == 'COMMAND_TIMEOUT' and not logic.armed
    # Subsequent commands cannot automatically clear a latched fault.
    assert logic.request(0.41, command) == ZERO
    assert not logic.armed

# A request arriving after a missed timer deadline cannot evade the timeout.
logic = ready()
logic.request(0.0, FORWARD)
logic.feedback(0.5, (1, 200), (0.0, 0.0, 0.0))
assert logic.request(0.5, FORWARD) == ZERO and logic.reason == 'COMMAND_TIMEOUT'
assert logic.arm(0.51)[0]
assert logic.tick(0.52) == ZERO
assert logic.request(0.53, FORWARD) == FORWARD

# Every disarmed timer tick emits zero; output never refreshes input time.
logic.stop('OPERATOR_DISARM')
zeros = [logic.tick(1.0 + i * 0.05) for i in range(40)]
assert zeros == [ZERO] * 40 and logic.last_request is None

# Feedback freezes, reversals, NaN, and graph failures latch stop.
logic = ready()
logic.request(0.0, FORWARD)
logic.feedback(0.30, (1, 1), (0.0, 0.0, 0.0))
assert logic.last_feedback == 0.0
assert logic.tick(0.36) == ZERO and logic.reason == 'ODOMETRY_STALE'
for key, velocity, reason in (((0, 1), (0.0, 0.0, 0.0), 'ODOMETRY_TIME_REVERSED'),
                              ((1, 2), (float('nan'), 0.0, 0.0), 'INVALID_ODOMETRY')):
    logic = ready()
    logic.feedback(0.10, key, velocity)
    assert not logic.armed and logic.reason == reason
    assert not logic.arm(0.11)[0]

for error in ('OUTPUT_PUBLISHER_CONFLICT', 'EXPECTED_DRIVER_MISSING_OR_DUPLICATE',
              'DRIVER_BYPASSES_GATE', 'MULTIPLE_COMMAND_SOURCES',
              'ODOMETRY_SOURCE_MISSING_OR_DUPLICATE', 'ODOMETRY_FRAME_MISMATCH_OR_MISSING',
              'STOP_COMMAND_SOURCE_BEFORE_ARM'):
    logic = ready()
    assert not logic.arm(0.0, error)[0]
    logic = ready()
    assert logic.request(0.05, FORWARD, error) == ZERO
    assert not logic.armed and logic.reason == error
    logic = ready()
    assert logic.tick(0.05, error) == ZERO and not logic.armed

for velocity in ((0.011, 0.0, 0.0), (0.0, 0.011, 0.0), (0.0, 0.0, 0.041)):
    logic = ready()
    logic.feedback(0.05, (1, 2), velocity)
    assert not logic.arm(0.05)[0] and logic.reason == 'ODOMETRY_NOT_STATIONARY'

for command, reason in (((float('nan'), 0, 0, 0, 0, 0), 'INVALID_COMMAND'),
                        ((0, 0, float('inf'), 0, 0, 0), 'INVALID_COMMAND'),
                        ((0, 0, 0.01, 0, 0, 0), 'UNSUPPORTED_AXIS'),
                        ((0, 0, 0, 0.01, 0, 0), 'UNSUPPORTED_AXIS'),
                        ((0.05, 0.05, 0, 0, 0, 0), 'SPEED_LIMIT'),
                        ((0.051, 0, 0, 0, 0, 0), 'SPEED_LIMIT'),
                        ((0, 0, 0, 0, 0, 0.151), 'SPEED_LIMIT')):
    logic = ready()
    assert logic.request(0.05, command) == ZERO and logic.reason == reason

for argv in (['--input-topic', '/cmd_vel_safe'], ['--input-topic', 'relative'],
             ['--odom-topic', '/cmd_vel'], ['--timeout', 'nan'], ['--timeout', '0.01'],
             ['--rate', 'inf'], ['--feedback-timeout', '0.01']):
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            gate.arguments(argv)
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError('invalid input accepted')
args = gate.arguments([])
assert args.input_topic != args.output_topic
print('PASS: D3 startup/arm, no command replay, timeout latch/rearm, every-tick zeros, '
      'fresh odometry, clock reversal, graph faults, speed/axis/NaN rejection, CLI bounds. '
      'Offline only; ROS graph and physical stop remain untested.')
