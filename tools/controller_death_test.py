"""Simulate a controller that dies mid-motion: publish 0.05 m/s for 2 s,
then exit without any zero command, and check that the base stops.

The watchdog (tools/cmd_vel_watchdog.py) must already be running on the same
ROS graph; without it the base keeps moving at 0.05 m/s until something else
sends zero. Wheels must be off the floor and motor power reachable.

Run in the robot ROS2 shell:
  python3 controller_death_test.py
"""

import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

rclpy.init()
node = Node('death_test')
pub = node.create_publisher(Twist, '/cmd_vel', 10)
samples = []
t0 = time.monotonic()


def callback(msg):
    samples.append((round(time.monotonic() - t0, 3), msg.twist.twist.linear.x))


node.create_subscription(Odometry, '/odom', callback, 10)
stop_at = t0 + 2.0
while time.monotonic() - t0 < 7.0:
    if time.monotonic() < stop_at:
        msg = Twist()
        msg.linear.x = 0.05
        pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.01)

node.destroy_node()
rclpy.shutdown()

print('last_command_at_s', round(stop_at - t0, 3))
print('samples', len(samples))
print('trace t_s: vx')
for t, v in samples[::5]:
    print('  %5.2f  %+.4f' % (t, v))

stop_time = None
search_from = next((i for i, (t, _) in enumerate(samples) if t > 2.0), len(samples))
for index in range(search_from, len(samples)):
    t, v = samples[index]
    if abs(v) <= 0.02:
        tail = samples[index:index + 5]
        if len(tail) == 5 and all(abs(vv) <= 0.02 for _, vv in tail):
            stop_time = t
            break
print('near_zero_from_s', stop_time)
if stop_time is None:
    print('RESULT: STILL MOVING after 7 s -> watchdog did NOT stop the base')
else:
    print('RESULT: stopped about %.2f s after the last command' % (stop_time - 2.0))
