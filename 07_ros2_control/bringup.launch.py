import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node, SetParameter


HERE        = os.path.dirname(os.path.realpath(__file__))

WORLD       = os.path.join   (HERE, 'myWorld.sdf'       )
URDF        = os.path.join   (HERE, 'robot.urdf'        )
CONTROLLERS = os.path.join   (HERE, 'controllers.yaml'  )
BRIDGE      = os.path.join   (HERE, 'bridge.yaml'       )
RVIZ        = os.path.join   (HERE, 'robot.rviz'        )


def generate_launch_description():

    with open(URDF, 'r') as f:
        robot_description = f.read()

    return LaunchDescription([
        SetParameter(
            name='use_sim_time', 
            value=True
        ),
        ExecuteProcess(
            cmd=['gz', 'sim', '-r', WORLD],
            output='screen'
        ),
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            parameters=[{'config_file': BRIDGE}],
            output='screen'
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen'
        ),
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=['-topic', 'robot_description', '-name', 'myrobot', '-z', '0.3'],
            output='screen'
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=['joint_state_broadcaster']
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=['diff_drive_controller']
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=['camera_pan_controller']
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            arguments=['camera_trajectory_controller', '--inactive']
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            output="screen",
            arguments=['-d', RVIZ] if os.path.exists(RVIZ) else []
        ),
    ])