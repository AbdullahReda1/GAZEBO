# Driving the Robot — ros2_control, gz_ros2_control, controller_manager

Session 3, phase 2. This builds directly on the two-wheeled `robot.urdf` from phase 1. Its wheels could already spin freely, with no motor. This phase adds the motor.

## 1. The confusion to clear up first

Three different-sounding names appear together constantly: `ros2_control`, `gz_ros2_control`, `controller_manager`. They are not three competing tools. They are three layers of one stack, and each layer only knows about the layer right next to it.

| Layer                  | What it is                                         | Lives where                               |
| ---------------------- | -------------------------------------------------- | ----------------------------------------- |
| `ros2_control`         | A hardware abstraction standard, just an interface | A `<ros2_control>` block in your URDF     |
| `gz_ros2_control`      | The bridge that connects that interface to Gazebo  | A `<gazebo><plugin>` block in your URDF   |
| `controller_manager`   | A ROS 2 node that loads and runs controllers       | Started automatically by the plugin above |

Read it as a chain, bottom to top. `ros2_control` is just a contract: "this joint accepts a velocity command, and reports back position and velocity." It says nothing about Gazebo. `gz_ros2_control` is the piece that fulfills that contract using real Gazebo joints. `controller_manager` is the broker sitting on top, deciding which controller gets to read and write which joint at any moment. You never call `controller_manager` directly from code; it runs quietly in the background once the plugin starts it.

## 2. Why two controllers, not one

A "controller" in this system is just a small plugin that either reads joint state, writes joint commands, or both. Your stack uses two, and they do different jobs on purpose.

`joint_state_broadcaster` only reads. It takes whatever `gz_ros2_control` reports from Gazebo, mass-produces it into one message, and publishes `/joint_states`. Nothing in your robot moves because of this controller; it only reports.

`diff_drive_controller` reads and writes. It subscribes to a velocity command topic, does the math to turn "move forward at 0.2 m/s" into "spin the left wheel at this rate, the right wheel at that rate," and sends those as commands. At the same time it tracks the robot's estimated position and publishes that as odometry.

You almost always load both together. Without the broadcaster, nothing outside Gazebo ever sees the real joint angles. Without the drive controller, nothing can command the wheels at all.

## 3. The full signal path

Trace one velocity command all the way through, so each piece's job is clear:

You publish a `Twist` on a cmd_vel topic. `diff_drive_controller` receives it and computes two wheel speeds. It hands those numbers to `controller_manager`, which routes them to the hardware interface that `gz_ros2_control` registered for this robot. The plugin applies those speeds to the actual joints inside Gazebo's physics engine. One simulation step later, Gazebo reports the new joint positions and velocities back up the same path. `joint_state_broadcaster` picks that up and publishes `/joint_states`. `diff_drive_controller` also uses it to update its odometry estimate and publish `/odom`.

Nothing in this chain talks to gz-transport or `ros_gz_bridge` directly. The `gz_ros2_control` plugin already lives inside the Gazebo process and reads Gazebo's internal joint state straight from the ECS, lesson 1's entity-component system. This is a separate path from the bridge you learned in lesson 2.

## 4. The three places you actually edit

Everything above is implemented by touching exactly three things: one block added to your URDF, one plugin added to your URDF, and one YAML file.

### 4.1 Add a `<ros2_control>` block to `robot.urdf`

This declares which joints exist and what each one accepts and reports. Add it as a top-level tag, alongside your existing `<link>` and `<joint>` tags:

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

Notice the joint names match the `continuous` joints you already built in phase 1. This block does not move anything by itself; it only declares the contract. `command_interface` is something this joint can be told to do. `state_interface` is something this joint reports back. A velocity-only wheel asks for nothing else.

### 4.2 Add the Gazebo plugin to `robot.urdf`

This is the piece that actually fulfills the contract above, inside Gazebo:

```xml
<gazebo>
  <plugin filename="gz_ros2_control-system"
          name="gz_ros2_control::GazeboSimROS2ControlPlugin">
    <parameters>/full/path/to/controllers.yaml</parameters>
  </plugin>
</gazebo>
```

This plugin is what starts `controller_manager` for you. You never run `controller_manager` as a separate command; it comes alive the moment this plugin loads, reading its settings from the YAML path given here.

### 4.3 Write `controllers.yaml`

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

    use_stamped_vel: false
```

Watch the nesting closely here, since it is easy to get wrong and ROS 2's parameter parser fails loudly if you do. Every value in this file must sit under a `ros__parameters:` key. That is why `joint_state_broadcaster` and `diff_drive_controller`'s *type* declarations live nested one level inside `controller_manager`'s own `ros__parameters` block, not as sibling top-level keys next to it. Only each controller's own tuning values, like `wheel_separation` here, get a second, separate top-level block with its own `ros__parameters:`. A bare `type:` sitting directly under a top-level `diff_drive_controller:` key, with no `ros__parameters:` above it, is invalid and will crash `gz sim` the moment the plugin tries to load it.

Two numbers come straight from your own `robot.urdf`: `wheel_separation` is the distance between the two wheels, 0.17 m out on each side, so 0.34 m total. `wheel_radius` is 0.08 m, matching the cylinder you already built. Get these wrong, and the robot will drive, but its odometry will drift and not match its real motion.

`use_stamped_vel` is worth a special note, and on Jazzy it no longer does what its name suggests. As of Jazzy, `diff_drive_controller`'s `~/cmd_vel` topic is unconditionally `geometry_msgs/msg/TwistStamped` — this was a deliberate breaking change, not version drift. Setting `use_stamped_vel: false` does **not** switch it back to plain `Twist`, and does **not** make the controller subscribe to a `cmd_vel_unstamped` topic either; on this version, that topic is never created at all. The parameter is effectively a no-op now. Publish `TwistStamped` from the start instead of fighting this.

## 5. Practical: drive your two-wheeled robot

You will run five terminals. Each does one job, same as the multi-terminal pattern from lesson 2.

* Edit `robot.urdf` from phase 1: add the `<ros2_control>` block (4.1) and the `<gazebo><plugin>` block (4.2) to it. Save `controllers.yaml` (4.3) in the same folder.

* Terminal 1 — publish the robot description as a ROS 2 parameter, which both RViz and the spawn step will read from:

```bash
ros2 run robot_state_publisher robot_state_publisher \
  --ros-args -p use_sim_time:=true \
  -p robot_description:="$(cat robot.urdf)"
```

* Terminal 2 — start the world:

```bash
gz sim -v 4 -r my_world.sdf
```

* Terminal 3 — bridge the clock, since `use_sim_time: true` is set in your YAML, and lesson 2 already explained why this must come first:

```bash
ros2 run ros_gz_bridge parameter_bridge \
  /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

* Terminal 4 — spawn the robot from the live topic, method 2 from phase 1, the `-topic` variant:

```bash
ros2 run ros_gz_sim create -topic robot_description -name my_robot -z 0.3
```

The moment this spawns, the `gz_ros2_control` plugin inside it loads, starts `controller_manager`, and reads `controllers.yaml`. At this point the controllers exist but are not yet active.

* Still terminal 4 — activate both controllers:

```bash
ros2 run controller_manager spawner joint_state_broadcaster
ros2 run controller_manager spawner diff_drive_controller
```

* Terminal 5 — drive it:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p stamped:=true -p frame_id:=base_link \
  -r /cmd_vel:=/diff_drive_controller/cmd_vel
```

`teleop_twist_keyboard` has its own `stamped` parameter for exactly this case: set to `true`, it publishes `geometry_msgs/msg/TwistStamped` instead of plain `Twist`, matching what `diff_drive_controller` actually listens for on Jazzy. `frame_id` is required alongside it, since a `TwistStamped` header needs one. Confirm the connection actually formed with `ros2 topic info /diff_drive_controller/cmd_vel` — both publisher and subscriber count should read `1`, with a single matching type, not the two-types trap from before.

The two `-p` flags can also live in a small params file instead of inline, which is tidier once you are typing this command often:

```yaml
# teleop_params.yaml
teleop_twist_keyboard:
  ros__parameters:
    stamped: true
    frame_id: base_link
```

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args --params-file teleop_params.yaml \
  -r /cmd_vel:=/diff_drive_controller/cmd_vel
```

`--params-file` only loads parameters for a node, never remaps, so the `-r` still has to stay on the command line either way. Save `teleop_params.yaml` in the same folder as `robot.urdf`.

Press a direction key and watch the wheels spin in Gazebo. Run `ros2 topic echo /joint_states` in a sixth terminal if you want to see the broadcaster's output directly, or `ros2 topic echo /diff_drive_controller/odom` to see the odometry update as it moves.

## 6. Common traps

| Symptom                                                                                                                          | Usual cause                                                                                                                                                                    |
| -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `gz sim` aborts the moment the robot spawns                                                                                      | A bare `type:` sitting under a controller name in `controllers.yaml` with no `ros__parameters:` above it — invalid, and the plugin crashes the whole process loading it        |
| `spawner` hangs, never returns                                                                                                   | `controller_manager` never started, check the plugin loaded in Gazebo's log                                                                                                    |
| Robot spawns, wheels never move                                                                                                  | `<command_interface name="velocity"/>` missing on the joint                                                                                                                    |
| `ros2 topic info` shows a publisher and subscriber, but teleop still does nothing                                                | Two different message types sharing one topic name — looks wired, nothing actually crosses                                                                                     |
| `ros2 topic info` on the topic you remapped to shows `Subscription count: 0`                                                     | Nothing is actually listening there, whatever the YAML says — see the debugging journey below for the Jazzy-specific version of this                                           |
| `diff_drive_controller` logs "Velocity command timed out" on a perfectly steady rhythm, with no gaps, even while pressing keys   | No command has ever arrived at all — this is not a physics or write-step problem, it is upstream of the controller entirely                                                    |
| Odometry drifts far from real motion                                                                                             | Wrong `wheel_separation` or `wheel_radius` in YAML                                                                                                                             |
| `joint_state_broadcaster` spawns, robot still frozen                                                                             | `diff_drive_controller` was never spawned, only the broadcaster                                                                                                                |
| Everything loads but sim time never advances                                                                                     | `/clock` bridge missing, same trap as lesson 2                                                                                                                                 |

## 7. The full debugging journey: "it loads fine but never moves"

This robot took a long real session to actually get moving, and almost none of the time was spent on the eventual real bug. Keeping the path here, in order, since the method matters more than the specific fixes — the same sequence of checks applies to any "everything looks fine but nothing happens" problem in this stack.

**Step 1 — a real crash, from a YAML structure mistake.** The first version of `controllers.yaml` put `type:` directly under `joint_state_broadcaster:` and `diff_drive_controller:` as their own top-level keys, with no `ros__parameters:` wrapping them. ROS 2's parameter parser rejected this outright — "Cannot have a value before ros__parameters" — and since this happens inside `gz_ros2_control`'s plugin load, the whole `gz sim` process aborted with it. Fix: nest the controller *type* declarations inside `controller_manager`'s own `ros__parameters` block, as shown in 4.3.

**Step 2 — the crash was gone, but nothing moved.** From here, several real things got checked and fixed along the way, none of which turned out to be the actual blocker:

* The Component Inspector's `Joint Velocity`, `Joint Position`, and `Joint Velocity Cmd` rows always showed blank, no matter what. This is a genuine GUI limitation — those are list-valued components, and the panel has no renderer for that type — not a sign of anything being zero. Worth knowing, not worth testing with again.
* `ros2 control list_hardware_interfaces` confirmed `left_wheel_joint/velocity` and `right_wheel_joint/velocity` as `claimed`, ruling out an ownership problem.
* A caster wheel offset error (`-0.06` instead of `-0.04`) had the chassis slightly sunk into the ground. Real bug, fixed, but not the one stopping motion.
* Teleop's own speed had been bumped up to nearly 19 m/s by repeated accidental key presses. Confusing to test with, not a bug.

**Step 3 — the decisive test: bypass ROS entirely.** With everything above checked and still no motion, the turning point was removing every ROS 2 layer from the test completely. A temporary `gz-sim-joint-controller-system` plugin was added straight to the URDF, and a single raw `gz topic` command was sent directly to the joint, with no `controller_manager`, no `diff_drive_controller`, no bridge, no teleop involved at all:

```bash
gz topic -t "/model/my_robot/joint/left_wheel_joint/cmd_vel" -m gz.msgs.Double -p "data: 5.0"
```

The wheel spun. That one result was worth more than everything before it — it proved conclusively that physics, geometry, and the joint itself were never the problem, and narrowed the entire search to the handoff somewhere between `teleop_twist_keyboard` and `gz_ros2_control`.

**Step 4 — proving no command was arriving at all.** Running `gz sim` with `RCUTILS_LOGGING_SEVERITY_THRESHOLD=DEBUG` set gave a log where `diff_drive_controller` printed "Velocity command timed out. Braking." on an unbroken, perfectly regular rhythm for the entire session — no gap, no interruption, even while keys were being pressed. A real incoming command would have reset that timer and broken the pattern. This was the proof that nothing was reaching the controller at all, not a bad write on the Gazebo side.

**Step 5 — finding exactly where the chain broke.** `ros2 node list` confirmed `teleop_twist_keyboard` really was running. `ros2 topic info /diff_drive_controller/cmd_vel_unstamped` then showed the actual gap: `Publisher count: 1`, `Subscription count: 0`. Teleop was publishing correctly — nobody was listening.

**Step 6 — the real root cause.** `diff_drive_controller` on ROS 2 Jazzy has a breaking change from older distros: `~/cmd_vel` is now unconditionally `geometry_msgs/msg/TwistStamped`, and `use_stamped_vel: false` no longer creates a `cmd_vel_unstamped` topic at all — that parameter is effectively a no-op now. Every earlier instruction to remap teleop to `cmd_vel_unstamped` was correct for older ROS 2 versions and simply wrong for this one.

**Step 7 — the actual fix.** Stop fighting the unstamped path and publish stamped from the start, using `teleop_twist_keyboard`'s own `stamped` and `frame_id` parameters, remapped straight to `cmd_vel`:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p stamped:=true -p frame_id:=base_link \
  -r /cmd_vel:=/diff_drive_controller/cmd_vel
```

That's the version in section 5 above. The robot moved on the first try with this command.

**The one habit worth keeping from all of this:** when commands "look" connected — a publisher exists, a subscriber exists, no errors anywhere — but nothing happens, check `ros2 topic info` for the actual type and the actual subscription count before touching anything else. A matching topic *name* proves nothing on its own.

## Updated folder for this lesson

```txt
03_spawn_urdf_robot/
├── workarea/
│   ├── robot.urdf              # now includes <ros2_control> + <gazebo><plugin>
│   ├── controllers.yaml
│   ├── teleop_params.yaml
│   └── spawn_robot.launch.py
├── info_3.md
└── info_3b.md
```
