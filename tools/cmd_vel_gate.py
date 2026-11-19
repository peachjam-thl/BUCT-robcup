#!/usr/bin/env python3
"""D3 wheels-lifted host gate: /cmd_vel -> /cmd_vel_safe.

Starts DISARMED. A manual Trigger arm service requires live stationary odometry
and the expected ROS graph. A fault or command timeout latches DISARMED. It is
not an MCU watchdog, motion authorization for ground use, or a security boundary.
"""
import argparse
import json
import math
import signal
import sys
import time


ZERO = (0.0,) * 6  # linear xyz, angular xyz


class GateLogic:
    """Pure logic. Only requests update command time; output zeros never do."""

    def __init__(self, timeout=0.4, feedback_timeout=0.35,
                 max_linear=0.05, max_angular=0.15):
        self.timeout = timeout
        self.feedback_timeout = feedback_timeout
        self.max_linear = max_linear
        self.max_angular = max_angular
        self.armed = False
        self.reason = 'STARTUP'
        self.last_request = None
        self.last_feedback = None
        self.feedback_key = None
        self.velocity = None
        self.moving = False

    def stop(self, reason):
        self.armed = False
        self.reason = reason
        self.last_request = None
        self.moving = False
        return ZERO

    def feedback(self, now, key, velocity):
        if len(velocity) != 3 or not all(math.isfinite(v) for v in velocity):
            self.velocity = None
            self.last_feedback = None
            self.stop('INVALID_ODOMETRY')
            return
        if self.feedback_key is not None and key < self.feedback_key:
            self.velocity = None
            self.last_feedback = None
            self.stop('ODOMETRY_TIME_REVERSED')
            return
        # Replayed identical stamps cannot keep feedback alive.
        if key != self.feedback_key:
            self.feedback_key = key
            self.velocity = velocity
            self.last_feedback = now

    def health(self, now, graph_error=None):
        if graph_error:
            return graph_error
        if self.last_feedback is None or now - self.last_feedback > self.feedback_timeout:
            return 'ODOMETRY_STALE'
        return None

    def arm(self, now, graph_error=None):
        error = self.health(now, graph_error)
        if not error and (self.velocity is None or abs(self.velocity[0]) > 0.01
                          or abs(self.velocity[1]) > 0.01 or abs(self.velocity[2]) > 0.04):
            error = 'ODOMETRY_NOT_STATIONARY'
        if error:
            self.stop(error)
            return False, error
        self.armed = True
        self.reason = 'WAITING_FOR_NEW_REQUEST'
        self.last_request = None
        self.moving = False
        return True, self.reason

    def request(self, now, values, graph_error=None):
        if not self.armed:
            return ZERO
        if self.last_request is not None and now - self.last_request >= self.timeout:
            return self.stop('COMMAND_TIMEOUT')
        error = self.health(now, graph_error)
        if error:
            return self.stop(error)
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            return self.stop('INVALID_COMMAND')
        if any(abs(values[i]) > 1e-9 for i in (2, 3, 4)):
            return self.stop('UNSUPPORTED_AXIS')
        if (math.hypot(values[0], values[1]) > self.max_linear + 1e-9
                or abs(values[5]) > self.max_angular + 1e-9):
            return self.stop('SPEED_LIMIT')
        self.last_request = now
        self.moving = any(abs(v) > 1e-9 for v in values)
        self.reason = 'FORWARDING' if self.moving else 'ZERO_REQUEST'
        return tuple(values)

    def tick(self, now, graph_error=None):
        if not self.armed:
            return ZERO
        error = self.health(now, graph_error)
        if error:
            return self.stop(error)
        if self.last_request is not None and now - self.last_request >= self.timeout:
            return self.stop('COMMAND_TIMEOUT')
        # Never regenerate a previous nonzero command from the timer.
        return None if self.moving else ZERO


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-topic', default='/cmd_vel')
    parser.add_argument('--output-topic', default='/cmd_vel_safe')
    parser.add_argument('--odom-topic', default='/odom')
    parser.add_argument('--odom-frame', default='odom_combined')
    parser.add_argument('--base-frame', default='base_footprint')
    parser.add_argument('--timeout', type=float, default=0.4)
    parser.add_argument('--feedback-timeout', type=float, default=0.35)
    parser.add_argument('--rate', type=float, default=20.0)
    parser.add_argument('--check-imports', action='store_true',
                        help='check ROS imports without creating a node or sending commands')
    args = parser.parse_args(argv)
    topics = (args.input_topic, args.output_topic, args.odom_topic)
    if any(not t.startswith('/') or t == '/' for t in topics) or len(set(topics)) != 3:
        parser.error('input, output and odom must be distinct absolute topic names')
    for name, low, high in (('timeout', 0.1, 1.0), ('feedback_timeout', 0.15, 1.0),
                            ('rate', 10.0, 50.0)):
        value = getattr(args, name)
        if not math.isfinite(value) or not low <= value <= high:
            parser.error('%s must be finite and in [%s, %s]' % (name, low, high))
    return args


def main(argv=None):
    args = arguments(argv)
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from std_msgs.msg import String
    from std_srvs.srv import Trigger
    from rclpy.clock import Clock, ClockType
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions

    if args.check_imports:
        print('ROS imports OK; steady clock type: %s' % ClockType.STEADY_TIME)
        return 0

    class Gate(Node):
        def __init__(self):
            super().__init__('cmd_vel_gate')
            self.logic = GateLogic(args.timeout, args.feedback_timeout)
            self.pub = self.create_publisher(Twist, args.output_topic, 1)
            self.state_pub = self.create_publisher(String, '/cmd_vel_gate/state', 1)
            self.request_sub = self.create_subscription(Twist, args.input_topic, self.on_request, 1)
            self.odom_sub = self.create_subscription(Odometry, args.odom_topic, self.on_odom, 1)
            self.arm_service = self.create_service(Trigger, '/cmd_vel_gate/arm', self.on_arm)
            self.disarm_service = self.create_service(Trigger, '/cmd_vel_gate/disarm', self.on_disarm)
            self.last_state = None
            self.last_report = float('-inf')
            self.odom_frames_valid = False
            self.steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
            self.timer = self.create_timer(1.0 / args.rate, self.on_tick, clock=self.steady_clock)
            self.get_logger().warn('D3 WHEELS-LIFTED ONLY. DISARMED. Output %s, input %s. '
                                   'Linear vector <=0.05 m/s, yaw <=0.15 rad/s.'
                                   % (args.output_topic, args.input_topic))

        def graph_error(self):
            output_pubs = self.get_publishers_info_by_topic(args.output_topic)
            if (len(output_pubs) != 1 or output_pubs[0].node_name != self.get_name()
                    or output_pubs[0].node_namespace != self.get_namespace()):
                return 'OUTPUT_PUBLISHER_CONFLICT'
            subscribers = self.get_subscriptions_info_by_topic(args.output_topic)
            if sum(s.node_name == 'wheeltec_robot' for s in subscribers) != 1:
                return 'EXPECTED_DRIVER_MISSING_OR_DUPLICATE'
            if any(s.node_name == 'wheeltec_robot'
                   for s in self.get_subscriptions_info_by_topic(args.input_topic)):
                return 'DRIVER_BYPASSES_GATE'
            if self.count_publishers(args.input_topic) > 1:
                return 'MULTIPLE_COMMAND_SOURCES'
            if self.count_publishers(args.odom_topic) != 1:
                return 'ODOMETRY_SOURCE_MISSING_OR_DUPLICATE'
            if not self.odom_frames_valid:
                return 'ODOMETRY_FRAME_MISMATCH_OR_MISSING'
            return None

        def publish(self, values):
            if values is None:
                return
            msg = Twist()
            msg.linear.x, msg.linear.y, msg.linear.z = values[:3]
            msg.angular.x, msg.angular.y, msg.angular.z = values[3:]
            self.pub.publish(msg)

        def report(self):
            state = ('ARMED' if self.logic.armed else 'DISARMED', self.logic.reason)
            now = time.monotonic()
            if state != self.last_state or now - self.last_report >= 1.0:
                msg = String()
                msg.data = json.dumps({'state': state[0], 'reason': state[1]})
                self.state_pub.publish(msg)
                if state != self.last_state:
                    self.get_logger().info('%s: %s' % state)
                self.last_state, self.last_report = state, now

        def on_odom(self, msg):
            stamp = (msg.header.stamp.sec, msg.header.stamp.nanosec)
            self.odom_frames_valid = (msg.header.frame_id == args.odom_frame
                                      and msg.child_frame_id == args.base_frame and stamp != (0, 0))
            if not self.odom_frames_valid:
                self.logic.last_feedback = None
                self.logic.velocity = None
                self.publish(self.logic.stop('ODOMETRY_FRAME_MISMATCH_OR_MISSING'))
                return
            v = msg.twist.twist
            self.logic.feedback(time.monotonic(), stamp, (v.linear.x, v.linear.y, v.angular.z))

        def on_request(self, msg):
            values = (msg.linear.x, msg.linear.y, msg.linear.z,
                      msg.angular.x, msg.angular.y, msg.angular.z)
            self.publish(self.logic.request(time.monotonic(), values, self.graph_error()))
            self.report()

        def on_tick(self):
            self.publish(self.logic.tick(time.monotonic(), self.graph_error()))
            self.report()

        def on_arm(self, request, response):
            error = self.graph_error()
            if self.count_publishers(args.input_topic) != 0:
                error = 'STOP_COMMAND_SOURCE_BEFORE_ARM'
            response.success, response.message = self.logic.arm(time.monotonic(), error)
            self.publish(ZERO)
            self.report()
            return response

        def on_disarm(self, request, response):
            self.publish(self.logic.stop('OPERATOR_DISARM'))
            response.success, response.message = True, 'DISARMED'
            self.report()
            return response

    stop = {'requested': False}
    def request_stop(signum, frame):
        stop['requested'] = True

    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    for name in ('SIGINT', 'SIGTERM', 'SIGHUP'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), request_stop)
    node = None
    try:
        node = Gate()
        while rclpy.ok() and not stop['requested']:
            rclpy.spin_once(node, timeout_sec=0.05)
    finally:
        if node is not None:
            # Best effort only: independent MCU protection is still required.
            deadline = time.monotonic() + 1.0
            node.logic.stop('SHUTDOWN')
            while rclpy.ok() and time.monotonic() < deadline:
                node.publish(ZERO)
                time.sleep(1.0 / args.rate)
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
