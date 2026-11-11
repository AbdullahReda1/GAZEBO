# info_7.md: ros2_control Inside Gazebo, the Depth Pass

Session 7 of 7. In lesson 3b you got the wheels driving. In lesson 5 you added a camera pan joint. Now you learn how the pieces really work, tune them, and move the camera with a trajectory controller.

## 1. What you already have

| Piece                              | Lesson | Job                                                  |
| ---------------------------------- | ------ | ---------------------------------------------------- |
| `<ros2_control>` tag in the URDF   | 3b     | Declares joints and their interfaces                 |
| `gz_ros2_control` plugin           | 3b     | Connects those interfaces to Gazebo joints           |
| `controller_manager`               | 3b     | Loads and runs controllers inside the Gazebo process |
| `joint_state_broadcaster`          | 3b     | Publishes `/joint_states`                            |
| `diff_drive_controller`            | 3b     | Wheels: `cmd_vel` in, odometry out                   |
| `camera_pan_controller`            | 5      | Camera: one angle in, joint moves                    |

## 2. Interfaces: what a joint can be told and what it reports

A joint has **command interfaces** (things a controller may write) and **state interfaces** (things it may read). A controller can only write a command interface it has claimed, and only one controller can hold a claim at a time.

| Command interface | What the controller writes | What `gz_ros2_control` does with it                                               |
| ----------------- | -------------------------- | --------------------------------------------------------------------------------- |
| `velocity`        | A target speed             | Sets the joint velocity directly. Your wheels use this                            |
| `position`        | A target angle             | Turns the error into a velocity with the P law (section 4). Your camera uses this |
| `effort`          | A force or torque          | Applies it to the joint as force                                                  |

While no controller has claimed a joint, `hold_joints` (default true) keeps it still. When a controller claims it, the joint follows that controller. If the controller stops, the joint is held again.

The same joint can appear in several controllers, but only one of them may be active at a time. That is how you switch the camera between two controllers in the practical.

## 3. Controller life cycle

A controller is a small state machine:

| State        | Meaning                                              |
| ------------ | ---------------------------------------------------- |
| unconfigured | Loaded, no parameters read yet                       |
| inactive     | Configured. Parameters are valid, no claim on joints |
| active       | Running. It holds its claims and writes commands     |

The `spawner` command loads the controller, configures it and activates it. The flag `--inactive` stops after configure, so the controller waits without claiming anything. You can talk to the controller manager with the `ros2 control` command:

```bash
ros2 control list_controllers -v
ros2 control list_hardware_interfaces
ros2 control list_hardware_components
ros2 control switch_controllers --deactivate camera_pan_controller --activate camera_trajectory_controller
ros2 control set_controller_state camera_trajectory_controller inactive
```

`list_controllers -v` shows which interfaces each controller has claimed. This is the first command to run when a joint does not move.

## 4. The P law and the update rate

You saw in lesson 5 how a position command becomes motion. The plugin sets the joint velocity like this:

```text
velocity = position_proportional_gain x update_rate x (target - position)
```

Each control cycle closes a fraction `gain` of the remaining error. Think of it as a discrete loop: `error_next = (1 - gain) x error`.

| Gain            | What happens (in theory)                         |
| --------------- | ------------------------------------------------ |
| below 1         | Smooth approach, no overshoot. Smaller is slower |
| exactly 1       | The target is reached in one cycle               |
| between 1 and 2 | Overshoots and swings back, the swings shrink    |
| 2 or more       | Unstable: each swing is bigger than the last     |

Real physics adds some lag, so treat these limits as a guide. The speed of the approach depends on both numbers. A rough time constant is `1 / (gain x update_rate)` seconds. With gain 0.1 and 100 Hz that is 0.1 s.

The controller manager runs at `update_rate` (100 Hz in your file) and Gazebo steps at 1000 Hz. That is the log line you saw: "Desired controller update period (0.01 s) is slower than the gazebo simulation period (0.001 s)". It is harmless. The controllers simply run every tenth physics step. Setting `update_rate: 1000` removes the warning. It cannot go above the physics rate.

You set the gain in the plugin block of the URDF. It is read when the plugin loads, so restart the simulation after you change it:

```xml
<plugin filename="gz_ros2_control-system" name="gz_ros2_control::GazeboSimROS2ControlPlugin">
    <parameters>/absolute/path/to/controllers.yaml</parameters>
    <position_proportional_gain>0.1</position_proportional_gain>
</plugin>
```

## 5. The trajectory controller

The group position controller jumps to a target as fast as the P law allows. A `joint_trajectory_controller` follows a path in time: you give it points and when to be there. It also reports its progress, and it can say whether the goal was reached.

```yaml
camera_trajectory_controller:
  ros__parameters:
    joints:
      - camera_pan_joint
    command_interfaces:
      - position
    state_interfaces:
      - position
      - velocity
    allow_partial_joints_goal: false
    constraints:
      stopped_velocity_tolerance: 0.05
      goal_time: 2.0
      camera_pan_joint:
        trajectory: 0.2
        goal: 0.05
```

It also needs a type line inside `controller_manager`:

```yaml
camera_trajectory_controller:
  type: joint_trajectory_controller/JointTrajectoryController
```

The `constraints` block makes it check itself. `trajectory` is how far from the path it may drift on the way. `goal` is how close to the target it must end. `goal_time` is how long after the end it may take to get there. If a check fails, the goal is aborted with an error code. Setting them to 0 turns that check off.

There are two ways to give it a goal:

```bash
ros2 topic pub --once /camera_trajectory_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [camera_pan_joint], points: [{positions: [0.8], time_from_start: {sec: 2}}]}"
```

```bash
ros2 action send_goal /camera_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: [camera_pan_joint], points: [{positions: [0.8], time_from_start: {sec: 2}}]}}"
```

Leave the header stamp at zero. That means "start now". The action also gives feedback and a result, which the topic does not.

To see how well the camera follows the path:

```bash
ros2 topic echo /camera_trajectory_controller/controller_state --field error.positions
```

## 6. Common traps

| Symptom                           | Usual cause                                                                             |
| --------------------------------- | --------------------------------------------------------------------------------------- |
| A controller will not activate    | Another active controller already claimed the same joint interface                      |
| `failed to configure`             | Its parameter block is missing or has a wrong name, for example no `joints`             |
| A joint name error                | The name in YAML must match the joint name in the URDF exactly                          |
| Joint does not move at all        | Controller is inactive, or `hold_joints` is holding it. Run `list_controllers -v`       |
| Joint shakes or swings            | `position_proportional_gain` is above 1. Lower it                                       |
| Trajectory goal aborted           | `trajectory`, `goal` or `goal_time` is too tight. Read the result code                  |
| Trajectory is ignored             | The header stamp is in the past. Leave it at zero                                       |
| New parameters seem to do nothing | Your installed version does not know them. Check with `ros2 param list /<controller>`   |
| Gain change has no effect         | The gain is read when the plugin loads. Restart the simulation                          |

## Practical: tune the camera and move it along a path

Files in `07_ros2_control/workarea/`: everything from lesson 6, with `controllers.yaml` and `bringup.launch.py` updated and a gain tag added in `robot.urdf`.

- Set the controllers path again and start everything:

```bash
cd 07_ros2_control/workarea
sed -i "s|/absolute/path/to/controllers.yaml|$PWD/controllers.yaml|" robot.urdf
ros2 launch $PWD/bringup.launch.py
```

- Look at the controllers. `camera_pan_controller` should be active and `camera_trajectory_controller` inactive:

```bash
ros2 control list_controllers -v
```

- **Tune the gain.** Command a move and watch the angle. Do this for the gain 0.1, then 1.0, then 1.8 (edit the number in `robot.urdf`, restart the simulation each time):

```bash
ros2 topic echo /joint_states --field position
ros2 topic pub --once /camera_pan_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.8]}"
```

At 0.1 the camera glides. At 1.0 it arrives in one jump. At 1.8 it swings past the target and settles. Do not test 2.0 or more unless you are ready to stop the simulation. Put the gain back to 0.1 afterwards.

- **Change the update rate.** Set `update_rate: 1000` in `controllers.yaml` and restart. The log warning disappears. The camera is now about ten times faster for the same gain, because the loop runs ten times more often.
- **Switch controllers.** Give the joint to the trajectory controller:

```bash
ros2 control switch_controllers --deactivate camera_pan_controller --activate camera_trajectory_controller
ros2 control list_controllers -v
```

- **Send a path.** Use the topic or the action from section 5, and watch the error in another terminal. The camera now takes 2 seconds instead of jumping. Try a path with two points:

```bash
ros2 action send_goal /camera_trajectory_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: [camera_pan_joint], points: [{positions: [0.8], time_from_start: {sec: 2}}, {positions: [-0.8], time_from_start: {sec: 5}}]}}"
```

- **Break a goal on purpose.** Set `goal: 0.0001` and `goal_time: 0.1` in `controllers.yaml`, restart, send the same goal, and read the result code. Then put the numbers back.

## Stretch: a tilt joint

To make a pan-tilt camera, add a short link under the pan joint and a second revolute joint on the `y` axis, between that link and `camera_link`. Add the joint to the `<ros2_control>` tag with a position command, add it to `joints` in `camera_trajectory_controller`, and you can send two-joint paths. A positive angle on the `y` axis looks down. Keep the camera top under the lidar scan plane (z = 0.10 from the base).

## Updated folder for this lesson

```txt
07_ros2_control/
├── workarea/
│   ├── myWorld.sdf
│   ├── robot.urdf              # + position_proportional_gain tag
│   ├── controllers.yaml        # + camera_trajectory_controller
│   ├── bridge.yaml
│   ├── teleop_params.yaml
│   ├── time_probe.py
│   ├── bringup.launch.py       # camera_trajectory_controller starts inactive
│   └── robot.rviz              # your saved RViz2 setup
└── info_7.md
```
