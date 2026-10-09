
# ros_gz_bridge

Session 2 of 7. Still a broad pass.

## 1. Why a bridge exists at all

Lesson 1 showed that Gazebo has its own messaging system, gz-transport, and that it is not DDS. ROS 2 nodes only speak DDS. So a gz topic and a ROS 2 topic can never see each other directly, no matter how similar their names look.

`ros_gz_bridge` is a translator process. It subscribes on one side and republishes on the other, converting each protobuf `gz.msgs.*` type into its matching ROS 2 message type, and back. It is a real ROS 2 node, so it shows up in `ros2 node list`, and it is also a real gz-transport node, so it shows up in `gz topic -l` output too.

## 2. Two ways to run it

The bridge has two use styles. The first is the command-line, one-topic-at-a-time form, good for quick tests:

```bash
ros2 run ros_gz_bridge parameter_bridge \
  /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

The second is a YAML config file, loaded by a launch file. This is what every real project uses, because listing ten topics on one command line is unreadable.

```yaml
# bridge_config.yaml
- ros_topic_name: "clock"
  gz_topic_name: "/clock"
  ros_type_name: "rosgraph_msgs/msg/Clock"
  gz_type_name: "gz.msgs.Clock"
  direction: GZ_TO_ROS

- ros_topic_name: "cmd_vel"
  gz_topic_name: "/model/my_robot/cmd_vel"
  ros_type_name: "geometry_msgs/msg/Twist"
  gz_type_name: "gz.msgs.Twist"
  direction: ROS_TO_GZ
```

```python
# launch file excerpt, Python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': 'bridge_config.yaml'}],
        output='screen'
    )
    return LaunchDescription([bridge])
```

## 3. Reading the one-line syntax

The command-line form packs a lot into one string. Read it piece by piece:

```bash
/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

The text before `@` is the topic name, shared by both sides. The text right after `@` is the ROS 2 type. The text after the bracket is the gz type. The bracket itself sets the direction.

| Bracket | Direction | Meaning                                 |
| ------- | --------- | --------------------------------------- |
| `[`     | GZ to ROS | Gazebo publishes, ROS 2 nodes subscribe |
| `]`     | ROS to GZ | ROS 2 publishes, Gazebo subscribes      |
| `@`     | Both ways | Bridged in both directions              |

Pick the direction on purpose. A clock only ever needs to flow from Gazebo to ROS. A velocity command only ever needs to flow from ROS to Gazebo. Bridging both ways on a topic that only needs one way wastes CPU and can create feedback loops on topics like odometry, where something might echo a message back to its own source.

## 4. Message pairs you will meet the most

Gazebo does not have its own version of every ROS message. The bridge only works for pairs that someone has already written a converter for, inside the `ros_gz_bridge` source code. You cannot bridge an arbitrary custom message without writing that converter yourself.

| ROS 2 type                        | GZ type                      | Typical use           | Usual direction |
| --------------------------------- | ---------------------------- | --------------------- | --------------- |
| `rosgraph_msgs/msg/Clock`         | `gz.msgs.Clock`              | Sim time              | GZ to ROS       |
| `geometry_msgs/msg/Twist`         | `gz.msgs.Twist`              | Velocity commands     | ROS to GZ       |
| `nav_msgs/msg/Odometry`           | `gz.msgs.Odometry`           | Robot pose and speed  | GZ to ROS       |
| `sensor_msgs/msg/Imu`             | `gz.msgs.IMU`                | IMU readings          | GZ to ROS       |
| `sensor_msgs/msg/LaserScan`       | `gz.msgs.LaserScan`          | 2D lidar              | GZ to ROS       |
| `sensor_msgs/msg/Image`           | `gz.msgs.Image`              | Camera frames         | GZ to ROS       |
| `sensor_msgs/msg/PointCloud2`     | `gz.msgs.PointCloudPacked`   | 3D lidar or depth cam | GZ to ROS       |
| `geometry_msgs/msg/PoseStamped`   | `gz.msgs.Pose`               | A single body's pose  | GZ to ROS       |
| `tf2_msgs/msg/TFMessage`          | `gz.msgs.Pose_V`             | Transform trees       | GZ to ROS       |

You do not need to memorize this table now. You will look it up every time you add a new topic, until the common ones stick from repetition.

## 5. Why the clock bridge matters so much

Sim time deserves a special note now, even though it gets a full lesson later. Gazebo runs its own clock, separate from your computer's wall clock. If a ROS 2 node's `use_sim_time` parameter is `true`, that node expects to read time from the `/clock` topic. If nobody bridges `/clock`, the node waits forever for a time source that never arrives, and anything using timestamps or timers can stall silently.

So in almost every real launch file, the clock bridge is the first bridge entry, even before anything else.

## 6. What the bridge does not do

The bridge only moves messages. It does not spawn robots, and it does not load plugins into Gazebo. Spawning is a separate service call, which is lesson 3. The bridge also adds a small delay and a translation cost on every message, so bridging a high-rate topic you never read, like a full-resolution camera nobody subscribes to, wastes bandwidth for no reason. Bridge only what you plan to use.

## 7. Common traps

| Symptom                                                 | Usual cause                                                                                                                                         |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ros2 topic echo` shows nothing                         | Wrong direction bracket, or the gz topic name is wrong                                                                                              |
| Bridge node starts then exits                           | A typo in the ROS or gz type string                                                                                                                 |
| `ros2 topic list` is missing the topic                  | Bridge process did not launch, check the launch log                                                                                                 |
| Node using`use_sim_time` never updates                  | `/clock` was never bridged                                                                                                                          |
| Data arrives late or choppy                             | Bridging a high-rate topic no one needs, wasting cycles                                                                                             |
| Pose topic echoes real data, but x/y/z stay frozen at 0 | Used`publish_link_pose` on a single-link model; that reports the link relative to its own model, not to world. Use `publish_model_pose` instead     |

Check the gz side name with `gz topic -l` and the exact type with `gz topic -i -t <topic>` before writing a bridge entry. A guessed topic name is the single most common reason a bridge silently does nothing.

## Practical: bridge a falling box's pose

Reuse the `box` model from lesson 1's world file. You will make Gazebo publish that box's pose, bridge it into ROS 2, and watch the numbers change live as it falls.

* Add a pose publisher plugin to the `box` model, right after its `<link>` closing tag, inside the `<model name="box">` block:

```xml
<plugin filename="gz-sim-pose-publisher-system"
        name="gz::sim::systems::PosePublisher">
  <publish_model_pose>true</publish_model_pose>
  <publish_link_pose>false</publish_link_pose>
  <use_pose_vector_msg>false</use_pose_vector_msg>
</plugin>
```

Use `publish_model_pose`, not `publish_link_pose`. The plugin's real job, by its own description, is to publish the pose of an entity's *children* relative to that entity. Attached inside `<model name="box">`, `publish_link_pose` reports `box_link`'s pose relative to the `box` model, not to the world. Since `box_link` has no `<pose>` offset of its own, that relative pose is permanently `0 0 0`, no matter how the box moves. `publish_model_pose` instead reports the model's own pose, which Gazebo tracks relative to the world. That is the number that actually changes as the box falls.

* Run the world and confirm the gz topic exists:

```bash
gz sim -v 4 -r my_world.sdf
gz topic -l | grep pose
```

You should see something like `/model/box/pose`.

* Check the exact gz type before writing the bridge line:

```bash
gz topic -i -t /model/box/pose
```

* Bridge it to ROS 2 as a `geometry_msgs/msg/PoseStamped`, one-line form, in a second terminal:

```bash
ros2 run ros_gz_bridge parameter_bridge \
  /model/box/pose@geometry_msgs/msg/PoseStamped[gz.msgs.Pose
```

* In a third terminal, watch it update:

```bash
ros2 topic echo /model/box/pose
```

You should see the Z value fall each print, then settle once the box lands on the ground plane. If nothing prints, work through the traps table above in order: check the gz topic name first, then the type string, then the bracket direction.

## What comes back later

The full plugin list for sensors, including the exact `<sensor>` tag next to each plugin, is lesson 4. The proper way to fold a bridge config into a robot's launch file, alongside spawning, comes in lesson 3. QoS tuning for the bridge is left for the depth pass.

## Test yourself

Why can a gz topic and a ROS 2 topic of the same name never talk directly? What does the `[` bracket mean, and when would you use `]` instead? Why is `/clock` almost always the first line in a bridge config? Answer these, then send your next file or say "next" for lesson 3.
