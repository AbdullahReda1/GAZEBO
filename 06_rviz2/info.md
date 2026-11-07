# RViz2 Alongside Gazebo

Session 6 of 7. Broad pass. It uses robot v2 from lesson 5, plus one small addition: a camera optical frame.

## 1. Two windows, two jobs

Gazebo and RViz2 both show a robot, but they show different things.

| Window     | What it shows                                   | Where the data comes from |
| ---------- | ----------------------------------------------- | ------------------------- |
| Gazebo GUI | The simulated world as it really is (the truth) | The physics engine        |
| RViz2      | What your ROS 2 nodes receive and believe       | ROS 2 topics and TF only  |

RViz2 is a normal ROS 2 node. It cannot see a gz topic, the same rule as in lesson 2. If a sensor is not bridged, RViz2 shows nothing for it, even when Gazebo shows it. That makes RViz2 a good test for your whole chain: sensor, bridge, TF, clock.

## 2. TF: the tree RViz2 needs

TF is the tree of coordinate frames. RViz2 draws everything by looking up where each frame sits. For your robot the tree is built by three publishers:

| Transform                                                            | Published by                                      | Topic          |
| -------------------------------------------------------------------- | ------------------------------------------------- | -------------- |
| `odom` to `base_link`                                                | `diff_drive_controller` (`enable_odom_tf`)        | `/tf`          |
| `base_link` to the wheels and `camera_link` (moving joints)          | `robot_state_publisher`, from `/joint_states`     | `/tf`          |
| `base_link` to `imu_link`, `lidar_link`, caster (fixed joints)       | `robot_state_publisher`                           | `/tf_static`   |

Two things follow from this. First, `robot_state_publisher` reads the URDF, so every link in the URDF is in the tree, even the ones Gazebo merged. Second, the moving camera works for free: the pan joint changes in `/joint_states`, and the camera frame moves in TF.

**Fixed Frame** is the frame RViz2 treats as standing still. The default is `map`, which your robot does not have. Set it to:

- `odom` if you want to watch the robot drive through the world. This is the usual choice.
- `base_link` if you want the robot to stay still and the world to move.

To see the whole tree as a picture:

```bash
ros2 run tf2_tools view_frames
```

## 3. Sensor frames and the optical frame

Every sensor message has a `frame_id` in its header. RViz2 uses it to place the data. In lesson 5 you set `gz_frame_id` on each sensor, so the frame names now match URDF links.

ROS has two frame conventions for a camera:

| Frame           | x       | y    | z       | Used for                         |
| --------------- | ------- | ---- | ------- | -------------------------------- |
| `camera_link`   | forward | left | up      | The body of the camera (REP 103) |
| optical frame   | right   | down | forward | Image data, camera info, depth   |

Image tools expect the optical frame. So add one empty link, joined to `camera_link` with a fixed joint turned by `-90 0 -90` degrees, and point the camera's `gz_frame_id` at it:

```xml
<link name="camera_optical_frame"/>
<joint name="camera_optical_joint" type="fixed">
    <parent link="camera_link"/>
    <child link="camera_optical_frame"/>
    <origin xyz="0.02 0 0.015" rpy="-1.5708 0 -1.5708"/>
</joint>
```

```xml
<gz_frame_id>camera_optical_frame</gz_frame_id>
```

The origin is the lens position, the same as the camera sensor pose. The lidar and the IMU keep `lidar_link` and `imu_link`, because their axes already follow the ROS convention. The `robot.urdf` in the lesson folder already has these changes.

## 4. The displays you will add

Use the Add button in RViz2, then pick the display type.

| Display    | Topic or setting                         | What to look for                                                  |
| ---------- | ---------------------------------------- | ----------------------------------------------------------------- |
| RobotModel | Description Topic `/robot_description`   | The robot with its shapes. The camera turns when you pan it       |
| TF         | Show Names on                            | Frames `odom`, `base_link`, `imu_link`, `lidar_link`, ...         |
| LaserScan  | `/scan`, Size (m) about 0.03             | Points where the lidar hits the box and the post                  |
| Image      | `/camera/image_raw`                      | The camera picture, same as `rqt_image_view`                      |
| Odometry   | `/diff_drive_controller/odom`            | Arrows that follow the robot as it drives                         |

If RobotModel is empty, open its Description Topic settings and set Durability Policy to Transient Local. `robot_state_publisher` publishes the description once and keeps it for late listeners, so RViz2 must ask for it in the same way.

RViz2 has no IMU display by default. Read the IMU with `ros2 topic echo /imu`.

## 5. RViz2 needs sim time too

This is lesson 5 again. RViz2 is a node with its own `use_sim_time`, default false. The sensor messages carry sim time, so RViz2 must run on sim time as well:

```bash
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true
```

If you forget, RViz2 prints errors like these and shows no sensor data:

```text
Message Filter dropping message: frame 'lidar_link' at time 12.3 for reason 'the timestamp on the message is earlier than all the data in the transform cache'
```

That sentence means: the data is stamped with sim time, but RViz2 asks TF for a wall-clock time.

## 6. Save the setup

Set up the displays once, then save: File, Save Config As, `robot.rviz`. Open it later with:

```bash
ros2 run rviz2 rviz2 -d robot.rviz --ros-args -p use_sim_time:=true
```

In `bringup.launch.py` the `SetParameter` action already makes RViz2 use sim time. The launch file in the lesson folder starts RViz2 with `robot.rviz` when that file exists.

## 7. Common traps

| Symptom                                                        | Usual cause                                                                    |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `Fixed Frame [map] does not exist`                             | Default Fixed Frame. Change it to `odom`                                       |
| `No transform from [lidar_link] to [odom]`                     | `robot_state_publisher` or the controllers are not running, or time mismatch   |
| `Message Filter dropping message ... earlier than ... cache`   | RViz2 is on wall time. Start it with `use_sim_time:=true`                      |
| RobotModel is empty or all white                               | Durability Policy must be Transient Local, or the Description Topic is wrong   |
| Robot model is there but stays at the origin                   | Fixed Frame is `base_link`. Choose `odom` to see it drive                      |
| LaserScan or Image shows nothing                               | The topic is not bridged, or a QoS mismatch. Check `ros2 topic hz` first       |
| Scan points are in the wrong place or turned                   | The `frame_id` does not match the sensor link (`gz_frame_id`)                  |
| Camera picture is fine but depth or camera info looks wrong    | Image is not in the optical frame                                              |

## Practical: see your robot in RViz2

Files in `06_rviz2/workarea/`: everything from lesson 5, with `robot.urdf` updated (camera optical frame) and `bringup.launch.py` now starting RViz2.

- Copy the lesson 5 folder, replace `robot.urdf` and `bringup.launch.py`, and set the controllers path again:

```bash
cd 06_rviz2/workarea
sed -i "s|/absolute/path/to/controllers.yaml|$PWD/controllers.yaml|" robot.urdf
```

- Start the simulation as in lesson 5 (the five commands, or `ros2 launch $PWD/bringup.launch.py`). If you use the launch file, RViz2 opens by itself with an empty setup.
- Start RViz2 by hand if you did not use the launch file:

```bash
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true
```

- Set Fixed Frame to `odom`. Add RobotModel, TF, LaserScan, Image and Odometry from the table in section 4.
- Check the tree and the frame names:

```bash
ros2 run tf2_tools view_frames
ros2 topic echo /camera/image_raw --field header.frame_id --once
```

The tree should show `odom`, then `base_link`, then the wheels, `imu_link`, `lidar_link` and `camera_link`, with `camera_optical_frame` under `camera_link`. The frame_id of the image should read `camera_optical_frame`.

- Drive with the teleop from lesson 3b. Watch the robot move in `odom`, the scan points stay on the box, and the Odometry arrows follow.
- Pan the camera, as in lesson 5, and watch the camera model turn in RobotModel while the Image display shows the new view:

```bash
ros2 topic pub --once /camera_pan_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.5]}"
```

- Break it on purpose. Close RViz2 and start it again without `use_sim_time:=true`. Read the errors. Then start it correctly and save your setup as `robot.rviz`.

## Updated folder for this lesson

```txt
06_rviz2/
├── workarea/
│   ├── myWorld.sdf
│   ├── robot.urdf              # + camera_optical_frame
│   ├── controllers.yaml
│   ├── bridge.yaml
│   ├── teleop_params.yaml
│   ├── time_probe.py
│   ├── bringup.launch.py       # + rviz2 node
│   └── robot.rviz              # you save this in step 8
└── info_6.md
```
