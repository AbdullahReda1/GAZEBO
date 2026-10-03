# info 1.md: Gazebo Harmonic Basics (World, Model, SDF)

Session 1 of 7. This is a broad pass. Depth comes on later rounds.

## 1. What Gazebo Harmonic is

Gazebo Harmonic is a physics simulator. Its main package is `gz-sim` version 8. It is a long-term support release, and it is the version that pairs with ROS 2 Jazzy.

The naming is confusing, so fix it now. "Gazebo Classic" is the old program. Its command is `gazebo`, and it stopped at version 11. "Gazebo" today means the new generation, which was first called Ignition (`ign` command). Harmonic belongs to the new generation, and its command is `gz`. Many answers online are for Classic. If a command or plugin name does not work, check this first.

## 2. Two processes and their own message layer

`gz sim` starts two parts. The server runs physics and sensors. The GUI only draws the scene. They talk over gz-transport, which is Gazebo's own messaging system.

gz-transport looks like ROS. It has topics and services. But it is not ROS and it is not DDS. Messages are protobuf types named `gz.msgs.*`. A ROS 2 node cannot see a gz topic on its own. This is the reason lesson 2 (`ros_gz_bridge`) exists.

Why split the server and the GUI? You can run the server alone with `gz sim -s`. Training a policy on a remote machine needs no window. Also, a GUI crash will not kill your simulation.

## 3. Everything is a system

Gazebo uses an Entity Component System. An entity is only an ID: a world, a model, a link, a sensor. A component is a piece of data on an entity, like a pose or a mass. A system is code that runs every step and reads or writes components.

The result is that each feature is a plugin. Physics is a system. Sensors are a system. If your world file does not load the system, the feature does not exist. There is no error message. A lidar without the sensors system just publishes nothing. This is the most common beginner trap.

| Plugin file                         | Job                                    | If it is missing              |
| ----------------------------------- | -------------------------------------- | ----------------------------- |
| `gz-sim-physics-system`             | Moves bodies and handles contact       | Nothing falls or moves        |
| `gz-sim-user-commands-system`       | Spawn, delete, move by service call    | Spawn calls fail (lesson 3)   |
| `gz-sim-scene-broadcaster-system`   | Sends the scene to the GUI             | GUI stays empty               |
| `gz-sim-sensors-system`             | Runs cameras and lidars (needs render) | Those sensors publish nothing |

The IMU has its own system, `gz-sim-imu-system`. We will meet it in lesson 4.

## 4. The object tree: world, model, link

A world holds models. A model holds links. A link is one rigid body. Joints connect links. Shapes and sensors sit on links.

| Element         | What it is                     | What it holds                        |
| --------------- | ------------------------------ | ------------------------------------ |
| `<world>`       | The whole scene                | Physics, plugins, lights, models     |
| `<model>`       | One object or one robot        | Links, joints, plugins               |
| `<link>`        | One rigid body                 | Inertial, collision, visual, sensors |
| `<joint>`       | A connection between two links | Parent, child, axis, limits          |
| `<inertial>`    | How the body resists motion    | Mass and inertia matrix              |
| `<collision>`   | Shape used for contact physics | Geometry                             |
| `<visual>`      | Shape used for drawing         | Geometry, material                   |
| `<sensor>`      | A sensor fixed on a link       | Type, update rate, topic             |

Visual and collision are separate on purpose. Contact math is costly. So you draw a detailed mesh but collide with a simple box. Physics only reads collision. The eye only reads visual.

If you skip `<inertial>`, Gazebo uses default values (mass 1, unit inertia). The body then moves wrongly, and you get no warning. Always set it. For a solid box, each diagonal term is `m * (a² + b²) / 12`.

A model with `<static>true</static>` never moves and costs no physics time. The ground plane is the usual example.

## 5. The standard SDF world pattern

SDF is XML. The root is `<sdf version="1.10">`. Harmonic uses SDF spec 1.10. Inside sits one `<world>`. The usual order inside a world is: physics, system plugins, light, then models. The order does not matter to the parser, but everyone writes it this way, so files are easy to read.

```xml
<?xml version="1.0"?>
<sdf version="1.10">
  <world name="my_world">

    <!-- 1. Physics: time step and target speed -->
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <!-- 2. Systems: without these, nothing happens -->
    <plugin filename="gz-sim-physics-system"
            name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system"
            name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system"
            name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system"
            name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <!-- 3. Light: without it the scene is dark -->
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <!-- 4. Ground: static, so it costs no physics -->
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry>
            <plane><normal>0 0 1</normal><size>100 100</size></plane>
          </geometry>
        </collision>
        <visual name="visual">
          <geometry>
            <plane><normal>0 0 1</normal><size>100 100</size></plane>
          </geometry>
          <material>
            <ambient>0.8 0.8 0.8 1</ambient>
            <diffuse>0.8 0.8 0.8 1</diffuse>
          </material>
        </visual>
      </link>
    </model>

    <!-- 5. A dynamic model: a 1 kg box dropped from 0.5 m -->
    <model name="box">
      <pose>0 0 0.5 0 0 0</pose>
      <link name="box_link">
        <inertial>
          <mass>1.0</mass>
          <inertia>
            <ixx>0.1667</ixx><iyy>0.1667</iyy><izz>0.1667</izz>
            <ixy>0</ixy><ixz>0</ixz><iyz>0</iyz>
          </inertia>
        </inertial>
        <collision name="collision">
          <geometry><box><size>1 1 1</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>1 1 1</size></box></geometry>
          <material>
            <ambient>0.2 0.4 0.9 1</ambient>
            <diffuse>0.2 0.4 0.9 1</diffuse>
          </material>
        </visual>
      </link>
    </model>

  </world>
</sdf>
```

The physics block sets the step size. A step of 0.001 s means 1000 steps per simulated second. Smaller steps give better contact but use more CPU. `real_time_factor` is a target speed, where 1.0 means real time. The `type="ignored"` text is a habit from the tutorials. The name is only a label.

Every `<pose>` is `x y z roll pitch yaw`, in meters and radians. It is relative to the parent frame. A model's pose is relative to the world. A link's pose is relative to its model. The axes are X forward, Y left, Z up. This is the same as ROS REP 103, so you need no conversion later.

## 6. Reusing models and the resource path

Real worlds do not paste every model inline. They use `<include>`.

```xml
<include>
  <uri>model://my_robot</uri>
  <name>robot_1</name>
  <pose>0 0 0.1 0 0 0</pose>
</include>
```

`model://my_robot` is not a real path. Gazebo searches a list of folders for a folder named `my_robot`. That list comes from an environment variable. This is the same idea as `AMENT_PREFIX_PATH` and `package://` in ROS.

```bash
# Add included models to the resource path of Gazebo to enable `gz sim` to find them with `model://` at uri tag.
export GZ_SIM_RESOURCE_PATH=$HOME/gz_models:$GZ_SIM_RESOURCE_PATH
# Add included models to the resource path of SDF to enable `gz sdf -k` to find them with `model://` at uri tag.
export SDF_PATH=$GZ_SIM_RESOURCE_PATH
```

The URI can also point to Gazebo Fuel, the online model library. The pattern is `https://fuel.gazebosim.org/1.0/<owner>/models/<name>`. Gazebo downloads and caches the model on first use.

## 7. Commands you will use every day

| Command                                  | What it does                               |
| ---------------------------------------- | ------------------------------------------ |
| `gz sim -v 4 -r my_world.sdf`            | Run server and GUI, verbose, start playing |
| `gz sim -s my_world.sdf`                 | Server only, no window (headless)          |
| `gz sim -g`                              | GUI only, joins a running server           |
| `gz sdf -k my_world.sdf`                 | Check the file for errors                  |
| `gz topic -l`                            | List gz topics                             |
| `gz topic -e -t /world/my_world/stats`   | Print messages from one topic              |
| `gz service -l`                          | List gz services                           |

Gazebo starts paused unless you pass `-r`. This surprises many people. You can also pause or play from a terminal, because world control is just a gz service.

```bash
gz service -s /world/my_world/control --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean --timeout 2000 --req 'pause: true'
```

Read the pattern: service name, request type, reply type, timeout, request body. Every gz service call has this shape. The ROS 2 equivalent is `ros2 service call`, but here you must name the message types yourself.

## 8. The standard workflow

Write the SDF file. Run `gz sdf -k` to catch XML and schema mistakes. Start with `gz sim -v 4 -r`, because verbosity level 4 prints plugin load messages. Then run `gz topic -l` to see what is alive. If an expected topic is missing, suspect a missing system plugin first, then a wrong plugin name, then a wrong resource path.

## 9. Common traps

| Symptom                           | Usual cause                                     |
| --------------------------------- | ----------------------------------------------- |
| GUI opens but the scene is empty  | Scene broadcaster system not in the world       |
| Objects hang in the air           | Physics system missing, or model is`<static>`   |
| Camera or lidar topic has no data | Sensors system missing, or wrong render engine  |
| Model falls through the ground    | Ground has no`<collision>`                      |
| `model://x` not found             | Folder is not on`GZ_SIM_RESOURCE_PATH`          |
| Robot jitters or explodes         | Bad inertia values, or time step too big        |
| An online answer does not work    | It was written for Gazebo Classic               |
