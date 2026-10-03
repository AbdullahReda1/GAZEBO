
# Session 1 Summary: Gazebo Harmonic Basics (World, Model, SDF)

## 📌 Notable Takeaways & Core Concepts

### 1. ROS 2 Jazzy & Gazebo Harmonic Ecosystem

* **Official Pairing:** ROS 2 Jazzy Jalisco officially relies on **Gazebo Harmonic** (part of the new Gazebo generation, formerly Ignition).
* **End of Life (EOL):** Gazebo Classic (Gazebo 11) is completely deprecated and unsupported in ROS 2 Jazzy.
* **Package Naming Convention:** The keyword `gazebo` has been replaced with `gz` in the official apt repositories.
  * Core bridge package: `ros-jazzy-ros-gz`
  * Control package: `ros-jazzy-gz-ros2-control`

### 2. Gazebo Communication & The Bridge

* **`gz-transport`:** Gazebo's internal communication engine. It features topics and services, but it is **not ROS** and **not DDS**.
* **Protobuf Messages:** Gazebo uses Google Protocol Buffers (`gz.msgs.*`) for internal messaging.
* **The Bridge Requirement:** A standard ROS 2 node cannot inherently see or read a `gz` topic. The **`ros_gz_bridge`** package is mandatory to translate messages bidirectionally between DDS (ROS 2) and Protobuf (`gz-transport`).

### 3. Entity Component System (ECS) Architecture

* **Entity:** A numerical unique ID representing any simulated object (e.g., world, model, link, sensor). It acts as an empty container.
* **Component:** A raw data structure stored on an entity providing specific traits (e.g., pose, mass, color).
* **System:** Executable code running every physics time-step that reads, updates, or writes to components (e.g., physics engine, sensor manager).
* **⚠️ The Beginner Trap:** All functionalities (like physics or sensor streaming) are loaded via discrete **World Plugins (Systems)**. If a world file fails to load the sensor system plugin, features like a Lidar or Camera will silently publish absolutely nothing without printing an error message.

### 4. Basic SDF 1.10 Anatomy & Parameters

* **Root Tag:** `<sdf version="1.10">` marks the file as standard Simulation Description Format version 1.10.
* **Physics Tag (`<physics name="..." type="ignored">`):**
  * `type="ignored"`: In the new Gazebo generation, the solver type attribute is ignored in this tag because physics engines are loaded externally as runtime plugins (like DART or Bullet).
  * `<max_step_size>`: Governs the mathematical time step size for calculations. A value of `0.001` equals a 1ms step size. Smaller steps increase precision but heavily strain the CPU.
  * `<real_time_factor>`: Target simulation speed coefficient. `1.0` forces simulation time to sync exactly with real-world time.
* **Lights (`<light type="directional">`):** Directional types emit parallel light rays across the whole scene mimicking real sunlight. Controlled by `<direction>` matrices, `<diffuse>` reflections, and `<cast_shadows>` booleans.
* **Ground Planes & Static Models:** Setting `<static>true</static>` anchors an entity permanently in 3D space, preventing it from reacting to gravitational forces and saving massive CPU overhead by ignoring physical kinetic calculations.

### 5. VS Code Configuration for Robotics Development

* **Extensions:** XML (by Red Hat) and ROS (by Microsoft) are necessary to parse tags, auto-close elements, and handle formatting.
* **File Associations:** VS Code defaults to opening `.sdf` and `.urdf` as raw plain text. They must be permanently bound to the XML parser by modifying `settings.json`:

```json
"files.associations": {
    "*.sdf": "xml",
    "*.urdf": "xml"
}
```

* **Custom Snippets:** Generating an isolated snippet workflow (e.g., naming a target keyword `sdfworld` mapped to target code blocks) allows rapid scaffolding of full SDF world layouts instantly using the `Tab` key.

### 6. Model Inclusion & The Resource Path Resolution Conundrum

* **Modularity:** Massive projects avoid pasting large descriptions inline. They use the `<include>` tag referencing elements via local resource scopes (`model://ModelName`) or online databases.
* **Online Repositories:** Referencing a URI from **Gazebo Fuel** (`https://fuel.gazebosim.org/...`) instructs Gazebo to automatically download, build, and save the model into the system cache (`~/.gz/fuel/`) during initial execution.
* **The Validator Bug vs. Live Simulation:**
  * The main simulator (`gz sim`) uses a live solver callback function (`sdf::setFindFileCallback`) to look at the environment path list `GZ_SIM_RESOURCE_PATH`.
  * The standalone linter/validator utility (**`gz sdf -k`**) is an offline parser that completely lacks this callback registration step. Hence, it remains completely blind to `GZ_SIM_RESOURCE_PATH`, triggering a false negative `Error Code 14 (Unable to find uri model://)` on perfectly valid files.
* **The Ultimate Environment Fix:** The legacy linter binary inside `libsdformat` strictly monitors a fallback path named `SDF_PATH`. Mapping them together in `~/.bashrc` solves all local asset validation problems permanently across all checkers:

```bash
export GZ_SIM_RESOURCE_PATH=$HOME/gz_models:$GZ_SIM_RESOURCE_PATH
export SDF_PATH=$GZ_SIM_RESOURCE_PATH
```
