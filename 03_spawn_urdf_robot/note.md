
# Lesson 3 (A & B) Consolidated Reference Log: Robot Spawning & ros2_control Actuation

Comprehensive reference guide capturing the architectural layers, file structures, signal paths, execution setups, and common traps encountered when spawning and driving a URDF robot using `ros2_control` in **ROS 2 Jazzy Jalisco** and **Gazebo Harmonic**.

---

## 1. Core Architecture Layers & Philosophy

The robot control stack is built on three tightly coupled layers that manage hardware abstraction and execution:

| Layer                            | What it is                                                                              | Location                                                         |
| :------------------------------- | :-------------------------------------------------------------------------------------- | :--------------------------------------------------------------- |
| **`ros2_control`**               | Hardware abstraction standard. Declares the command and state contract.                 | Top-level `<ros2_control>` block in the `robot.urdf` file.       |
| **`gz_ros2_control`**            | The physical simulation bridge plugin that fulfills the contract using Gazebo joints.   | A `<gazebo><plugin>` wrapper block in the `robot.urdf` file.     |
| **`controller_manager`**         | The central broker node managing resource locks, loading, and running controller loops. | Instantiated automatically by the `gz_ros2_control` plugin.      |

* **The Chain Principle:** This stack functions sequentially from bottom to top. `ros2_control` acts as a pure contract ("this joint accepts velocity and reports position") without knowing anything about Gazebo. `gz_ros2_control` fulfills that contract by interfacing directly with Gazebo's internal **Entity-Component-System (ECS)**. `controller_manager` handles execution and joint allocations. It runs quietly in the background and is never invoked directly by hand.

---

## 2. Controller Specializations & Signal Path

### 2.1 The Two Core Controllers

Driving a mobile platform requires running two distinct types of controllers inside the `controller_manager` broker:

1. **`joint_state_broadcaster` (Read Only):** Periodically reads raw joint states from `gz_ros2_control` and outputs a unified `/joint_states` message. It causes no physical movement.
2. **`diff_drive_controller` (Read/Write):** Subscribes to velocity inputs, calculates the differential kinematics for wheel velocities, handles actuation commands, tracks position changes, and handles odometry feedback.

### 2.2 Complete Signal Control Chain

```txt
[User Input: TwistStamped]
          │
          ▼
[diff_drive_controller]  (Computes individual wheel kinematics)
          │
          ▼
[controller_manager]     (Routes commands & locks resource access)
          │
          ▼
[gz_ros2_control Interface] (Bypasses ROS network / Injects directly to ECS)
          │
          ▼
[Gazebo Physics Engine]  (Actuates mechanical wheel joints)
```

---

## 3. Verified Code Configurations

### 3.1 `robot.urdf` Elements

#### Hardware Interface Block

```xml
<ros2_control name="GazeboSimSystem" type="system">
    <hardware>
        <plugin>gz_ros2_control/GazeboSimSystem</plugin>
    </hardware>
    <joint name="left_wheel_joint">
        <command_interface name="velocity"/>
        <state_interface name="position"/>
        <state_interface name="velocity"/>
    </joint>
    <joint name="right_wheel_joint">
        <command_interface name="velocity"/>
        <state_interface name="position"/>
        <state_interface name="velocity"/>
    </joint>
</ros2_control>
```

#### Simulation Plugin Block

```xml
<gazebo>
    <plugin filename="gz_ros2_control-system" name="gz_ros2_control::GazeboSimROS2ControlPlugin">
        <parameters>$(find my_robot_bringup)/config/controllers.yaml</parameters>
    </plugin>
</gazebo>
```

### 3.2 `controllers.yaml` Structural Design

```yaml
controller_manager:
  ros__parameters:
    update_rate: 100
    use_sim_time: true

    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster
    diff_drive_controller:
      type: diff_drive_controller/DiffDriveController

diff_drive_controller:
  ros__parameters:
    left_wheel_names: ["left_wheel_joint"]
    right_wheel_names: ["right_wheel_joint"]
    wheel_separation: 0.34
    wheel_radius: 0.08
    publish_rate: 50.0
    odom_frame_id: odom
    base_frame_id: base_link
    enable_odom_tf: true
    use_stamped_vel: true
```

* **Nesting Trap Warning:** Parameter parsing in ROS 2 requires strict dictionary nesting. Controller `type:` definitions **must** live one level inside the `controller_manager` node's own `ros__parameters:` block. Placing a bare `type:` key on the file root level will crash `gz sim` immediately upon loading.

---

## 4. Crucial ROS 2 Jazzy Breaking Changes

* **Mandatory `TwistStamped` Enforcements:** On ROS 2 Jazzy, `diff_drive_controller` forces its input topic to use **`geometry_msgs/msg/TwistStamped`**.
* **The No-Op Parameter:** Setting `<use_stamped_vel: false>` inside your YAML file **no longer reverts** the topic format to plain unstamped `Twist` messages. It is effectively a no-op parameter that fails to construct any alternative unstamped `/cmd_vel_unstamped` interfaces. You must publish stamped messages from the beginning instead of fighting the pipeline.

---

## 5. Summary of Spawning Workflow Methods

Lesson 3 establishes 5 distinct methods to handle entity generation inside a simulation ecosystem:

1. **GUI Drag-In (Resource Spawner):** Quick manual testing without scripts using local resource paths or Fuel cloud models. It cannot be automated or repeated precisely.
2. **CLI Spawn Node (`ros2 run ros_gz_sim create`):** Scriptable, repeatable ROS 2 command style. Uses `-file` for localized layouts or `-topic` (`/robot_description`) for advanced project workflows.
3. **Launch File Automation (`launch.py`):** The standard project production layout. Coordinates physics engines and entity factory nodes using custom delay timers (`TimerAction`) from a single command.
4. **Baked into World (`<include>`):** Loads assets instantly alongside world file definitions. Requires converting raw URDF formats to static SDF compositions first via `gz sdf -p robot.urdf > robot.sdf`. Unsuitable for Reinforcement Learning routines that require constant location resets.
5. **Raw Service Calls (`gz service`):** Direct low-level transport invocation hitting `/world/<world_name>/create` endpoints using `gz.msgs.EntityFactory` requests. Essential for debugging system internals.

---

## 6. Execution Command Sequence (5-Terminal Flow)

To execute a complete test run of your mobile platform, spin up five synchronized terminals in the following sequence:

* **Terminal 1 — Publish Robot Description Parameter:**

```bash
ros2 run robot_state_publisher robot_state_publisher --ros-args -p use_sim_time:=true -p robot_description:="$(cat robot.urdf)"
```

* **Terminal 2 — Launch World Environment:**

```bash
gz sim -v 4 -r my_world.sdf
```

* **Terminal 3 — Bridge Global Clock Stream:**

```bash
ros2 run ros_gz_bridge parameter_bridge /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

* **Terminal 4 — Spawn Entity & Awaken Controllers:**

```bash
# Spawn from the live ROS parameter topic
ros2 run ros_gz_sim create -topic robot_description -name my_robot -z 0.3

# Activate the loaded controllers from the same terminal window
ros2 run controller_manager spawner joint_state_broadcaster
ros2 run controller_manager spawner diff_drive_controller
```

* **Terminal 5 — Drive via Keyboard Teleoperation:**

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true -p frame_id:=base_link -r /cmd_vel:=/diff_drive_controller/cmd_vel
```

---

## 7. The Systematic Debugging Matrix & Traps

| Symptom | Probable Cause | Direct Resolution |
| :--- | :--- | :--- |
| `gz sim` aborts instantly when robot spawns | Bare `type:` key sitting directly under controller name in YAML. | Nest the `type:` declarations inside `controller_manager.ros__parameters`. |
| Controller `spawner` hangs indefinitely | `controller_manager` failed to start up. | Check Gazebo console logs for failed hardware plugin loads. |
| Robot spawns but wheels never rotate | Missing `<command_interface name="velocity"/>` tag in URDF. | Append the velocity command interface lines inside the URDF joints. |
| "Velocity command timed out" logs on a steady loop | No input messages are arriving at the controller subscriber endpoint. | Check upstream remapping strings; confirm teleop output formatting matches the controller. |
| Odometry drifts heavily from true position tracking | Mismatched kinematic dimensions inside `controllers.yaml`. | Ensure `wheel_separation` and `wheel_radius` match the values declared in your URDF. |

### 🧠 The Ultimate Golden Rule for Debugging Control Chains

When topic graphs show publishers and subscribers hooked up correctly but no movement occurs, **never guess**. Immediately run `ros2 topic info <topic_name>`. Verify that the message types match exactly across endpoints. A shared topic *name* means nothing if a type mismatch exists between plain `Twist` structures and Jazzy's new `TwistStamped` format.
