# Sensors — IMU, Lidar, Camera

Session 4 of 7. Broad pass. This builds on the same two-wheeled `robot.urdf` from lessons 3 and 3b.

## 1. Two different sensor systems, not one

Lesson 1 foreshadowed this: "The IMU has its own system, `gz-sim-imu-system`." Now it matters. Gazebo splits sensors into two families, by whether they need to render a scene.

Camera and lidar both work by drawing the world from the sensor's point of view, one as a picture, the other as a grid of simulated laser rays. Both are handled by the one `gz-sim-sensors-system` plugin you already loaded into `my_world.sdf` back in lesson 1, with `render_engine` set to `ogre2`. You do not add anything new to the world file for these two.

An IMU does not render anything. It reads the physics engine directly for acceleration and angular velocity. Because of this, it needs its own small plugin, separate from the rendering pipeline. Add this to `my_world.sdf`, alongside your other world-level plugins:

```xml
<plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
```

| Sensor type | Needs rendering? | World-level plugin needed                              |
| ----------- | ---------------- | ------------------------------------------------------ |
| Camera      | Yes              | `gz-sim-sensors-system` (already in your world file)   |
| Lidar       | Yes              | `gz-sim-sensors-system` (already in your world file)   |
| IMU         | No               | `gz-sim-imu-system` (new, add it now)                  |

Magnetometer, altimeter, and air pressure sensors follow the IMU's pattern: each gets its own small world-level system, since none of them render a scene either. You will not need them today, but now you know where to look if a future sensor's data never shows up despite a correct `<sensor>` tag.

## 2. Attaching a sensor to a URDF link

Pure SDF puts a `<sensor>` tag directly inside a `<link>`, the way lesson 1 showed. URDF has no `<sensor>` tag at all — it is not part of the URDF spec. The way around this is the same escape hatch you already used for `<ros2_control>`'s Gazebo plugin: a `<gazebo reference="...">` block, naming the link the sensor belongs to.

```xml
<gazebo reference="base_link">
  <sensor name="imu_sensor" type="imu">
    <pose>0 0 0 0 0 0</pose>
    <always_on>true</always_on>
    <update_rate>100</update_rate>
    <topic>imu</topic>
  </sensor>
</gazebo>
```

The `reference` attribute is what makes this different from the plain `<gazebo>` block you already used for the `gz_ros2_control` plugin. Without it, Gazebo has no link to attach the sensor to. `<pose>` here is relative to that link, same rule as every pose you have written so far.

## 3. The camera

```xml
<gazebo reference="base_link">
  <sensor name="camera_sensor" type="camera">
    <pose>0.15 0 0.05 0 0 0</pose>
    <update_rate>30</update_rate>
    <topic>camera</topic>
    <camera>
      <horizontal_fov>1.047</horizontal_fov>
      <image>
        <width>640</width>
        <height>480</height>
      </image>
      <clip>
        <near>0.1</near>
        <far>100</far>
      </clip>
    </camera>
  </sensor>
</gazebo>
```

The pose pushes the camera forward (`0.15` on x) and slightly up, so it sits in front of the chassis instead of inside it. A camera positioned inside its own robot's body sees only the inside of that body — every frame solid black. `horizontal_fov` is in radians; `1.047` is 60 degrees. `clip` sets the near and far render distance, same idea as any 3D renderer: objects closer than `near` or farther than `far` are not drawn.

## 4. The lidar

```xml
<gazebo reference="base_link">
  <sensor name="lidar_sensor" type="gpu_lidar">
    <pose>0 0 0.1 0 0 0</pose>
    <update_rate>10</update_rate>
    <topic>scan</topic>
    <lidar>
      <scan>
        <horizontal>
          <samples>360</samples>
          <min_angle>-3.14159</min_angle>
          <max_angle>3.14159</max_angle>
        </horizontal>
      </scan>
      <range>
        <min>0.1</min>
        <max>10.0</max>
      </range>
    </lidar>
  </sensor>
</gazebo>
```

`type="gpu_lidar"` is the one to reach for by default. It uses the GPU to cast rays, the same way the camera does, which is why it needs the same `gz-sim-sensors-system` rather than a dedicated plugin of its own. `samples` is how many rays fire across the full sweep; `min_angle`/`max_angle` here cover a full 360-degree circle. `range` caps how far a ray can detect anything, in meters.

## 5. Topic names: let Gazebo tell you, don't guess

Lesson 1 already taught the real workflow here, and it applies again: check what topic actually exists before writing a bridge command, rather than assuming one. Setting `<topic>imu</topic>` gives Gazebo a hint, but the real, final topic name depends on how it gets scoped under the model. Confirm it directly:

```bash
gz topic -l | grep -E "imu|camera|scan"
```

Lesson 2's trap table said it plainly: a guessed topic name is the single most common reason a bridge silently does nothing. That is just as true for sensors as it was for the box's pose.

## 6. Bridging sensor data into ROS 2

These three message pairs were already in lesson 2's table; here they are again, now with a real use:

| ROS 2 type                    | GZ type               | Direction |
| ----------------------------- | --------------------- | --------- |
| `sensor_msgs/msg/Imu`         | `gz.msgs.IMU`         | GZ to ROS |
| `sensor_msgs/msg/Image`       | `gz.msgs.Image`       | GZ to ROS |
| `sensor_msgs/msg/LaserScan`   | `gz.msgs.LaserScan`   | GZ to ROS |

All three only ever need to flow one way, Gazebo to ROS, the same reasoning lesson 2 gave for `/clock`: nothing in ROS ever needs to command a sensor's raw reading back into the simulator.

## 7. Common traps

| Symptom                                          | Usual cause                                                                                      |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Camera or lidar topic exists but carries no data | `gz-sim-sensors-system` missing from `my_world.sdf`, or no `render_engine` set                   |
| IMU topic never appears at all                   | `gz-sim-imu-system` missing from `my_world.sdf` — a camera/lidar fix will not help this one      |
| Bridge runs, `ros2 topic echo` shows nothing     | Guessed the topic name instead of checking `gz topic -l` first                                   |
| Camera image is solid black every frame          | Camera pose places it inside the robot's own chassis geometry                                    |
| Lidar always reports the maximum range           | Nothing solid is close enough, or `<range><max>` is set too short                                |
| Sensor tag written, nothing changes              | Forgot the `<gazebo reference="link_name">` wrapper — a bare `<sensor>` is invalid in URDF       |

## Practical: add all three sensors to your robot

* Add the `gz-sim-imu-system` plugin to `my_world.sdf`, alongside your existing world plugins.

* Add the IMU, camera, and lidar blocks from sections 2 through 4 to `robot.urdf`, all referencing `base_link`.

* Run your usual stack: `robot_state_publisher`, `gz sim -r my_world.sdf`, the `/clock` bridge, then spawn:

```bash
ros2 run ros_gz_sim create -topic robot_description -name my_robot -z 0.3
```

* Find the real topic names:

```bash
gz topic -l | grep -E "imu|camera|scan"
```

* Bridge each one, using the types from section 6 and the real names from step 4. For example, if the IMU topic turns out to be `/model/my_robot/imu`:

```bash
ros2 run ros_gz_bridge parameter_bridge \
  /model/my_robot/imu@sensor_msgs/msg/Imu[gz.msgs.IMU
```

Repeat for the camera and lidar topics, with their own type pairs from the table.

* Check each one landed in ROS 2:

```bash
ros2 topic echo /model/my_robot/imu
ros2 run rqt_image_view rqt_image_view
ros2 topic echo /model/my_robot/scan
```

`rqt_image_view` is the easiest way to look at a bridged camera topic; `ros2 topic echo` on an image topic prints an unreadable wall of raw bytes. Pick the bridged camera topic from its dropdown once it opens. For the lidar, the `ranges` array in the echoed `LaserScan` message is what to watch — it should shrink wherever something solid is close to the robot, and read near the max range everywhere else.

## Updated folder for this lesson

```txt
04_sensors/
├── workarea/
│   ├── robot.urdf          # now includes IMU, camera, and lidar sensor blocks
│   ├── my_world.sdf        # now includes gz-sim-imu-system
│   └── controllers.yaml
└── info_4.md
```
