from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():
    gazebo = ExecuteProcess(
        cmd = ['gz', 'sim', '-r', 'empty.sdf'],
        output = 'screen'
    )

    spawn = Node(
        package = 'ros_gz_sim',
        executable = 'create',
        arguments = [
            '-file', '/mnt/ubuntu_data/ROS2/URDF/01_urdf_basics/diff_drive.urdf',
            '-name', 'robot',
            '-z', '5'
        ],
        output = 'screen'
    )
    
    delay = TimerAction(
        period = 6.0,
        actions = [spawn]
    )

    return LaunchDescription([gazebo, delay])