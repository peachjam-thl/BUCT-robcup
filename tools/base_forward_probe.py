#!/usr/bin/env python3
"""Bounded wheels-lifted axis probe for the inspected WHEELTEC Twist driver.

Run in the robot's ROS2 Humble shell with the base_serial driver running.
No launch files or firmware are changed. This is NOT an independent MCU watchdog.
Physical wheel support and a reachable motor power switch are required.

Optional evidence helpers:
  --check-silence-stop   stop publishing, then observe up to --silence-window seconds
  --silence-window SEC   silence observation limit, 0.5 to 5.0 s (default 1.5)
  --confirm-wheel-stop   ask the operator whether the wheels are still afterwards
  --log-csv PATH         write commands and /odom feedback as a time series
  --evidence-out PATH    write the printed evidence block to a Markdown file
  --watchdog             allow exactly one extra /cmd_vel publisher, the host
                         watchdog node named cmd_vel_watchdog (for its retest)

The operator answers are part of the evidence: a scripted observation of /odom
cannot show that the four wheels physically stopped.
"""

import argparse
import csv
import math
import signal
import sys
import time
from datetime import datetime


def timestamp():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def ask_operator(question):
    """One short answer from a terminal; anything else counts as unobserved."""
    if not sys.stdin or not sys.stdin.isatty():
        print("%s -> unobserved (no interactive terminal)" % question, flush=True)
        return "unobserved"
    try:
        answer = input("%s [y/n] " % question).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("", flush=True)
        return "unobserved"
    if answer in ("y", "yes", "是"):
        return "yes"
    if answer in ("n", "no", "否"):
        return "no"
    return "unobserved"


class Recorder:
    """Optional CSV of every command and feedback sample used in the run."""

    def __init__(self, path):
        self.handle = None
        self.writer = None
        if path:
            self.handle = open(path, "w", newline="", encoding="utf-8")
            self.writer = csv.writer(self.handle)
            self.writer.writerow(
                ["t_s", "phase", "command", "odom_vx", "odom_vy", "odom_wz"])

    def record(self, t, phase, command, twist):
        if self.writer is None:
            return
        feedback = twist if twist is not None else ("", "", "")
        self.writer.writerow([round(t, 3), phase, round(command, 4)]
                             + [round(v, 4) for v in feedback])

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None
            self.writer = None


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=("x", "y", "yaw"), default="x",
                        help="positive x forward, y left, yaw counterclockwise")
    parser.add_argument("--speed", type=float, default=0.03,
                        help="positive m/s for x/y (max 0.05), rad/s for yaw (max 0.15)")
    parser.add_argument("--duration", type=float, default=1.0, help="seconds, >0 and <=3.0")
    parser.add_argument("--check-silence-stop", action="store_true",
                        help="after the motion phase, stop publishing and observe whether "
                             "motion stops before the zero fallback")
    parser.add_argument("--silence-window", type=float, default=1.5,
                        help="seconds of command silence to observe, 0.5 to 5.0 (default 1.5)")
    parser.add_argument("--log-csv", default=None,
                        help="write commands and /odom feedback to this CSV file")
    parser.add_argument("--evidence-out", default=None,
                        help="write the printed evidence block to this Markdown file")
    parser.add_argument("--confirm-wheel-stop", action="store_true",
                        help="after the zero fallback, ask whether the wheels are still")
    parser.add_argument("--watchdog", action="store_true",
                        help="allow exactly one extra /cmd_vel publisher named "
                             "cmd_vel_watchdog, so the host watchdog can be retested")
    args = parser.parse_args(argv)
    limit = 0.15 if args.axis == "yaw" else 0.05
    unit = "rad/s" if args.axis == "yaw" else "m/s"
    if not math.isfinite(args.speed) or not 0 < args.speed <= limit:
        parser.error("speed must be finite and in (0, %s] %s" % (limit, unit))
    if not math.isfinite(args.duration) or not 0 < args.duration <= 3.0:
        parser.error("duration must be finite and in (0, 3.0] seconds")
    if not math.isfinite(args.silence_window) or not 0.5 <= args.silence_window <= 5.0:
        parser.error("silence window must be finite and in [0.5, 5.0] seconds")
    return args


def other_publishers(node):
    """Names of /cmd_vel publishers other than this node, or None if unavailable."""
    getter = getattr(node, "get_publishers_info_by_topic", None)
    if getter is None:
        return None
    try:
        infos = getter("/cmd_vel")
    except Exception:
        return None
    own = node.get_name()
    return [info.node_name for info in infos if info.node_name != own]


def exercise(node, ros, twist_type, should_stop, speed, duration, now=time.monotonic,
             axis="x", check_silence_stop=False, silence_window=1.5,
             log_path=None, ask=None, record=None, confirm_wheel_stop=False,
             allow_watchdog=False):
    """Publish bounded commands; attempt zero before context destruction on every exit.

    Operator questions are asked only after the zero fallback, so answering them
    never delays the stop commands.
    """
    axis_index = {"x": 0, "y": 1, "yaw": 2}[axis]
    baseline_limits = {"x": 0.02, "y": 0.02, "yaw": 0.06}
    record = {} if record is None else record
    record.setdefault("started", timestamp())
    record["axis"] = axis
    record["speed"] = speed
    record["duration"] = duration
    record["silence_window"] = silence_window
    record["log_csv"] = log_path
    ask = ask or ask_operator
    recorder = Recorder(log_path)
    started = now()
    last_nonzero_at = None

    def message(value):
        msg = twist_type()
        if axis == "yaw":
            msg.angular.z = value
        else:
            setattr(msg.linear, axis, value)
        return msg

    def fresh():
        return node.last_odom_time is not None and now() - node.last_odom_time <= 0.35

    def check():
        if should_stop():
            raise InterruptedError("stop requested")
        if not ros.ok():
            raise RuntimeError("ROS context unavailable")
        others = other_publishers(node)
        if others is None:
            limit = 2 if allow_watchdog else 1
            if node.count_publishers("/cmd_vel") > limit:
                raise RuntimeError("another /cmd_vel publisher is present")
        elif allow_watchdog:
            if others != ["cmd_vel_watchdog"]:
                raise RuntimeError("unexpected /cmd_vel publishers: %s" % others)
        elif others:
            raise RuntimeError("another /cmd_vel publisher is present: %s" % others)

    def phase(name, value, seconds, require_feedback):
        nonlocal last_nonzero_at
        deadline = now() + seconds
        next_send = now()
        next_report = now()
        reported_motion = False
        recorder.record(now() - started, name + ":start", value, node.last_twist)
        while now() < deadline:
            check()
            if require_feedback and not fresh():
                raise RuntimeError("/odom reception stale (>0.35 seconds)")
            if node.pub.get_subscription_count() < 1:
                raise RuntimeError("base command subscriber disappeared")
            if value and node.last_twist is not None:
                reported_motion = reported_motion or abs(node.last_twist[axis_index]) > 0.003
            if now() >= next_send:
                node.pub.publish(message(value))
                if value:
                    last_nonzero_at = now()
                next_send = now() + 0.05
            if now() >= next_report:
                if value:
                    print("odom vx/vy/wz: %s" % (node.last_twist,), flush=True)
                recorder.record(now() - started, name, value, node.last_twist)
                next_report = now() + 0.25
            ros.spin_once(node, timeout_sec=0.01)
        recorder.record(now() - started, name + ":end", value, node.last_twist)
        if value and not reported_motion:
            print("WARNING: no nonzero odometry observed on commanded axis; "
                  "motor/encoder response is NOT verified.", flush=True)

    def silence_baseline_problem():
        if last_nonzero_at is None or not fresh() or node.last_twist is None:
            return "no fresh feedback at observation start; no timeout conclusion"
        baseline = node.last_twist[axis_index]
        limit = baseline_limits[axis]
        if axis == "yaw":
            if not abs(baseline) > limit:
                return ("yaw feedback magnitude not above %.2f rad/s at observation start; "
                        "no timeout conclusion" % limit)
        elif not baseline > limit:
            name = "forward" if axis == "x" else "lateral"
            return ("%s feedback not above %.2f m/s at observation start; "
                    "no timeout conclusion" % (name, limit))
        return None

    def observe_silence():
        problem = silence_baseline_problem()
        if problem is not None:
            raise RuntimeError("SILENCE_CHECK_INVALID: " + problem)
        deadline = last_nonzero_at + silence_window
        still_since = None
        record["silence_started"] = True
        next_record = now()
        print("COMMAND SILENCE: no velocity messages for up to %.2f s; "
              "watch all wheels. ZERO fallback follows." % silence_window, flush=True)
        recorder.record(now() - started, "silence:start", 0.0, node.last_twist)
        while now() < deadline:
            check()
            if not fresh():
                raise RuntimeError("SILENCE_CHECK_INVALID: /odom reception stale")
            if node.pub.get_subscription_count() < 1:
                raise RuntimeError("SILENCE_CHECK_INVALID: command subscriber disappeared")
            if now() >= next_record:
                recorder.record(now() - started, "silence", 0.0, node.last_twist)
                next_record = now() + 0.25
            vx, vy, wz = node.last_twist
            stopped = abs(vx) <= 0.01 and abs(vy) <= 0.01 and abs(wz) <= 0.04
            if stopped:
                if still_since is None:
                    still_since = node.last_odom_time
                elif node.last_odom_time - still_since >= 0.20:
                    record["silence_stop_at"] = round(
                        max(0.0, still_since - last_nonzero_at), 3)
                    print("SILENCE_STOP_OBSERVED: near-zero feedback after about %.3f s "
                          "from last command, sustained for >=0.20 s. "
                          "Reception-time estimate; physical stop still needs observation."
                          % record["silence_stop_at"], flush=True)
                    return
            else:
                still_since = None
            ros.spin_once(node, timeout_sec=0.01)
        raise RuntimeError("SILENCE_STOP_NOT_OBSERVED: no sustained near-zero feedback "
                           "within %.2f s; sending ZERO fallback. "
                           "This does not rule out a longer device timeout." % silence_window)

    try:
        print("Waiting for command subscriber and fresh /odom (max 5 s)...", flush=True)
        deadline = now() + 5.0
        while True:
            check()
            if node.pub.get_subscription_count() >= 1 and fresh():
                break
            if now() >= deadline:
                raise RuntimeError("no command subscriber or fresh /odom within 5 seconds")
            ros.spin_once(node, timeout_sec=0.01)
        print("Initial ZERO for 1 s.", flush=True)
        phase("zero_before", 0.0, 1.0, True)
        unit = "rad/s" if axis == "yaw" else "m/s"
        print("COMMAND %s=%.3f %s for at most %.2f s." % (axis, speed, unit, duration),
              flush=True)
        phase("motion", speed, duration, True)
        if check_silence_stop:
            try:
                observe_silence()
                record["silence_outcome"] = "silence_stop_observed"
            except RuntimeError as exc:
                record["silence_outcome"] = "silence_stop_not_observed_or_invalid: %s" % exc
                raise
    finally:
        print("Stopping: attempt repeated ZERO commands for 2 s.", flush=True)
        deadline = now() + 2.0
        next_send = now()
        record["zero_fallback"] = True
        try:
            while now() < deadline:
                if not ros.ok():
                    raise RuntimeError("cannot send zero: ROS context unavailable")
                if now() >= next_send:
                    node.pub.publish(message(0.0))
                    next_send = now() + 0.05
                recorder.record(now() - started, "zero_after", 0.0, node.last_twist)
                ros.spin_once(node, timeout_sec=0.01)
        except Exception as exc:
            print("ZERO transmission failed: %s; use physical motor stop." % exc,
                  file=sys.stderr, flush=True)
            raise
        finally:
            recorder.close()
        record["last_twist"] = node.last_twist
        print("Last reported vx/vy/wz: %s; physically check wheels have stopped."
              % (node.last_twist,), flush=True)
        # Ask only now: a prompt must never hold back the zero fallback.
        if sys.exc_info()[0] is not InterruptedError:
            if record.get("silence_started"):
                record["operator_silence_stop"] = ask(
                    "静默窗口内四轮是否在兜底零速之前停转?")
            if confirm_wheel_stop:
                record["operator_wheel_stop"] = ask(
                    "零速兜底阶段结束时四轮是否已完全静止?")


def evidence_block(record):
    """Markdown snippet that can be pasted into a daily log or acceptance table."""

    def show(key, default="未记录"):
        value = record.get(key)
        return default if value in (None, "") else value

    lines = [
        "## base_forward_probe 证据",
        "",
        "- 开始时间：%s" % show("started"),
        "- 结果：%s" % show("result"),
        "- 轴 / 速度 / 时长：%s / %s / %s" % (show("axis"), show("speed"), show("duration")),
        "- 静默观察窗口：%s s" % show("silence_window"),
        "- 断流判定：%s" % show("silence_outcome"),
        "- 静默后近零反馈时刻（距最后一条非零指令）：%s s" % show("silence_stop_at"),
        "- 操作员观察（静默窗口内是否在兜底前停转）：%s" % show("operator_silence_stop"),
        "- 操作员观察（零速兜底后四轮是否完全静止）：%s" % show("operator_wheel_stop"),
        "- 最后一条反馈 vx/vy/wz：%s" % (show("last_twist"),),
        "- 时间序列 CSV：%s" % show("log_csv"),
        "",
        "> 值为 unobserved 或“未记录”的观察项不能作为“已确认”的证据。",
    ]
    return "\n".join(lines)


def main(argv=None):
    args = arguments(argv)
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions

    stop = {"requested": False}

    def request_stop(signum, frame):
        stop["requested"] = True

    # Keep the context usable while finally publishes zero, including Ctrl+C.
    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), request_stop)

    class Probe(Node):
        def __init__(self):
            super().__init__("base_forward_probe")
            self.last_odom_time = None
            self.last_twist = None
            self.pub = self.create_publisher(Twist, "/cmd_vel", 1)
            self.odom_sub = self.create_subscription(Odometry, "/odom", self.observe, 1)

        def observe(self, msg):
            self.last_odom_time = time.monotonic()
            v = msg.twist.twist
            self.last_twist = (round(v.linear.x, 4), round(v.linear.y, 4),
                               round(v.angular.z, 4))

    node = None
    record = {"result": "did not finish"}
    result = 0
    try:
        node = Probe()
        print("Wheels must be off the floor; keep motor power stop reachable.", flush=True)
        exercise(node, rclpy, Twist, lambda: stop["requested"], args.speed, args.duration,
                 axis=args.axis, check_silence_stop=args.check_silence_stop,
                 silence_window=args.silence_window, log_path=args.log_csv, record=record,
                 confirm_wheel_stop=args.confirm_wheel_stop,
                 allow_watchdog=args.watchdog)
        record["result"] = "finished"
    except InterruptedError:
        print("Interrupted; zero phase finished.", flush=True)
        record["result"] = "interrupted (operator or signal)"
        result = 130
    except Exception as exc:
        print("Probe aborted: %s" % exc, file=sys.stderr, flush=True)
        record["result"] = "aborted: %s" % exc
        result = 1
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        text = evidence_block(record)
        print(text, flush=True)
        if args.evidence_out:
            with open(args.evidence_out, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
    return result


if __name__ == "__main__":
    sys.exit(main())
