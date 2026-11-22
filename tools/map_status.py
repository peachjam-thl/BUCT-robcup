#!/usr/bin/env python3
"""只读建图状态查看器（RDK X5 / ROS 2 Humble）。

用途：建图过程中随时查看 /map 尺寸与已知栅格比例、机器人位姿、雷达距离和
map→odom_combined→base_footprint→laser 的 TF 链是否完整。不发布任何指令，
不调用服务，不修改配置。

用法（板卡上，先 source 环境）：
    source /opt/ros/humble/setup.bash
    source ~/wheeltec_ros2/install/setup.bash
    python3 map_status.py                 # 单次快照
    python3 map_status.py --watch 10      # 每 10 秒打印一次，Ctrl+C 结束
    python3 map_status.py --json          # 输出 JSON，便于存档
"""
import argparse
import json
import math
import sys
import time

import rclpy
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
import tf2_ros


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class MapStatus(Node):
    def __init__(self):
        super().__init__('dsh_map_status')
        self.map_msg = None
        self.odom_msg = None
        self.scan_msg = None
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        latched = QoSProfile(depth=1,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, latched)
        self.create_subscription(Odometry, '/odom_combined', self.on_odom, 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)

    def on_map(self, msg):
        self.map_msg = msg

    def on_odom(self, msg):
        self.odom_msg = msg

    def on_scan(self, msg):
        self.scan_msg = msg

    def spin_for(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.1)

    def map_stats(self):
        m = self.map_msg
        if m is None:
            return None
        data = m.data
        known = occ = 0
        min_x = min_y = 10 ** 9
        max_x = max_y = -10 ** 9
        w = m.info.width
        for i, v in enumerate(data):
            if v < 0:
                continue
            known += 1
            if v >= 65:
                occ += 1
            cx = i % w
            cy = i // w
            if cx < min_x:
                min_x = cx
            if cx > max_x:
                max_x = cx
            if cy < min_y:
                min_y = cy
            if cy > max_y:
                max_y = cy
        res = m.info.resolution
        ox = m.info.origin.position.x
        oy = m.info.origin.position.y
        total = len(data)
        out = {
            'width': m.info.width,
            'height': m.info.height,
            'res': res,
            'box_m': [round(w * res, 2), round(m.info.height * res, 2)],
            'known': known,
            'known_pct': round(100.0 * known / total, 2) if total else 0.0,
            'occupied': occ,
            'origin': [round(ox, 2), round(oy, 2)],
        }
        if known:
            out['known_bbox_m'] = [round(ox + min_x * res, 2), round(ox + max_x * res, 2),
                                   round(oy + min_y * res, 2), round(oy + max_y * res, 2)]
        return out

    def odom_stats(self):
        o = self.odom_msg
        if o is None:
            return None
        p = o.pose.pose
        return {
            'x': round(p.position.x, 3),
            'y': round(p.position.y, 3),
            'yaw_deg': round(math.degrees(yaw_of(p.orientation)), 1),
            'vx': round(o.twist.twist.linear.x, 3),
            'wz': round(o.twist.twist.angular.z, 3),
        }

    def scan_stats(self):
        s = self.scan_msg
        if s is None:
            return None
        vals = [r for r in s.ranges if math.isfinite(r) and r > 0.02]
        if not vals:
            return {'n': len(s.ranges), 'valid': 0}
        return {
            'frame': s.header.frame_id,
            'n': len(s.ranges),
            'valid': len(vals),
            'min': round(min(vals), 2),
            'max': round(max(vals), 2),
            'stamp': round(s.header.stamp.sec + s.header.stamp.nanosec * 1e-9, 3),
        }

    def tf_stats(self):
        out = {}
        for target, source in (('map', 'odom_combined'),
                               ('odom_combined', 'base_footprint'),
                               ('base_footprint', 'laser')):
            key = '%s->%s' % (target, source)
            try:
                tr = self.tf_buffer.lookup_transform(target, source, rclpy.time.Time(), rclpy.time.Duration(seconds=1.0))
                t = tr.transform.translation
                out[key] = 'ok(%.3f,%.3f,%.3f)' % (t.x, t.y, t.z)
            except Exception as exc:  # noqa: BLE001
                out[key] = 'FAIL:%s' % type(exc).__name__
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--watch', type=float, default=0, help='每隔 N 秒重复打印，0 表示只打印一次')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    rclpy.init()
    node = MapStatus()
    rc = 0
    try:
        last_known = None
        while True:
            node.spin_for(3.0)
            snap = {
                'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'map': node.map_stats(),
                'odom': node.odom_stats(),
                'scan': node.scan_stats(),
                'tf': node.tf_stats(),
            }
            if snap['map'] is None:
                snap['map_error'] = 'no /map received (slam_toolbox running?)'
            if args.json:
                print(json.dumps(snap, ensure_ascii=False))
            else:
                print('== %s ==' % snap['time'])
                if snap['map']:
                    m = snap['map']
                    extra = ''
                    if last_known is not None:
                        extra = ' (+%d cells since last)' % (m['known'] - last_known)
                    print('map %dx%d  %.2fx%.2f m  known=%d (%.2f%%) occ=%d%s' % (
                        m['width'], m['height'], m['box_m'][0], m['box_m'][1],
                        m['known'], m['known_pct'], m['occupied'], extra))
                    if 'known_bbox_m' in m:
                        b = m['known_bbox_m']
                        print('  known bbox x=[%.2f,%.2f] y=[%.2f,%.2f]' % (b[0], b[1], b[2], b[3]))
                    last_known = m['known']
                else:
                    print('map: %s' % snap['map_error'])
                if snap['odom']:
                    o = snap['odom']
                    print('pose x=%.3f y=%.3f yaw=%.1fdeg  vx=%.3f wz=%.3f' % (
                        o['x'], o['y'], o['yaw_deg'], o['vx'], o['wz']))
                if snap['scan']:
                    s = snap['scan']
                    print('scan frame=%s valid=%d/%d min=%.2f max=%.2f' % (
                        s.get('frame', '?'), s.get('valid', 0), s['n'], s.get('min', 0), s.get('max', 0)))
                print('tf ' + '  '.join('%s=%s' % kv for kv in snap['tf'].items()))
            if args.watch <= 0:
                break
            time.sleep(args.watch)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return rc


if __name__ == '__main__':
    sys.exit(main())
