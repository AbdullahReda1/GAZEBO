from contextlib import suppress

import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType


class TimeProbe(Node):
    def __init__(self):
        super().__init__('time_probe')
        self.wall_clock = Clock(clock_type=ClockType.SYSTEM_TIME)
        self.last_wall  = self.wall_clock.now()
        self.create_timer(1.0, self.tick)

    def tick(self):
        use_sim  = self.get_parameter('use_sim_time').value
        ros_now  = self.get_clock().now()
        wall_now = self.wall_clock.now()
        wall_gap = (wall_now - self.last_wall).nanoseconds / 1e9
        self.last_wall = wall_now
        self.get_logger().info(
            f'use_sim_time={use_sim}  ros_time={ros_now.nanoseconds / 1e9:10.3f}  '
            f'wall_time={wall_now.nanoseconds / 1e9:.3f}  wall_seconds_since_last_tick={wall_gap:.2f}'
        )


def main():
    rclpy.init()
    node = TimeProbe()
    with suppress(KeyboardInterrupt):
        rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()