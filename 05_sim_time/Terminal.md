# Terminal Analyse

The test went well. The numbers match what lesson 5 says should happen.

| What you measured                                                                                                        | What it shows                                                                          |
| ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `/clock` echoed 31.908 twice in a row                                                                                    | Sim time stopped while Gazebo was paused.                                              |
| The probe with sim time had `wall_delta` jumps of 18.55 s and 37.02 s, but `ros_time` still went up by exactly 1.000     | Those jumps are your two pauses. ROS timers count simulated seconds, not wall seconds. |
| The probe without sim time: 157 samples, `ros_time` = `wall_time`, delta always 1.00                                     | The wall clock never cares about pause or speed.                                       |
| IMU stamps were 38.87 and 49.95, `/clock` was 41.08 and 49.95, `date +%s` was 1794007307                                 | Sensor data uses sim time. A node on wall time sees a stamp from 1970.                 |
| `header.frame_id` was `imu_link` and `camera_link`                                                                       | `gz_frame_id` works.                                                                   |
| `set_physics` returned `data: true`                                                                                      | You can change speed while the sim runs.                                               |
| `/clock` rate fell from about 780 to about 440 messages per second                                                       | The real time factor is the rate divided by 1000.                                      |
| `wall_delta` grew from about 1.1 to about 2.3 s per sim second                                                           | The real time factor dropped from about 0.9 to about 0.43.                             |
| `tf2_echo` showed a fixed offset `[0.12, 0, 0.05]` and a yaw of 0, then 28.648°, then −40.107°                           | The offset equals the pan joint origin. The angles are exactly 0.5 and −0.7 rad.       |

**What to watch:**

- **Speed:** you asked for 0.5, but your machine got about 0.43–0.49. Camera, lidar and the Gazebo window together are heavy. For more speed, lower the camera size and rate, for example 320×240 at 15 Hz, and use fewer lidar samples. Nothing is broken, because sim time keeps the robot logic correct.
- **Stalls:** the longest gap between `/clock` messages grew to 0.396 s, so Gazebo stutters sometimes.
- **Early errors:** `/clock does not appear to be published yet` and `frame base_link does not exist` are harmless. They appear when you start a command before the simulation and bridge are up.

Four things you can learn from that TF output:

**1. The stamps work as a speed meter.** `tf2_echo` prints about once per wall second. In the first group the stamps move 0.505 sim seconds per print (34.38 to 56.61 over 44 prints). That means the real time factor was about 0.5, which is exactly what you set with `set_physics`.

**2. You can read the pan angle from the quaternion.** Yaw = 2·atan2(z, w). For z = 0.242 and w = 0.970 that gives 28.0°, which matches the printed 28.048°. The settled values 28.648° and −40.107° are exactly 0.5 and −0.7 rad. So the position controller reaches its target exactly.

**3. The joint settles in one or two prints.** The camera went from about +28° (26.356° while moving) to −28.648° in the 0.48 sim seconds between the G3 and G4 stamps. Intermediate values like 26.356° and 28.048° are the camera caught while moving.

**4. Small backward steps are normal; a reset is not.** The stamps went back by 0.02 s and 0.12 s, but TF keeps about 10 seconds of history, so it handles that. Trouble starts when time jumps back far, like a Gazebo reset. To check for a duplicate publisher, run this:

```bash
ros2 topic info /tf -v
```

It should list exactly two publishers: `robot_state_publisher` and `diff_drive_controller`. A third one means a leftover node from an earlier run is also publishing.

```Shell
abdullah@linux:/mnt/ubuntu_data/ROS2/GAZEBO/05_sim_time$ ros2 param list /controller_manager 
    camera_pan_controller.fallback_controllers
    camera_pan_controller.node_options_args
    camera_pan_controller.type
    defaults.allow_controller_activation_with_inactive_hardware
    defaults.deactivate_controllers_on_hardware_self_deactivate
    defaults.switch_controller.strictness
    diagnostic_updater.period
    diagnostic_updater.use_fqn
    diagnostics.threshold.controller_manager.periodicity.mean_error.error
    diagnostics.threshold.controller_manager.periodicity.mean_error.warn
    diagnostics.threshold.controller_manager.periodicity.standard_deviation.error
    diagnostics.threshold.controller_manager.periodicity.standard_deviation.warn
    diagnostics.threshold.controllers.execution_time.mean_error.error
    diagnostics.threshold.controllers.execution_time.mean_error.warn
    diagnostics.threshold.controllers.execution_time.standard_deviation.error
    diagnostics.threshold.controllers.execution_time.standard_deviation.warn
    diagnostics.threshold.controllers.periodicity.mean_error.error
    diagnostics.threshold.controllers.periodicity.mean_error.warn
    diagnostics.threshold.controllers.periodicity.standard_deviation.error
    diagnostics.threshold.controllers.periodicity.standard_deviation.warn
    diagnostics.threshold.hardware_components.execution_time.mean_error.error
    diagnostics.threshold.hardware_components.execution_time.mean_error.warn
    diagnostics.threshold.hardware_components.execution_time.standard_deviation.error
    diagnostics.threshold.hardware_components.execution_time.standard_deviation.warn
    diagnostics.threshold.hardware_components.periodicity.mean_error.error
    diagnostics.threshold.hardware_components.periodicity.mean_error.warn
    diagnostics.threshold.hardware_components.periodicity.standard_deviation.error
    diagnostics.threshold.hardware_components.periodicity.standard_deviation.warn
    diff_drive_controller.fallback_controllers
    diff_drive_controller.node_options_args
    diff_drive_controller.type
    enforce_command_limits
    handle_exceptions
    hardware_components_initial_state.inactive
    hardware_components_initial_state.shutdown_on_initial_state_failure
    hardware_components_initial_state.unconfigured
    joint_state_broadcaster.fallback_controllers
    joint_state_broadcaster.node_options_args
    joint_state_broadcaster.type
    overruns.print_warnings
    qos_overrides./clock.subscription.depth
    qos_overrides./clock.subscription.durability
    qos_overrides./clock.subscription.history
    qos_overrides./clock.subscription.reliability
    qos_overrides./parameter_events.publisher.depth
    qos_overrides./parameter_events.publisher.durability
    qos_overrides./parameter_events.publisher.history
    qos_overrides./parameter_events.publisher.reliability
    start_type_description_service
    update_rate
    use_sim_time
```
