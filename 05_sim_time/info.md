# Simulation Time and use_sim_time

Session 5 of 7. Broad pass. This lesson also upgrades the robot to **v2**: every sensor gets its own link with a shape, joined to the base with a joint, and the camera sits on a pan joint you can move.

## 1. Three clocks

A simulation has more than one idea of "now". Keep these three apart and most time bugs disappear.

| Clock     | Who owns it     | Stops when Gazebo is paused?     | Can run slower than your wall clock? |
| --------- | --------------- | -------------------------------- | ------------------------------------ |
| Wall time | The computer    | No                               | No, it is the wall clock             |
| Sim time  | Gazebo physics  | Yes                              | Yes, see the real time factor        |
| ROS time  | Each ROS 2 node | Only if `use_sim_time` is true   | Only if `use_sim_time` is true       |

Why does sim time exist? Only a physics step moves the world. A step can take longer to compute than the time it simulates, for example on a slow computer or with a camera rendering. If your nodes used the wall clock, "one second" would mean a different amount of robot motion each run. Sim time keeps timers, controllers and timestamps in step with what the robot really did.

ROS time is just "whatever this node's clock says". By default that is the wall clock. With `use_sim_time` set to true it becomes Gazebo's sim time.

## 2. How sim time reaches ROS 2

Gazebo publishes its time on a gz topic called `/clock`, one message for every physics step. The message holds three times (sim, real, system). With the default 1 ms step and a simulation that keeps real time, that is about 1000 messages per second.

You learned the next part in lesson 2: the bridge turns the gz message into `rosgraph_msgs/msg/Clock`, one way only, `[`. Every ROS 2 node that has `use_sim_time` true listens to `/clock` and reads its own time from it.

```bash
ros2 topic echo /clock --once
ros2 topic hz /clock
gz topic -e -t /world/myWorld/stats -n 1
```

The last command prints Gazebo's own numbers: `sim_time`, `real_time`, `real_time_factor`, `paused`, `iterations`. Use your real world name instead of `myWorld`.

One startup rule: if Gazebo sees another publisher on `/clock` when it starts, it publishes only `/world/<world_name>/clock`. Then bridge that topic instead.

## 3. use_sim_time belongs to each node

`use_sim_time` is a normal ROS 2 parameter. Its default is false, and it is set per node. There is no global switch. These are the four ways to set it:

| Where                      | How                                                                | Use it for                      |
| -------------------------- | ------------------------------------------------------------------ | ------------------------------- |
| One node, command line     | `--ros-args -p use_sim_time:=true`                                 | Quick tests                     |
| Parameter file, many nodes | `/**:` then `ros__parameters:` then `use_sim_time: true`           | Fixed setups                    |
| Launch file                | `SetParameter(name='use_sim_time', value=True)` before the nodes   | The normal way                  |
| Nodes inside Gazebo        | `use_sim_time: true` under `controller_manager` in your YAML       | `gz_ros2_control` (lesson 3b)   |

```yaml
/**:
  ros__parameters:
    use_sim_time: true
```

The wildcard `/**` matches every node. Your `controllers.yaml` already has the last row. The controllers copy that value, which you saw in the log as `-p use_sim_time:=true`.

Check any node:

```bash
ros2 param get /robot_state_publisher use_sim_time
ros2 param get /controller_manager use_sim_time
```

The rule is all or none. Every node that handles robot data must agree. One node on the wrong clock is the most common time bug.

What if `/clock` is missing? A node with `use_sim_time` true waits at time zero. Its timers never fire and its TF lookups fail. It looks frozen but it is only waiting for a clock.

## 4. Why a mismatch hurts

Three places show it.

**Timers.** With sim time, `create_timer(1.0, ...)` means one simulated second. Pause Gazebo and the timer stops. Run at half speed and it fires every two wall seconds. That is the right behavior for a robot, and you will see it in the practical.

**Timestamps.** Every bridged sensor message carries a sim-time stamp. Sim time starts near zero when Gazebo starts. Wall time is about 1.7 billion seconds since 1970. A node on wall time sees a sim stamp as decades old. Message filters and TF then reject the data.

**TF.** `robot_state_publisher` stamps the moving-joint transforms with the time of the joint state message, so they carry sim time. TF looks up a transform by time. A node on the wrong clock asks for a time that is not in the buffer and gets an extrapolation error. If you press Gazebo's reset button, sim time jumps back to zero. TF clears its buffers when time jumps back. Restart your nodes after a reset.

## 5. Speed of the simulation

Two numbers from lesson 1 set the speed: `max_step_size` (how much time one step simulates) and `real_time_factor` (the target speed, 1.0 means real time). Gazebo shows the actual factor as a percent at the bottom of the 3D view, for example 56 %. Below 100 % the simulation is slower than real time.

You can change the target while it runs. The world needs the user-commands system, which yours has:

```bash
gz service -s /world/myWorld/set_physics \
  --reqtype gz.msgs.Physics \
  --reptype gz.msgs.Boolean \
  --timeout 2000 \
  --req 'real_time_factor: 0.5'
```

The target caps the speed. A fast computer is slowed to half real time, a slow one cannot go above what it can compute.

## 6. Robot v2: a link and a joint for every sensor

In lesson 4 all three sensors hung on `base_link`. Now each sensor has its own link with a shape, joined to `base_link` by a joint, and `<gazebo reference="...">` names that sensor link.

| Part   | Link            | Shape                       | Joint                | Type                     | Joint origin from base_link | Sensor pose in its link |
| ------ | --------------- | --------------------------- | -------------------- | ------------------------ | --------------------------- | ----------------------- |
| IMU    | `imu_link`      | box 2 x 2 x 1 cm            | `imu_joint`          | fixed                    | `0 0 0.055`                 | `0 0 0`                 |
| Lidar  | `lidar_link`    | cylinder r 3 cm, h 6 cm     | `lidar_joint`        | fixed                    | `-0.05 0 0.08`              | `0 0 0.02`              |
| Camera | `camera_link`   | box 3 x 5 x 3 cm and a lens | `camera_pan_joint`   | revolute, z axis, +-1.57 | `0.12 0 0.05`               | `0.02 0 0.015`          |

Why build it this way:

1. The joint origin is the one place that says where a sensor sits. The sensor's own `<pose>` only covers the offset inside its link, like the lens tip. Move a sensor by editing one joint.
2. The link is the TF frame. `imu_link`, `lidar_link` and `camera_link` will appear in `/tf`. Lesson 6 needs them for RViz2.
3. A shape makes the sensor visible and gives it mass and collision. The numbers are chosen so the lidar scan plane (z = 0.10) clears the chassis top (0.05) and the camera top (0.08).
4. A movable mount needs a child link that can move. A camera attached to `base_link` could never pan.

All inertias were computed with the solid-shape formulas from the `urdf-inertia` snippet note. The base and wheel values are the ones you already had.

```xml
<joint name="camera_pan_joint" type="revolute">
    <parent link="base_link"/>
    <child link="camera_link"/>
    <origin xyz="0.12 0 0.05" rpy="0 0 0"/>
    <axis xyz="0 0 1"/>
    <limit lower="-1.57" upper="1.57" effort="1.0" velocity="2.0"/>
    <dynamics damping="0.01" friction="0.0"/>
</joint>

<gazebo reference="camera_link">
    <sensor name="camera_sensor" type="camera">
        <pose>0.02 0 0.015 0 0 0</pose>
        <topic>camera</topic>
        <gz_frame_id>camera_link</gz_frame_id>
        <!-- camera block as in lesson 4 -->
    </sensor>
</gazebo>
```

**Fixed joints get merged.** When Gazebo builds its model from a URDF, it merges two links joined by a fixed joint into one link. A sensor on a merged link is moved into the parent with the right offset, so it still works, but the sensor link disappears from the Entity Tree. The robot file keeps `imu_link` and `lidar_link` alive with `preserveFixedJoint` on their joints:

```xml
<gazebo reference="imu_joint"><preserveFixedJoint>true</preserveFixedJoint></gazebo>
```

The caster stays merged because nothing needs it. The camera joint is revolute, so it is never merged.

**The frame_id of sensor data.** `<gz_frame_id>` is read by Gazebo's sensor code and becomes the `frame_id` in every message header. Without it the frame_id is the sensor's name as Gazebo knows it, often a long `model/link/sensor` path that matches no URDF frame. It is a Gazebo tag, not part of the SDF spec, so a strict checker may warn about it.

## 7. The movable camera

The pan joint is a third joint under `ros2_control`, with a **position** command instead of velocity:

```xml
<joint name="camera_pan_joint">
    <command_interface name="position"/>
    <state_interface name="position">
        <param name="initial_value">0.0</param>
    </state_interface>
    <state_interface name="velocity"/>
</joint>
```

In `controllers.yaml` it needs a controller. A group position controller is the simplest one:

```yaml
controller_manager:
  ros__parameters:
    camera_pan_controller:
      type: position_controllers/JointGroupPositionController

camera_pan_controller:
  ros__parameters:
    joints:
      - camera_pan_joint
```

Then spawn it like the other two. It listens on `/camera_pan_controller/commands` for a `Float64MultiArray` with one angle in radians.

How Gazebo turns a position command into motion: the plugin sets the joint velocity to `gain x update_rate x (target - position)`. The gain is `position_proportional_gain` (0.1 unless you change it) and the update rate is the controller manager's, 100 Hz in your file. So each control cycle closes about a tenth of the remaining error and the camera settles in a fraction of a second. Below 1 there is no overshoot, and 2 is the stability limit.

Two details from the plugin code:

- Before `camera_pan_controller` is active, `hold_joints` (default true) holds the joint still with a zero velocity command. The camera stays at its start angle until the controller takes over.
- `initial_value` sets the start angle of the joint.

## 8. Common traps

| Symptom                                                        | Usual cause                                                                                   |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| A node with `use_sim_time` true never runs its timer           | `/clock` is not bridged, or Gazebo is paused                                                  |
| Timestamps look decades old, TF lookups or filters reject data | One node is on wall time while the data has sim time. Check each node with `ros2 param get`   |
| Everything freezes when you press pause in Gazebo              | Expected. Sim time stopped, so every sim-time node stopped                                    |
| A 1 second timer fires every 2 seconds                         | Real time factor is 50 %. Timers count simulated seconds                                      |
| Warnings about a jump back in time                             | You pressed reset. Sim time returned to 0. Restart the nodes                                  |
| `/clock` is missing but Gazebo runs                            | The bridge is not running, or another node already publishes `/clock`                         |
| Sensor `frame_id` is a long path                               | No `<gz_frame_id>` in the sensor                                                              |
| The camera does not pan                                        | `camera_pan_controller` not spawned. Check `ros2 control list_controllers`                    |
| A sensor link is missing in the Entity Tree                    | Its fixed joint was merged. Add `preserveFixedJoint`                                          |

## Practical: a robot with sensor links and a movable camera, on sim time

Files in `05_sim_time/workarea/`: `myWorld.sdf`, `robot.urdf`, `controllers.yaml`, `bridge.yaml`, `teleop_params.yaml`, `time_probe.py` and `bringup.launch.py`.

- Put the real path of `controllers.yaml` into the URDF. The file keeps a placeholder:

```bash
cd 05_sim_time/workarea
sed -i "s|/absolute/path/to/controllers.yaml|$PWD/controllers.yaml|" robot.urdf
```

- Start everything, in separate terminals, from `workarea`:

```bash
gz sim -r myWorld.sdf
```

```bash
ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=$PWD/bridge.yaml
```

```bash
ros2 run robot_state_publisher robot_state_publisher \
  --ros-args -p use_sim_time:=true \
  -p robot_description:="$(cat robot.urdf)"
```

```bash
ros2 run ros_gz_sim create -topic robot_description -name my_robot -z 0.3
ros2 run controller_manager spawner joint_state_broadcaster
ros2 run controller_manager spawner diff_drive_controller
ros2 run controller_manager spawner camera_pan_controller
```

The same thing in one command, with `use_sim_time` set once for all nodes by `SetParameter`:

```bash
ros2 launch $PWD/bringup.launch.py
```

- **See the clock.** Echo it, then press pause in Gazebo and echo again. The time stops. Press play and it moves.

```bash
ros2 topic echo /clock --once
ros2 topic hz /clock
```

- **Compare the clocks.** Run the probe twice in two terminals and read the lines:

```bash
python3 time_probe.py
python3 time_probe.py --ros-args -p use_sim_time:=true
```

The first shows `ros_time` close to `wall_time` and about 1 second between lines. The second shows a small `ros_time` that follows Gazebo. Now press pause. The second probe prints nothing until you press play, then one line with a big `wall_seconds_since_last_tick`. Then set half speed and watch the gap grow to about 2 seconds:

```bash
gz service -s /world/myWorld/set_physics --reqtype gz.msgs.Physics \
  --reptype gz.msgs.Boolean --timeout 2000 --req 'real_time_factor: 0.5'
```

Set it back with `real_time_factor: 1.0`. For a last experiment stop the bridge terminal with Ctrl+C. The sim-time probe stops, because `/clock` stopped. Start the bridge again and it continues.

- **Look at the stamps and frames.** Sensor data carries sim time, and the frame_id is the sensor link:

```bash
ros2 topic echo /imu --field header.stamp --once
ros2 topic echo /clock --once
date +%s
ros2 topic echo /imu --field header.frame_id --once
ros2 topic echo /camera/image_raw --field header.frame_id --once
```

The IMU stamp is close to the `/clock` value. `date +%s` is a huge number. These two can never be compared. The frame_ids should read `imu_link` and `camera_link`.

- **Move the camera.** Open the image and turn the camera. From the start pose, the blue box is about 28 degrees to the left and the orange post about 40 degrees to the right:

```bash
ros2 run rqt_image_view rqt_image_view
```

```bash
ros2 topic pub --once /camera_pan_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.5]}"
ros2 topic pub --once /camera_pan_controller/commands std_msgs/msg/Float64MultiArray "{data: [-0.7]}"
ros2 topic pub --once /camera_pan_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.0]}"
```

Pick `/camera/image_raw` in `rqt_image_view`. While the camera turns, watch the transform change:

```bash
ros2 run tf2_ros tf2_echo base_link camera_link
```

- **Drive and pan together.** Use the teleop command from lesson 3b with `teleop_params.yaml`, and check the three controllers with `ros2 control list_controllers`.
- **Build it yourself with your snippets.** Try writing the camera part by hand: `urdf-link-full`, `urdf-joint-revolute`, `urdf-ros2control-joint` with `urdf-command-interface` and `urdf-state-interface-initial-value`, `urdf-gazebo-sensor-camera`, then in YAML `cm-controller-type` and `jgpc-full`.

## Updated folder for this lesson

```txt
05_sim_time/
├── workarea/
│   ├── myWorld.sdf
│   ├── robot.urdf              # v2: sensor links, camera pan joint
│   ├── controllers.yaml        # + camera_pan_controller
│   ├── bridge.yaml
│   ├── teleop_params.yaml
│   ├── time_probe.py
│   └── bringup.launch.py
└── info_5.md
```
