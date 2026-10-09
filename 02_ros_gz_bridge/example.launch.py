from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': 'bridge_config_example.yaml'}],
        output='screen'
    )
    return LaunchDescription([bridge])