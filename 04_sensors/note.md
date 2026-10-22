# Sensors Integration (IMU, Lidar, Camera)

This note logs the architectural rules, deployment discoveries, and critical takeaways from integrating sensor pipelines into ROS 2 Jazzy and Gazebo Harmonic.

## 1. Unified URDF Injection vs. Separation Rule

* **The Core Rule:** Model-level plugins (like gz_ros2_control) must live in a generic `<gazebo></gazebo>` tag. Link-level structural components (like physical sensors) must live inside a `<gazebo reference="link_name"></gazebo>` tag.
* **Merging Optimization:** Multiple sensors (imu, camera, gpu_lidar) can be cleanly nested inside a single, shared `<gazebo reference="base_link"></gazebo>` wrapper. This improves URDF readability while enforcing their unified transform attachment to the central chassis.

## 2. Global Namespace Behavior Discovery

* **Observation:** Running the standard spawn execution natively exposed topics on the root namespace directly (/imu, /scan, /camera, /camera_info), instead of being nested under a model path (e.g., /model/my_robot/imu).
* **Impact:** This simplifies the ros_gz_bridge launch configuration, allowing direct remapping and bridging without string concatenation or custom pattern matching for nested models.

## 3. Case-Sensitivity Traps (The IMU Case Study)

* **The Issue:** Attempting to run a bridge using `gz.msgs.Imu` resulted in a critical failure: No template specialization for the pair.
* **The Fix:** Gazebo Harmonic's message definition array is strictly case-sensitive. The shorthand token for Inertial Measurement Units must be written in full uppercase: `gz.msgs.IMU`.
* **Reference Table for Safe Bridging:**

Target SensorROS 2 Message TypeGazebo Transport TypeDirection
**IMU**
`sensor_msgs/msg/Imu` `gz.msgs.IMU` [ (Gz to ROS)
**Lidar**
`sensor_msgs/msg/LaserScan` `gz.msgs.LaserScan` [ (Gz to ROS)
**Camera (Raw)**
`sensor_msgs/msg/Image` `gz.msgs.Image` [ (Gz to ROS)
**Camera Info**
`sensor_msgs/msg/CameraInfo` `gz.msgs.CameraInfo` [ (Gz to ROS)

## 4. Live Telemetry Data Verification (What the Bytes Mean)

* **Physical Gravity (IMU):** When static, linear_acceleration.z accurately outputs ~9.81 m/s². This confirms the world-level physics system (gz-sim-physics-system) is successfully interacting with the model.
* **Laser Out-of-Bounds (Lidar):** The appearance of .inf elements in the ranges array is normal behavior. It signifies that specific laser rays traveled into empty space without striking an obstacle within the maximum specified `<range></range><max></max>` threshold (10.0m).
* **Chassis Occlusion Avoidance (Camera):** Pushing the camera component forward on the x-axis (`<pose>0.15 0 0.05 0 0 0</pose>`) shifts the rendering origin out of the interior body collision box, ensuring a clean field of view rather than a solid black matrix.

## 5. Automated Coordinate Frames (TF)

* **Observation:** The bridge natively populates frame_id fields following an explicit nested path scheme: my_robot/base_link/imu_sensor, my_robot/base_link/lidar_sensor, and my_robot/base_link/camera_sensor.
* **Impact:** This natively sets up our coordinate stack for downstream navigation or SLAM (Nav2) packages, ensuring clear kinematic transforms back to the absolute center of mass.

## 6. Sensor Visibility vs. Data Generation (Visual Body Separation)

* **The Rule:** The `<sensor>` tag inside a `<gazebo>` block handles **only** the mathematical and data-generation pipelines (publishing topics, update rates, FOV). It does not generate any 3D geometry in the simulator window.
* **The Symptom:** Sensors generate correct data arrays, but their physical mounts or housings are completely invisible in the Gazebo GUI.
* **The Fix:** To make a sensor visible, you must explicitly model it as a standard URDF `<link>` with `<visual>` and `<collision>` geometries, attach it to the chassis via a fixed `<joint>`, and update the `<gazebo reference="...">` attribute to target this new specific link name.
