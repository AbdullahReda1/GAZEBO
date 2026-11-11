# `ros2_control` Inside Gazebo (The Depth Pass)

## 1. Core Architecture & Hardware Interfaces

- **`<ros2_control>` (URDF):** Declares robot joints and their available **command interfaces** (what controllers write: `position`, `velocity`, `effort`) and **state interfaces** (what controllers read: `position`, `velocity`).
- **`gz_ros2_control` Plugin:** Bridges ROS 2 control interfaces directly to Gazebo physics joints.
- **`hold_joints` (Default `true`):** Keeps joints locked in place whenever no active controller holds a claim on them.
- **Exclusive Interface Claiming:** Only **one** active controller may claim a specific joint command interface at a time. Broadcasters (like `joint_state_broadcaster`) only read state interfaces and never claim command interfaces.

## 2. Controller Lifecycle States

- **Loaded:** The controller plugin code is brought into memory by `controller_manager`.
- **Unconfigured:** Loaded into memory, but parameters from `controllers.yaml` have not been read yet.
- **Inactive:** Configured with valid parameters and ready to run, holding **no claims** on joint interfaces.
- **Active:** Running in the control loop, holding exclusive claims on its command interfaces, and writing commands to hardware.

### Essential CLI Management Commands

```bash
ros2 control list_controllers -v
ros2 control list_hardware_interfaces
ros2 control list_hardware_components
ros2 control switch_controllers --deactivate camera_pan_controller --activate camera_trajectory_controller
ros2 control set_controller_state camera_trajectory_controller inactive
```

## 3. Proportional Control Law & Loop Rates

For `position` command interfaces, `gz_ros2_control` converts target position errors into joint velocities using a discrete proportional law:

```text
velocity = position_proportional_gain × update_rate × (target - position)
```

### Parameter Locations & Interaction

| Parameter                        | File Location                                 | Role & Units                                                                         |
| :------------------------------- | :-------------------------------------------- | :----------------------------------------------------------------------------------- |
| `<max_step_size>`                | `myWorld.sdf` (`<physics>`)                   | Base Gazebo physics simulation period (`0.001` s = **1000 Hz**).                     |
| `update_rate`                    | `controllers.yaml` (`controller_manager`)     | Frequency (**Hz**) at which ROS 2 controllers read state and compute commands.       |
| `<position_proportional_gain>`   | `robot.urdf` (`<plugin>`)                     | Dimensionless gain multiplier read once when the plugin loads.                       |

### Gain Tuning Behavior

- **`gain < 1.0`:** Smooth approach without overshoot (smaller values move slower).
- **`gain = 1.0`:** Reaches target in a single control step (ideal discrete response).
- **`1.0 < gain < 2.0`:** Overshoots target and oscillates with shrinking swings.
- **`gain >= 2.0`:** Unstable oscillation (swings grow larger each cycle).
- **Rate Coupling:** Increasing `update_rate` from `100 Hz` to `1000 Hz` removes the slower-period warning and makes the joint move **10x faster** for the same gain.

## 4. `JointTrajectoryController` & Constraints

Unlike `JointGroupPositionController` (which jumps directly to a target), `joint_trajectory_controller/JointTrajectoryController` interpolates smooth time-parameterized waypoints and monitors execution constraints.

### Configuration & Units (`controllers.yaml`)

- **`allow_partial_joints_goal` (Boolean):** When `false`, every trajectory message must specify all listed joints; when `true`, subsets of joints can be commanded while others hold position.
- **`stopped_velocity_tolerance` (`rad/s` or `m/s`):** Maximum speed allowed at the end of a motion for the joint to be considered stopped.
- **`goal_time` (`seconds`):** Extra grace window after `time_from_start` allowed for the joint to settle within final goal tolerance.
- **`trajectory` (`rad` or `m`):** Maximum allowed path tracking error during motion before aborting.
- **`goal` (`rad` or `m`):** Final destination accuracy tolerance required for `SUCCEEDED` status (`error_code: 0`).

### Multi-Joint Strict Configuration Example (`allow_partial_joints_goal: false`)

```yaml
camera_trajectory_controller:
  ros__parameters:
    joints:
      - camera_pan_joint
      - camera_tilt_joint
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
      camera_tilt_joint:
        trajectory: 0.2
        goal: 0.05
```

## 5. Practical Execution & Terminal Diagnostics

- **Action vs. Topic Goals:** Sending goals via `/camera_trajectory_controller/follow_joint_trajectory` (`control_msgs/action/FollowJointTrajectory`) provides live feedback and final result codes (`error_code: 0` / `SUCCEEDED`), whereas topic publishing is fire-and-forget.
- **Header Timestamp Rule:** Always leave `header.stamp` at `sec: 0, nanosec: 0` ("start immediately"); timestamps in the past cause the trajectory to be ignored.
- **Monitoring Tracking Error:**

```bash
ros2 topic echo /camera_trajectory_controller/controller_state --field error.positions
```

- **High-Frequency CLI Echoing:** At `update_rate: 1000 Hz`, one-shot `ros2 topic echo --once` commands may report `A message was lost!!!` while connecting, and one-shot `ros2 topic pub --once` commands incur node discovery latency before executing.
