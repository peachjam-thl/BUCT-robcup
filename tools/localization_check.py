#!/usr/bin/env python3
"""激光与地图对齐检查（只读）。

把一帧 /scan 的每个点，用 TF 变换到 map 坐标系，再查地图栅格：
统计有多少点落在占用栅格的容差范围内。用于验证"重载地图 + AMCL 定位"后，
激光是否真的贴合地图墙体——比只看 RViz 截图可复核。

用法（车上，先 source 环境并 export ROS_DOMAIN_ID=10）：
    python3 localization_check.py --map ~/maps/2026-11-23/map_20261123_1617.yaml
    python3 localization_check.py --map ... --radius 0.15 --max-range 12
"""
import argparse
import math
import statistics
import sys

import rclpy
import tf2_ros
import yaml
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


def read_pgm(path):
    """读取 P5 二进制 PGM，返回 (width, height, 像素字节串)。"""
    with open(path, 'rb') as f:
        data = f.read()
    if not data.startswith(b'P5'):
        raise ValueError('不是 P5 PGM: %s' % path)
    pos, fields = 2, []
    while len(fields) < 3:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b'#':
            while pos < len(data) and data[pos:pos + 1] != b'\n':
                pos += 1
            continue
        start = pos
        while pos < len(data) and not data[pos:pos + 1].isspace():
            pos += 1
        fields.append(int(data[start:pos]))
    pos += 1
    w, h, _maxval = fields
    return w, h, data[pos:pos + w * h]


class Checker(Node):
    def __init__(self):
        super().__init__('dsh_localization_check')
        self.scan = None
        self.amcl_pose = None
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)

    def on_scan(self, msg):
        self.scan = msg

    def on_amcl(self, msg):
        self.amcl_pose = msg

    def spin_for(self, sec):
        end = self.get_clock().now().nanoseconds / 1e9 + sec
        while self.get_clock().now().nanoseconds / 1e9 < end:
            rclpy.spin_once(self, timeout_sec=0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', required=True, help='地图 yaml 路径')
    ap.add_argument('--radius', type=float, default=0.15, help='命中容差（米）')
    ap.add_argument('--max-range', type=float, default=12.0, help='只统计该距离以内的点')
    args = ap.parse_args()

    meta = yaml.safe_load(open(args.map))
    img_path = meta['image']
    if not img_path.startswith('/'):
        img_path = args.map.rsplit('/', 1)[0] + '/' + img_path
    res = float(meta['resolution'])
    ox, oy = float(meta['origin'][0]), float(meta['origin'][1])
    w, h, pixels = read_pgm(img_path)

    # 占用栅格集合：统一使用 map 坐标（y 向上）；PGM 第 0 行是地图最上方
    occ = set()
    for i in enumerate(pixels):
        idx, v = i
        if v < 60:
            occ.add((idx % w, (h - 1) - (idx // w)))
    print('地图 %dx%d  res=%.3f  origin=(%.2f,%.2f)  占用栅格=%d' % (w, h, res, ox, oy, len(occ)))

    rclpy.init()
    node = Checker()
    node.spin_for(6)
    if node.scan is None:
        print('未收到 /scan')
        return 2
    scan = node.scan
    try:
        tr = node.tf_buffer.lookup_transform('map', scan.header.frame_id, rclpy.time.Time())
    except Exception as exc:  # noqa: BLE001
        print('拿不到 map -> %s 的 TF: %s' % (scan.header.frame_id, exc))
        return 2

    t = tr.transform.translation
    q = tr.transform.rotation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    cy, sy = math.cos(yaw), math.sin(yaw)
    radius_cells = max(1, int(round(args.radius / res)))

    dists, outside = [], 0
    for i, r in enumerate(scan.ranges):
        if not math.isfinite(r) or r <= 0.02 or r > args.max_range:
            continue
        a = scan.angle_min + i * scan.angle_increment
        lx, ly = r * math.cos(a), r * math.sin(a)
        mx = t.x + cy * lx - sy * ly
        my = t.y + sy * lx + cy * ly
        ix = int(math.floor((mx - ox) / res))
        iy = int(math.floor((my - oy) / res))
        if not (0 <= ix < w and 0 <= iy < h):
            outside += 1
            continue
        best = 99.0
        for dy in range(-radius_cells, radius_cells + 1):
            for dx in range(-radius_cells, radius_cells + 1):
                if (ix + dx, iy + dy) in occ:
                    d = math.hypot(dx, dy) * res
                    if d < best:
                        best = d
        dists.append(best)

    print('map->%s: (%.3f, %.3f, %.1f deg)' % (scan.header.frame_id, t.x, t.y, math.degrees(yaw)))
    print('统计点数 %d（地图外 %d）' % (len(dists), outside))
    if dists:
        hits = sum(1 for d in dists if d <= args.radius + 1e-9)
        near = sum(1 for d in dists if d <= 0.30)
        print('命中占用(<=%.2fm): %d/%d = %.1f%%' % (args.radius, hits, len(dists), 100.0 * hits / len(dists)))
        print('命中占用(<=0.30m): %d/%d = %.1f%%' % (near, len(dists), 100.0 * near / len(dists)))
        print('最近占用距离: 中位数 %.3f m, 90分位 %.3f m' % (
            statistics.median(dists), sorted(dists)[max(0, int(len(dists) * 0.9) - 1)]))
    if node.amcl_pose is not None:
        p = node.amcl_pose.pose.pose.position
        print('AMCL 位姿: (%.3f, %.3f)' % (p.x, p.y))

    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
