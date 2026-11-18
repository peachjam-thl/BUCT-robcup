#!/usr/bin/env python3
"""Host-side /cmd_vel command-timeout watchdog.

If no velocity command arrives for --timeout seconds, publish zero Twist at
--rate Hz so the base stops. This protects against a controller process dying
or a topic going silent while this node and the driver are still alive.

It is NOT an MCU watchdog. It cannot cover a crashed driver, a cut serial
cable or a dead compute board; it also cannot prove the firmware has any
independent timeout. Pair it with tests/check_cmd_vel_watchdog.py, which runs
without ROS, and with the silence check in tools/base_forward_probe.py.

Usage:
  python3 cmd_vel_watchdog.py --timeout 0.4 --rate 20
  python3 cmd_vel_watchdog.py --topic /cmd_vel --timeout 0.3 --rate 20
"""

import argparse
import math
import signal
import sys
import time


class WatchdogLogic:
    """Pure decision logic so the stop behaviour can be tested without ROS."""

    def __init__(self, timeout):
        self.timeout = timeout
        self.last_activity = None
        self.stopping = False

    def command(self, stamp, moving):
        """Record a received command; only a moving command releases the stop."""
        self.last_activity = stamp
        if moving:
            self.stopping = False

    def tick(self, stamp):
        """Return (publish_zero, event); event is None, 'startup' or 'silence'."""
        if self.last_activity is None:
            if not self.stopping:
                self.stopping = True
                return True, "startup"
            return True, None
        if stamp - self.last_activity >= self.timeout:
            if not self.stopping:
                self.stopping = True
                return True, "silence"
            return True, None
        return False, None


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="/cmd_vel",
                        help="topic to watch and to publish zeros on (default /cmd_vel)")
    parser.add_argument("--timeout", type=float, default=0.4,
                        help="command silence before zero is published, 0.1 to 2.0 s")
    parser.add_argument("--rate", type=float, default=20.0,
                        help="zero refresh rate while silent, 5 to 50 Hz")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0.1 <= args.timeout <= 2.0:
        parser.error("timeout must be finite and in [0.1, 2.0] seconds")
    if not math.isfinite(args.rate) or not 5.0 <= args.rate <= 50.0:
        parser.error("rate must be finite and in [5, 50] Hz")
    return args


def main(argv=None):
    args = arguments(argv)

    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions

    class Watchdog(Node):
        def __init__(self):
            super().__init__("cmd_vel_watchdog")
            self.logic = WatchdogLogic(args.timeout)
            self.pub = self.create_publisher(Twist, args.topic, 10)
            self.sub = self.create_subscription(Twist, args.topic, self.on_command, 10)
            self.timer = self.create_timer(1.0 / args.rate, self.on_timer)
            self.get_logger().info(
                "watching %s; timeout %.2f s; zero refresh %.0f Hz"
                % (args.topic, args.timeout, args.rate))

        def on_command(self, msg):
            moving = (abs(msg.linear.x) + abs(msg.linear.y) + abs(msg.linear.z)
                      + abs(msg.angular.x) + abs(msg.angular.y) + abs(msg.angular.z)) > 1e-6
            was_stopping = self.logic.stopping
            self.logic.command(time.monotonic(), moving)
            if moving and was_stopping:
                self.get_logger().info("WATCHDOG_RELEASE: moving command received")

        def on_timer(self):
            publish, event = self.logic.tick(time.monotonic())
            if event == "silence":
                self.get_logger().warn(
                    "WATCHDOG_STOP: no %s for %.2f s; publishing zero"
                    % (args.topic, args.timeout))
            elif event == "startup":
                self.get_logger().info("WATCHDOG_START: no command yet; holding zero")
            if publish:
                self.pub.publish(Twist())

    stop = {"requested": False}

    def request_stop(signum, frame):
        stop["requested"] = True

    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), request_stop)

    node = Watchdog()
    try:
        while rclpy.ok() and not stop["requested"]:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        # Leave zeros behind: never exit while the last command may be nonzero.
        for _ in range(5):
            node.pub.publish(Twist())
            time.sleep(0.02)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
