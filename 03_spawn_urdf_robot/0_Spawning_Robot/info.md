# Spawning a Robot

Session 3 of 7. Broad pass, five ways to get a robot into a running world.

## 1. Why five methods exist

Lesson 1 taught one way already: write the model straight into the world file with `<include>`. That is fine for a fixed scene, like a table that is always there. But a robot is different. You often want to spawn it after the world is already running, maybe many times in a row for RL training, maybe from a different name each time, maybe from a file a launch system built just now. So Gazebo gives you more than one hook into the same action: create an entity in a running world. All five methods below end up calling the same underlying service. They are just five different doors into the same room.

## 2. The method comparison

| Method            | Needs the sim already running? | Good for                           | Typical use               |
| ----------------- | ------------------------------ | ---------------------------------- | ------------------------- |
| GUI drag-in       | Yes                            | Quick manual test, no typing       | Trying a model by eye     |
| CLI spawn         | Yes                            | One robot, scripted, repeatable    | Testing one spawn command |
| Launch file       | Starts it for you              | Normal project workflow            | Everyday development      |
| Baked into world  | No, loads at start             | A robot that is always there       | Fixed scenes, no respawn  |
| Raw`gz service`   | Yes                            | Debugging, understanding internals | Rarely used by hand       |

## 3. Method 1: GUI drag-in

Open the Insert panel on the left side of the Gazebo GUI. It lists every model Gazebo can find, searching your `GZ_SIM_RESOURCE_PATH` folders first, then Fuel. Click a model, then click again inside the 3D view to drop it at that spot.

This is the only method with no file and no command. It is good for a quick look at a model, but it does not scale. You cannot repeat it exactly, and nothing about it is scriptable. Treat it as a viewer, not a workflow.

## 4. Method 2: command-line spawn

The `ros_gz_sim` package ships a small node called `create`, built exactly for this. It is a real ROS 2 node, so it has ROS 2 style arguments.

```bash
ros2 run ros_gz_sim create \
  -file robot.urdf \
  -name my_robot \
  -x 0 -y 0 -z 0.3
```

`-file` points at a local SDF or URDF file. Note that URDF works directly here. The `create` node runs the URDF through libsdformat's own URDF-to-SDF converter before sending it to Gazebo, so you never have to convert by hand just to spawn.

There is a second input style, `-topic`, used instead of `-file`:

```bash
ros2 run ros_gz_sim create \
  -topic robot_description \
  -name my_robot
```

This reads the robot's description from a live ROS 2 topic, usually the one published by `robot_state_publisher`. This is the pattern you will use from lesson 6 onward, once RViz2 and TF need that same topic too. For now, `-file` is simpler and keeps today's lesson self-contained.

## 5. Method 3: one launch file for both steps

A launch file can start `gz sim` and the spawn command together, so one command does both. This is the shape nearly every real ROS 2 + Gazebo project uses.

```python
# spawn_robot.launch.py
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node

def generate_launch_description():
    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', '-r', 'my_world.sdf'],
        output='screen'
    )

    spawn = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-file', 'robot.urdf',
            '-name', 'my_robot',
            '-z', '0.3'
        ],
        output='screen'
    )

    return LaunchDescription([gazebo, spawn])
```

Notice there is no delay or wait step between the two actions. In this simple case it works because `ros2 run` (and the launch `Node` action) does not return until the node connects, and `create` keeps retrying the service call for a few seconds if the world is not ready yet. In bigger launch files you will sometimes see a `TimerAction` adding a short delay before the spawn, as a safety margin. Keep that in mind for later; it is not needed for today's practical.

## 6. Method 4: baked into the world file

This is lesson 1's `<include>`, used again here for a robot instead of furniture. The robot loads the moment the world starts, with no separate spawn step at all.

One limit to know: `<include>` expects an SDF model package, a folder with a `model.config` and a `model.sdf`, not a raw `.urdf` file. So to bake a URDF robot in this way, you convert it to SDF first:

```bash
gz sdf -p robot.urdf > robot.sdf
```

Then reference it the same way as lesson 1:

```xml
<include>
  <uri>robot.sdf</uri>
  <name>my_robot</name>
  <pose>0 0 0.3 0 0 0</pose>
</include>
```

Use this method only when the robot should always be there, with no respawning, no changing its start pose at runtime, and no scripting around it. For RL training, where you reset and respawn constantly, this method is the wrong tool.

## 7. Method 5: raw `gz service` call

Every method above ends at the same place: a gz-transport service called `/world/<world_name>/create`. Calling it directly shows you what is really happening underneath.

```bash
gz service -s /world/my_world/create \
  --reqtype gz.msgs.EntityFactory \
  --reptype gz.msgs.Boolean \
  --timeout 2000 \
  --req 'sdf_filename: "/full/path/robot.sdf", name: "my_robot", pose: {position: {z: 0.3}}'
```

Read the pattern the same way as the pause/play call from lesson 1: service name, request type, reply type, timeout, request body. The request type is `gz.msgs.EntityFactory`, a message built to describe one new entity: which file, what name, what starting pose. The `create` CLI node you used in method 2 is, underneath, just code that builds this exact request and sends it. You will rarely type this by hand, but seeing it once removes the mystery from the other four methods.

## 8. A detail worth noticing: continuous joints

If your URDF robot has a `continuous` joint, like a free-spinning wheel, know that SDF has no `continuous` joint type at all. Lesson 1's SDF snippet reference only listed `fixed`, `revolute`, `prismatic`, `ball`, and `universal`, because those are the real SDF types. When libsdformat converts your URDF, a `continuous` joint becomes a `revolute` joint with no `<limit>` tag, which Gazebo reads as free rotation with no stop. This is why a URDF wheel still spins forever once it lands in Gazebo, even though the word "continuous" never appears in the SDF.

## 9. Common traps

| Symptom                               | Usual cause                                                                   |
| ------------------------------------- | ----------------------------------------------------------------------------- |
| `create` hangs, never finishes        | No world is running yet, or the wrong world name                              |
| Robot spawns underground or flying    | Wrong`-z`, or `<pose>` z value                                                |
| Robot spawns but falls apart          | Missing`<inertial>` on one or more links                                      |
| `<include>` cannot find the robot     | URDF was not converted to SDF first                                           |
| Wheels do not spin freely as expected | Checked SDF directly, forgot`continuous` becomes `revolute` with no limit     |
| Two robots with the same name         | `-name` must be unique per world                                              |

## Practical: build and spawn a two-wheeled robot

This is a minimal robot: one box base, two cylinder wheels on continuous joints, with real inertial values so nothing acts strangely.

* Save this as `robot.urdf`:

```xml
<?xml version="1.0"?>
<robot name="my_robot">

  <link name="base_link">
    <inertial>
      <mass value="2.0"/>
      <inertia ixx="0.05" iyy="0.06" izz="0.08" ixy="0" ixz="0" iyz="0"/>
    </inertial>
    <visual>
      <geometry><box size="0.4 0.3 0.15"/></geometry>
    </visual>
    <collision>
      <geometry><box size="0.4 0.3 0.15"/></geometry>
    </collision>
  </link>

  <link name="left_wheel">
    <inertial>
      <mass value="0.3"/>
      <inertia ixx="0.001" iyy="0.001" izz="0.001" ixy="0" ixz="0" iyz="0"/>
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="1.5708 0 0"/>
      <geometry><cylinder radius="0.08" length="0.04"/></geometry>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="1.5708 0 0"/>
      <geometry><cylinder radius="0.08" length="0.04"/></geometry>
    </collision>
  </link>

  <link name="right_wheel">
    <inertial>
      <mass value="0.3"/>
      <inertia ixx="0.001" iyy="0.001" izz="0.001" ixy="0" ixz="0" iyz="0"/>
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="1.5708 0 0"/>
      <geometry><cylinder radius="0.08" length="0.04"/></geometry>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="1.5708 0 0"/>
      <geometry><cylinder radius="0.08" length="0.04"/></geometry>
    </collision>
  </link>

  <joint name="left_wheel_joint" type="continuous">
    <parent link="base_link"/>
    <child link="left_wheel"/>
    <origin xyz="0 0.17 -0.05" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>

  <joint name="right_wheel_joint" type="continuous">
    <parent link="base_link"/>
    <child link="right_wheel"/>
    <origin xyz="0 -0.17 -0.05" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
  </joint>

</robot>
```

* Start lesson 1's world, with nothing baked in except the ground:

```bash
gz sim -v 4 -r my_world.sdf
```

* Spawn it with method 2, the CLI node:

```bash
ros2 run ros_gz_sim create -file robot.urdf -name my_robot -z 0.3
```

Check the Entity Tree panel in the GUI. `my_robot` should appear, sitting on the ground, not falling through.

* Now remove it and spawn the same robot again, this time with method 5, the raw service call, to see it is the same action underneath:

```bash
gz service -s /world/my_world/remove \
  --reqtype gz.msgs.Entity \
  --reptype gz.msgs.Boolean \
  --timeout 2000 \
  --req 'name: "my_robot", type: MODEL'

gz service -s /world/my_world/create \
  --reqtype gz.msgs.EntityFactory \
  --reptype gz.msgs.Boolean \
  --timeout 2000 \
  --req 'sdf_filename: "/full/path/to/robot.urdf", name: "my_robot", pose: {position: {z: 0.3}}'
```

* As homework before lesson 4, try method 1 yourself: drag a model from the Insert panel into the same running world, just to feel the difference. And try method 4: convert `robot.urdf` to `robot.sdf` with `gz sdf -p`, then bake it into a copy of your world file with `<include>`, so it loads automatically on startup.

## Folder for this lesson

```txt
03_spawn_urdf_robot/
├── workarea/
│   ├── robot.urdf
│   └── spawn_robot.launch.py
└── info_3.md
```
