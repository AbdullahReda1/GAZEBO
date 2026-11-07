
# Sim Time & Dynamic Sensors

This note documents the architectural rules, debugging discoveries, and orchestration patterns mastered in Session 5 for **ROS 2 Jazzy** and **Gazebo Harmonic**.

## 1. Simulation Time & The Three Clocks (`/clock`)

* **The Heartbeat:** Gazebo publishes one message per physics step (`step_size: 1ms` = `1000Hz`) on the `/clock` topic.
* **The Three Time Domains:**
  * **Sim Time:** Virtual world clock; pauses/scales with simulation speed. Used by all sensor headers.
  * **Real Time:** Actual elapsed processing time since pressing Play (used to compute the `real_time_factor`).
  * **System Time:** Host OS wall clock (Unix Epoch time).
* **Global Time Sync (`SetParameter`):** Placing `SetParameter(name='use_sim_time', value=True)` at the top of `bringup.launch.py` forces every subsequent ROS 2 node in the launch description to synchronize with `/clock` automatically.
* **Bridge QoS Profile:** The `/clock` bridge entry must explicitly specify `qos_profile: CLOCK` to enforce high reliability and transient local durability, preventing timestamp jitter or startup deadlocks.

## 2. Structural URDF Rules: Visual Sensors & Kinematic Frames

* **Joint vs. Link Separation (`<gazebo reference="...">`):** A single `<gazebo>` tag can only target one entity name. Therefore, joint-level settings and link-level sensors must remain strictly separated:
  * **Preventing Fixed Joint Lumping:** Gazebo merges fixed joints into their parent link (`base_link`) by default, erasing child links from the Entity Tree and breaking TF trees for RViz2. Use `<gazebo reference="imu_joint"><preserveFixedJoint>true</preserveFixedJoint></gazebo>` to keep sensor frames alive.
  * **Explicit TF Frame Alignment (`<gz_frame_id>`):** Add `<gz_frame_id>link_name</gz_frame_id>` inside `<sensor>` blocks to override Gazebo's long default paths (`model/link/sensor`), ensuring clean, matching `frame_id` headers for downstream RViz2/Nav2 stacks.
* **Physical Clearances:** Sensor joint origins are calculated explicitly so the Lidar scan plane (`z = 0.10m`) clears both the chassis top (`0.05m`) and the camera housing (`0.08m`).

## 3. Movable Camera & `ros2_control` Parameter Hygiene

* **Dynamic Pan Control:** Mounting the camera on a `revolute` joint (`camera_pan_joint`, limits `±1.57 rad`) controlled via `position_controllers/JointGroupPositionController` enables live pan actuation via `std_msgs/msg/Float64MultiArray` on `/camera_pan_controller/commands`.
* **Proportional Control Loop:** Gazebo converts position commands into joint velocities using `Gain (0.1) * Update Rate (100Hz) * Position Error`, settling smoothly without overshoot (`Gain < 1.0`, instability limit at `2.0`).
* **Strict `controllers.yaml` Hygiene:**
  * Only `update_rate` and `use_sim_time` belong under `controller_manager: ros__parameters:`.
  * `hold_joints` (default `true`, locks joints at zero velocity before controllers spawn) belongs inside the `<plugin>` block in `robot.urdf` (`<hold_joints>true</hold_joints>`), **not** in the YAML file.
  * Unknown parameters (`ros_distro`, `robot_description`, `use_global_arguments`) are silently ignored by Jazzy's `controller_manager`.

## 4. YAML Structures & CLI / Launch Best Practices

* **YAML File Schemas:**
  * **Lists (`-`):** Used for repeated independent mappings (e.g., `bridge.yaml` topic arrays).
  * **Maps (`/` or Node Name):** Used for hierarchical node parameter trees (e.g., `controllers.yaml`, `teleop_params.yaml`).
* **Standalone Execution & Path Injection:** Standalone folders work outside formal `ament` ROS 2 packages without `get_package_share_directory()` by resolving relative paths dynamically via `os.path.dirname(os.path.realpath(__file__))` and string-replacing placeholder paths inside the URDF at runtime.
* **Spawning Multiple Controllers:**
  * **Best Practice:** Pass all controller names to a single spawner instance (`ros2 run controller_manager spawner joint_state_broadcaster diff_drive_controller camera_pan_controller`).
  * **Chaining Trap:** Using `&&` halts execution if an earlier spawner delays/fails; use `;` if chaining separate commands.
* **GUI & Debugging Utilities (`rqt` & Shell):**
  * `teleop_twist_keyboard` only publishes `Twist`/`TwistStamped`; use `rqt_publisher` (or a dedicated custom node) to publish `Float64MultiArray` angles to the camera.
  * Use `ros2 param list /controller_manager` to verify valid parameters on the live system.
  * **Filename Hygiene:** Hidden spaces in filenames (e.g., `bringup.launch .py`) break standard CLI execution and require shell escaping (`\ .py`) or renaming via `mv`.
