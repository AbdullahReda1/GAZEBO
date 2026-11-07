# RViz2 Alongside Gazebo Harmonic

## 1. Gazebo vs. RViz2: Two Windows, Two Jobs

* **Gazebo GUI (Ground Truth):** Renders the simulated world directly from the physics engine (`ogre2`).
* **RViz2 (Robot's Belief):** A standard ROS 2 node that visualizes **only** what is bridged and published over ROS 2 topics and `/tf` / `/tf_static`. If a sensor is not bridged, RViz2 cannot see it.

---

## 2. TF Coordinate Tree & Publishers

The complete robot TF tree is constructed by two nodes across three transform groups:

| Transform Chain | Publisher Node | Topic | Update Behavior |
| :--- | :--- | :--- | :--- |
| `odom` -> `base_link` | `diff_drive_controller` (`enable_odom_tf`) | `/tf` | Dynamic (~50 Hz in sim) |
| `base_link` -> `left_wheel_link`, `right_wheel_link`, `camera_link` | `robot_state_publisher` (from `/joint_states`) | `/tf` | Dynamic (~19 Hz in sim) |
| `base_link` -> `imu_link`, `lidar_link`, `caster_wheel_link` | `robot_state_publisher` (from URDF) | `/tf_static` | Static (latched once) |
| `camera_link` -> `camera_optical_frame` | `robot_state_publisher` (from URDF) | `/tf_static` | Static (latched once) |

* **Why merged Gazebo links still appear in TF:** `robot_state_publisher` reads the URDF directly—independent of Gazebo's fixed-joint lumping—so every URDF link appears in `/tf_static`.
* **Fixed Frame in RViz2:**
  * Set to **`odom`** to watch the robot drive across the world.
  * Set to **`base_link`** to keep the robot stationary at the center while the world moves around it.

---

## 3. Camera Frames: `camera_link` vs. `camera_optical_frame`

Separating the mechanical mounting frame from the optical measurement frame is an industry-wide sensor engineering standard:

| Frame | Axis Convention | Standard | Purpose |
| :--- | :--- | :--- | :--- |
| `camera_link` | **X:** Forward, **Y:** Left, **Z:** Up | REP 103 (Robotics Body) | Physical mounting, CAD, and URDF kinematics. |
| `camera_optical_frame` | **X:** Right, **Y:** Down, **Z:** Forward | Computer Vision / OpenCV | Image pixel coordinates, `CameraInfo`, and 3D depth projection. |

* **URDF Optical Joint:** Attached to `camera_link` with `rpy="-1.5708 0 -1.5708"` (`-90° 0° -90°`).
* **Single `<gz_frame_id>` Rule:** Never put two `<gz_frame_id>` tags inside one `<sensor>`. Keep `<gazebo reference="camera_link">` for physical placement, and set **only** `<gz_frame_id>camera_optical_frame</gz_frame_id>` so image headers carry the optical frame ID.

---

## 4. Quality of Service (QoS) Key Takeaways

* **Durability Policy (`Transient Local` vs. `Volatile`):**
  * `robot_state_publisher` publishes `/robot_description` **once** with `Transient Local` durability (keeping a saved copy for late subscribers).
  * RViz2's `RobotModel` defaults to `Volatile` (listening only for new messages). Setting it to **`Transient Local`** allows RViz2 to receive the saved URDF immediately upon startup.
* **History & Depth QoS:**
  * When `History Policy` is **Keep Last**, **Depth** defines the queue size (how many recent messages ROS 2 buffers in memory before overwriting the oldest ones).
  * Small depths (`1–5`) keep high-rate sensor streams (camera, lidar) fresh without lag; larger depths (`10+`) prevent dropping bursty commands.

---

## 5. Simulation Time (`use_sim_time`) Synchronization

* RViz2 and CLI tools default to wall-clock time (`use_sim_time:=false`), whereas bridged sensor data carries Gazebo simulation timestamps.
* **Timestamp Mismatch Error:**
  `Message Filter dropping message: frame 'lidar_link' at time 12.3 for reason 'the timestamp on the message is earlier than all the data in the transform cache'`
  * **Meaning:** Sensor messages are stamped with simulation time, while RViz2 is querying TF using system wall-clock time.
* **Launch Command (Manual):**

```bash
ros2 run rviz2 rviz2 -d robot.rviz --ros-args -p use_sim_time:=true
```

  *(Handled automatically in `bringup.launch.py` via `SetParameter(name='use_sim_time', value=True)`.)*

---

## 6. RViz2 Displays & Useful CLI Commands

* **Configured Displays (`robot.rviz`):**
  * **RobotModel:** Topic `/robot_description` (`Durability: Transient Local`)
  * **TF:** Visualizes `odom -> base_link -> ... -> camera_optical_frame`
  * **LaserScan:** Topic `/scan` (`Size (m): 0.03` recommended for visibility)
  * **Image:** Topic `/camera/image_raw`
  * **Odometry:** Topic `/diff_drive_controller/odom`
* **Generate & Rename TF Tree Diagrams:**

  ```bash
  # Generate with custom filename prefix (creates my_robot_tf.gv and my_robot_tf.pdf)
  ros2 run tf2_tools view_frames -o my_robot_tf --ros-args -p use_sim_time:=true
  ```

* **Verify Image Header Frame ID:**

  ```bash
  ros2 topic echo /camera/image_raw --field header.frame_id --once
  ```

* **Test Camera Pan Joint:**
  
  ```bash
  ros2 topic pub --once /camera_pan_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.5]}"
  ```
