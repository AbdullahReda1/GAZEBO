# Lesson 2: ROS 2 & Gazebo Harmonic Bridge Architecture

Key architectural breakthroughs, traps, and configurations established during the implementation of the `ros_gz_bridge`.

---

## 1. Environment Variable Matching & Linting

* **The Standalone Linter Trap:** The offline syntax checker `gz sdf -k` strictly queries the legacy `SDF_PATH` variable. The runtime simulator utilizes the modern `GZ_SIM_RESOURCE_PATH` variable instead.
* **The Definitive Resolution:** To prevent missing fallback error flags (`sdf::setFindCallback()` empty / Unable to find uri) during syntax audits, both variables must be explicitly bound inside `~/.bashrc`:

  ```bash
  export GZ_SIM_RESOURCE_PATH=$HOME/gz_models:$GZ_SIM_RESOURCE_PATH
  export SDF_PATH=$GZ_SIM_RESOURCE_PATH
  ```

---

## 2. Bridge Configuration & CPU Management

* **Direction Constraints:** ROS 2 message definitions or Protobuf formats do not dictate transmission flow. Flow direction is an engineering layout configuration set inside the bridge instance depending on who owns the publisher.
* **One-Way Traffic Efficiency:** Restrict channels strictly to one-way directions (`GZ_TO_ROS` for sensors/clock, `ROS_TO_GZ` for `cmd_vel`).
* **The CPU & Loop Hazard:** Enabling bidirectional bridging (`@`) on channels that only need one-way flow wastes host CPU execution threads and causes catastrophic feedback loops on navigation layers like odometry, causing robots to bounce or glitch as nodes echo data back to its source.
* **Typo Exits:** A typo or case-sensitivity mismatch in either the ROS 2 or Gazebo type string inside commands or YAML maps will cause the bridge node to immediately shut down upon launching to protect system data integrity.

---

## 3. Kinematic Frames & Global Tracking Resolution

* **The Local Relative Trap:** Inside the modern `PosePublisher` plugin architecture, enabling `<publish_link_pose>true</publish_link_pose>` inside a single rigid `<model>` structure only tracks the child link relative to the local parent model frame. This outputs static `0.0` vectors regardless of the robot's physical altitude in the simulation world.

* **The Definitive Solution for Absolute Tracking:** To capture absolute altitude vectors over the global ground plane on the direct `/model/model_name/pose` topic without altering standard bridge message types, explicit configuration switches must be applied inside the model's `<plugin>` configuration parameters:

  ```xml
  <plugin filename="gz-sim-pose-publisher-system" name="gz::sim::systems::PosePublisher">
      <publish_model_pose>true</publish_model_pose>      <!-- Force world-frame global mapping -->
      <publish_link_pose>false</publish_link_pose>       <!-- Mute relative link identity frames -->
      <publish_collision_pose>false</publish_collision_pose>
      <publish_visual_pose>false</publish_visual_pose>
      <publish_nested_models>true</publish_nested_models>
      <use_pose_vector_msg>false</use_pose_vector_msg>    <!-- Keep standard geometry_msgs/msg/PoseStamped -->
      <update_frequency>50</update_frequency>             <!-- Cap transmission rates to preserve CPU cycles -->
  </plugin>
  ```
