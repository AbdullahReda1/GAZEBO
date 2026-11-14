import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node, SetParameter


HERE        = os.path.dirname(os.path.realpath(__file__)    )

WORLD       = os.path.join   (HERE, 'myWorld.sdf'           )
URDF        = os.path.join   (HERE, 'robot.urdf'            )
CONTROLLERS = os.path.join   (HERE, 'controllers.yaml'      )
BRIDGE      = os.path.join   (HERE, 'bridge.yaml'           )
RVIZ        = os.path.join   (HERE, 'robot.rviz'            )
PERSPECTIVE = os.path.join   (HERE, 'trajectory.perspective')


def generate_launch_description():

    with open(URDF, 'r') as f:
        robot_description = f.read()

    spawn_active = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            'diff_drive_controller',
            'camera_trajectory_controller',
        ]
    )

    spawn_inactive = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['camera_pan_controller', '--inactive']
    )

    rqt_node = Node(
        package='rqt_gui',
        executable='rqt_gui',
        arguments=['--perspective-file', PERSPECTIVE] if os.path.exists(PERSPECTIVE) else [],
        output='screen'
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', RVIZ] if os.path.exists(RVIZ) else [],
        output='screen'
    )

    return LaunchDescription([
        SetParameter(name='use_sim_time', value=True),

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

        spawn_active,
        spawn_inactive,

        TimerAction(
            period=6.0,
            actions=[rviz_node]
        ),

        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=spawn_active,
                on_exit=[rqt_node],
            )
        ),

        Node(
            package='teleop_twist_keyboard',
            executable='teleop_twist_keyboard',
            prefix='gnome-terminal --',
            arguments=['--repeat-rate', '10.0'],
            parameters=[os.path.join(HERE, 'teleop_params.yaml')],
            remappings=[('/cmd_vel', '/diff_drive_controller/cmd_vel')],
            output='screen'
        ),
    ])