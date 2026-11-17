#!/usr/bin/env python3
"""Bounded wheels-lifted axis probe for the inspected WHEELTEC Twist driver.

Run in the robot's ROS2 Humble shell with the base_serial driver running.
No launch files or firmware are changed. This is NOT an independent MCU watchdog.
Physical wheel support and a reachable motor power switch are required.
"""

import argparse
import math
import signal
import sys
import time


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=("x", "y", "yaw"), default="x",
                        help="positive x forward, y left, yaw counterclockwise")
    parser.add_argument("--speed", type=float, default=0.03,
                        help="positive m/s for x/y (max 0.05), rad/s for yaw (max 0.15)")
    parser.add_argument("--duration", type=float, default=1.0, help="seconds, >0 and <=3.0")
    parser.add_argument("--check-silence-stop", action="store_true",
                        help="x only: observe command silence for at most 1.5 s before zero fallback")
    args = parser.parse_args(argv)
    limit = 0.15 if args.axis == "yaw" else 0.05
    unit = "rad/s" if args.axis == "yaw" else "m/s"
    if not math.isfinite(args.speed) or not 0 < args.speed <= limit:
        parser.error("speed must be finite and in (0, %s] %s" % (limit, unit))
    if not math.isfinite(args.duration) or not 0 < args.duration <= 3.0:
        parser.error("duration must be finite and in (0, 3.0] seconds")
    if args.check_silence_stop and args.axis != "x":
        parser.error("command-silence check is supported only for axis x")
    return args


def exercise(node, ros, twist_type, should_stop, speed, duration, now=time.monotonic,
             axis="x", check_silence_stop=False):
    """Publish bounded commands; attempt zero before context destruction on every exit."""
    axis_index = {"x": 0, "y": 1, "yaw": 2}[axis]
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
        if node.count_publishers("/cmd_vel") > 1:
            raise RuntimeError("another /cmd_vel publisher is present")

    def phase(value, seconds, require_feedback):
        nonlocal last_nonzero_at
        deadline = now() + seconds
        next_send = now()
        next_report = now()
        reported_motion = False
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
            if value and now() >= next_report:
                print("odom vx/vy/wz: %s" % (node.last_twist,), flush=True)
                next_report = now() + 0.25
            ros.spin_once(node, timeout_sec=0.01)
        if value and not reported_motion:
            print("WARNING: no nonzero odometry observed on commanded axis; "
                  "motor/encoder response is NOT verified.", flush=True)

    def observe_silence():
        # A stationary baseline cannot establish whether command loss stops motion.
        if (axis != "x" or last_nonzero_at is None or not fresh()
                or node.last_twist is None or not node.last_twist[0] > 0.02):
            raise RuntimeError("SILENCE_CHECK_INVALID: forward feedback not above 0.02 m/s "
                               "at observation start; no timeout conclusion")
        deadline = last_nonzero_at + 1.5
        still_since = None
        print("COMMAND SILENCE: no velocity messages for up to 1.5 s; "
              "watch all wheels. ZERO fallback follows.", flush=True)
        while now() < deadline:
            check()
            if not fresh():
                raise RuntimeError("SILENCE_CHECK_INVALID: /odom reception stale")
            if node.pub.get_subscription_count() < 1:
                raise RuntimeError("SILENCE_CHECK_INVALID: command subscriber disappeared")
            vx, vy, wz = node.last_twist
            stopped = abs(vx) <= 0.01 and abs(vy) <= 0.01 and abs(wz) <= 0.04
            if stopped:
                if still_since is None:
                    still_since = node.last_odom_time
                elif node.last_odom_time - still_since >= 0.20:
                    print("SILENCE_STOP_OBSERVED: near-zero feedback after about %.3f s "
                          "from last command, sustained for >=0.20 s. "
                          "Reception-time estimate; physical stop still needs observation."
                          % max(0.0, still_since - last_nonzero_at), flush=True)
                    return
            else:
                still_since = None
            ros.spin_once(node, timeout_sec=0.01)
        raise RuntimeError("SILENCE_STOP_NOT_OBSERVED: no sustained near-zero feedback "
                           "within 1.5 s; sending ZERO fallback. "
                           "This does not rule out a longer device timeout.")

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
        phase(0.0, 1.0, True)
        unit = "rad/s" if axis == "yaw" else "m/s"
        print("COMMAND %s=%.3f %s for at most %.2f s." % (axis, speed, unit, duration),
              flush=True)
        phase(speed, duration, True)
        if check_silence_stop:
            observe_silence()
    finally:
        print("Stopping: attempt repeated ZERO commands for 2 s.", flush=True)
        deadline = now() + 2.0
        next_send = now()
        try:
            while now() < deadline:
                if not ros.ok():
                    raise RuntimeError("cannot send zero: ROS context unavailable")
                if now() >= next_send:
                    node.pub.publish(message(0.0))
                    next_send = now() + 0.05
                ros.spin_once(node, timeout_sec=0.01)
        except Exception as exc:
            print("ZERO transmission failed: %s; use physical motor stop." % exc,
                  file=sys.stderr, flush=True)
            raise
        print("Last reported vx/vy/wz: %s; physically check wheels have stopped."
              % (node.last_twist,), flush=True)


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
    result = 0
    try:
        node = Probe()
        print("Wheels must be off the floor; keep motor power stop reachable.", flush=True)
        exercise(node, rclpy, Twist, lambda: stop["requested"], args.speed, args.duration,
                 axis=args.axis, check_silence_stop=args.check_silence_stop)
    except InterruptedError:
        print("Interrupted; zero phase finished.", flush=True)
        result = 130
    except Exception as exc:
        print("Probe aborted: %s" % exc, file=sys.stderr, flush=True)
        result = 1
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return result


if __name__ == "__main__":
    sys.exit(main())
