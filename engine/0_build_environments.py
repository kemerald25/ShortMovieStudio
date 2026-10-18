"""
0_build_environments.py
Procedurally builds a clean, stylized cinematic campsite environment in Blender 5.2.
Saves to assets/environments/campsite.blend
"""

import bpy
import math
import random
import os

def clean_scene():
    """Removes all default objects, meshes, materials, lights, and cameras."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for m in bpy.data.materials:
        bpy.data.materials.remove(m, do_unlink=True)
    for c in bpy.data.cameras:
        bpy.data.cameras.remove(c, do_unlink=True)
    for l in bpy.data.lights:
        bpy.data.lights.remove(l, do_unlink=True)

def create_principled_mat(name, base_color, roughness=0.8, metallic=0.0, emission_color=None, emission_strength=0.0):
    """Helper to create a Principled BSDF material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission_color and emission_strength > 0:
            bsdf.inputs["Emission Color"].default_value = emission_color
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat

def build_terrain(collection):
    """Builds a stylized bumpy green terrain with a central campfire clearing."""
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=50,
        y_subdivisions=50,
        size=26.0,
        location=(0, 0, 0)
    )
    terrain = bpy.context.active_object
    terrain.name = "Terrain"
    collection.objects.link(terrain)
    bpy.context.scene.collection.objects.unlink(terrain)

    # Displace vertices procedurally
    mesh = terrain.data
    random.seed(42)
    for v in mesh.vertices:
        x, y = v.co.x, v.co.y
        dist_from_center = math.hypot(x, y)
        if dist_from_center < 3.2:
            # Flattened campsite area
            z = math.sin(x * 1.5) * math.cos(y * 1.5) * 0.04
        else:
            # Stylized rolling mounds around perimeter
            t = (dist_from_center - 3.2) / 10.0
            z = (math.sin(x * 0.45) * 0.45 + math.cos(y * 0.38) * 0.45 + math.sin((x + y) * 0.3) * 0.3) * min(t, 1.2)
        v.co.z = z

    mesh.update()
    bpy.ops.object.shade_smooth()

    mat_terrain = create_principled_mat(
        "Mat_Terrain",
        base_color=(0.07, 0.16, 0.06, 1.0),
        roughness=0.9
    )
    terrain.data.materials.append(mat_terrain)

    # Add central dirt patch
    bpy.ops.mesh.primitive_circle_add(
        vertices=24,
        radius=2.2,
        fill_type='NGON',
        location=(0, 0, 0.015)
    )
    dirt = bpy.context.active_object
    dirt.name = "Campfire_DirtPatch"
    collection.objects.link(dirt)
    bpy.context.scene.collection.objects.unlink(dirt)
    mat_dirt = create_principled_mat(
        "Mat_Dirt",
        base_color=(0.11, 0.07, 0.04, 1.0),
        roughness=0.95
    )
    dirt.data.materials.append(mat_dirt)

def build_aframe_tent(collection, location=(-3.2, 1.8, 0.0), rot_z_deg=25):
    """Builds an orange stylized A-frame tent with ridge pole and entry flap."""
    tent_col = bpy.data.collections.new("Tent_Structure")
    collection.children.link(tent_col)

    mat_orange = create_principled_mat(
        "Mat_Tent_Orange",
        base_color=(0.88, 0.28, 0.05, 1.0),
        roughness=0.75
    )
    mat_wood = create_principled_mat(
        "Mat_Tent_Poles",
        base_color=(0.18, 0.11, 0.06, 1.0),
        roughness=0.85
    )

    # Main A-frame canvas (triangular prism)
    verts = [
        (-0.9, -1.3, 0.0), (0.9, -1.3, 0.0), (0.0, -1.3, 1.55),  # Front triangle
        (-0.9,  1.3, 0.0), (0.9,  1.3, 0.0), (0.0,  1.3, 1.55)   # Back triangle
    ]
    faces = [
        (0, 1, 2),       # Front face
        (4, 3, 5),       # Back face
        (0, 2, 5, 3),    # Left slope
        (2, 1, 4, 5),    # Right slope
        (0, 3, 4, 1)     # Bottom floor
    ]
    mesh = bpy.data.meshes.new("Tent_Canvas_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    tent_body = bpy.data.objects.new("Tent_Body", mesh)
    tent_body.data.materials.append(mat_orange)
    tent_col.objects.link(tent_body)

    # Ridge pole
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=0.04,
        depth=2.8,
        location=(0.0, 0.0, 1.55),
        rotation=(math.radians(90), 0, 0)
    )
    ridge_pole = bpy.context.active_object
    ridge_pole.name = "Tent_RidgePole"
    ridge_pole.data.materials.append(mat_wood)
    tent_col.objects.link(ridge_pole)
    bpy.context.scene.collection.objects.unlink(ridge_pole)

    # Front A-frame support poles
    for x_sign in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8,
            radius=0.035,
            depth=1.85,
            location=(x_sign * 0.45, -1.32, 0.77),
            rotation=(0, x_sign * math.radians(30), 0)
        )
        pole = bpy.context.active_object
        pole.name = f"Tent_FrontPole_{x_sign}"
        pole.data.materials.append(mat_wood)
        tent_col.objects.link(pole)
        bpy.context.scene.collection.objects.unlink(pole)

    # Group under an empty parent
    tent_root = bpy.data.objects.new("Tent_Root", None)
    tent_root.location = location
    tent_root.rotation_euler = (0, 0, math.radians(rot_z_deg))
    tent_col.objects.link(tent_root)
    for obj in [tent_body, ridge_pole]:
        obj.parent = tent_root

def build_campfire(collection):
    """Builds campfire stone ring, charred wooden logs, glowing embers, and flickering light."""
    fire_col = bpy.data.collections.new("Campfire")
    collection.children.link(fire_col)

    mat_stone = create_principled_mat(
        "Mat_Campfire_Stone",
        base_color=(0.22, 0.23, 0.25, 1.0),
        roughness=0.9
    )
    mat_log = create_principled_mat(
        "Mat_Campfire_Log",
        base_color=(0.14, 0.08, 0.05, 1.0),
        roughness=0.85
    )
    mat_fire_ember = create_principled_mat(
        "Mat_Campfire_Flame",
        base_color=(1.0, 0.5, 0.05, 1.0),
        roughness=0.3,
        emission_color=(1.0, 0.42, 0.04, 1.0),
        emission_strength=28.0
    )

    # 1. Circle of 10 low-poly stones
    num_stones = 10
    radius = 0.85
    random.seed(101)
    for i in range(num_stones):
        angle = (2.0 * math.pi / num_stones) * i + random.uniform(-0.1, 0.1)
        sx = math.cos(angle) * radius
        sy = math.sin(angle) * radius
        sz = 0.1 + random.uniform(0.0, 0.04)

        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=1,
            radius=0.18 + random.uniform(-0.03, 0.04),
            location=(sx, sy, sz)
        )
        stone = bpy.context.active_object
        stone.name = f"Stone_{i+1}"
        stone.scale = (1.0, 1.0 + random.uniform(-0.2, 0.3), 0.75 + random.uniform(-0.1, 0.2))
        stone.rotation_euler = (random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), random.uniform(0, 6.28))
        stone.data.materials.append(mat_stone)
        fire_col.objects.link(stone)
        bpy.context.scene.collection.objects.unlink(stone)

    # 2. Crossed wooden logs
    num_logs = 5
    for i in range(num_logs):
        ang = (math.pi / num_logs) * i + 0.2
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8,
            radius=0.075,
            depth=0.95,
            location=(math.cos(ang) * 0.08, math.sin(ang) * 0.08, 0.12),
            rotation=(math.radians(12), math.radians(15), ang)
        )
        log = bpy.context.active_object
        log.name = f"Log_{i+1}"
        log.data.materials.append(mat_log)
        fire_col.objects.link(log)
        bpy.context.scene.collection.objects.unlink(log)

    # 3. Glowing flame / ember crystals
    for j in range(5):
        fang = (2.0 * math.pi / 5) * j
        frad = 0.14
        bpy.ops.mesh.primitive_cone_add(
            vertices=5,
            radius1=0.14 - j * 0.015,
            radius2=0.01,
            depth=0.45 + (j % 2) * 0.12,
            location=(math.cos(fang) * frad, math.sin(fang) * frad, 0.22 + (j % 2) * 0.05),
            rotation=(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15), random.uniform(0, 3.14))
        )
        flame = bpy.context.active_object
        flame.name = f"Flame_Ember_{j+1}"
        flame.data.materials.append(mat_fire_ember)
        fire_col.objects.link(flame)
        bpy.context.scene.collection.objects.unlink(flame)

    # 4. Animated Flickering Point Light
    light_data = bpy.data.lights.new(name="Campfire_PointLight", type='POINT')
    light_data.color = (1.0, 0.58, 0.14)
    light_data.shadow_soft_size = 0.35
    light_obj = bpy.data.objects.new("Campfire_PointLight", light_data)
    light_obj.location = (0.0, 0.0, 0.45)
    fire_col.objects.link(light_obj)

    # Keyframe flicker animation over 300 frames (~12.5 seconds at 24fps)
    random.seed(999)
    base_power = 260.0
    for frame in range(1, 301, 2):
        flicker_power = base_power + random.uniform(-65.0, 75.0)
        light_data.energy = flicker_power
        light_data.keyframe_insert(data_path="energy", frame=frame)
        
        # Subtle position jitter for dancing campfire shadows
        jx = random.uniform(-0.03, 0.03)
        jy = random.uniform(-0.03, 0.03)
        jz = 0.45 + random.uniform(-0.02, 0.03)
        light_obj.location = (jx, jy, jz)
        light_obj.keyframe_insert(data_path="location", frame=frame)

def build_stylized_tree(name, location, scale=1.0, col=None):
    """Builds a low-poly stylized pine tree (trunk + 3 tiered conical foliage layers)."""
    mat_trunk = create_principled_mat(
        "Mat_Tree_Trunk",
        base_color=(0.14, 0.09, 0.05, 1.0),
        roughness=0.9
    )
    mat_foliage = create_principled_mat(
        "Mat_Tree_Foliage",
        base_color=(0.05, 0.15, 0.07, 1.0),
        roughness=0.85
    )

    tree_empty = bpy.data.objects.new(name, None)
    tree_empty.location = location
    tree_empty.scale = (scale, scale, scale)
    col.objects.link(tree_empty)

    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=0.22,
        depth=1.8,
        location=(location[0], location[1], location[2] + 0.9 * scale)
    )
    trunk = bpy.context.active_object
    trunk.name = f"{name}_Trunk"
    trunk.scale = (scale, scale, scale)
    trunk.data.materials.append(mat_trunk)
    trunk.parent = tree_empty
    col.objects.link(trunk)
    bpy.context.scene.collection.objects.unlink(trunk)

    # 3 Foliage Cones
    tiers = [
        {"r1": 1.45, "depth": 1.5, "z": 1.8},
        {"r1": 1.15, "depth": 1.4, "z": 2.7},
        {"r1": 0.85, "depth": 1.3, "z": 3.5}
    ]
    for idx, tier in enumerate(tiers):
        bpy.ops.mesh.primitive_cone_add(
            vertices=7,
            radius1=tier["r1"],
            radius2=0.02,
            depth=tier["depth"],
            location=(location[0], location[1], location[2] + tier["z"] * scale),
            rotation=(0, 0, idx * 0.4)
        )
        cone = bpy.context.active_object
        cone.name = f"{name}_Cone_{idx+1}"
        cone.scale = (scale, scale, scale)
        cone.data.materials.append(mat_foliage)
        cone.parent = tree_empty
        col.objects.link(cone)
        bpy.context.scene.collection.objects.unlink(cone)

def build_perimeter_trees(collection):
    """Distributes 8 stylized pine trees around the clearing perimeter."""
    trees_col = bpy.data.collections.new("Trees_Perimeter")
    collection.children.link(trees_col)

    # Coordinates surrounding campsite (avoiding direct line-of-sight of Cam_Wide)
    tree_configs = [
        {"pos": (-7.0,  3.5, 0.0), "scale": 1.25},
        {"pos": (-5.5,  6.8, 0.0), "scale": 1.10},
        {"pos": (-1.5,  8.5, 0.0), "scale": 1.35},
        {"pos": ( 3.8,  7.5, 0.0), "scale": 1.20},
        {"pos": ( 7.2,  4.2, 0.0), "scale": 1.15},
        {"pos": ( 7.8, -1.2, 0.0), "scale": 1.30},
        {"pos": ( 6.0, -5.5, 0.0), "scale": 1.05},
        {"pos": (-6.8, -3.8, 0.0), "scale": 1.20},
    ]

    for i, cfg in enumerate(tree_configs):
        build_stylized_tree(f"PineTree_{i+1}", cfg["pos"], cfg["scale"], trees_col)

def setup_cinema_lighting(collection):
    """Sets up Moonlight Area rim light and Dark sunset/night sky world shader."""
    # 1. Cool Moonlight Area Rim Light from behind
    moon_data = bpy.data.lights.new(name="Moonlight_RimLight", type='AREA')
    moon_data.color = (0.38, 0.62, 1.0)
    moon_data.energy = 520.0
    moon_data.size = 5.0
    moon_obj = bpy.data.objects.new("Moonlight_RimLight", moon_data)
    moon_obj.location = (4.5, 6.5, 7.5)
    # Point towards center (0, 0, 1.0)
    moon_obj.rotation_euler = (math.radians(-42), math.radians(28), math.radians(-145))
    collection.objects.link(moon_obj)

    # 2. Subtle Navy Ambient Fill Light
    fill_data = bpy.data.lights.new(name="Ambient_FillLight", type='AREA')
    fill_data.color = (0.15, 0.22, 0.45)
    fill_data.energy = 60.0
    fill_data.size = 8.0
    fill_obj = bpy.data.objects.new("Ambient_FillLight", fill_data)
    fill_obj.location = (-5.5, -4.0, 5.0)
    fill_obj.rotation_euler = (math.radians(35), math.radians(-30), math.radians(40))
    collection.objects.link(fill_obj)

    # 3. Night Sky World Shader
    world = bpy.data.worlds.new("CampsiteNightWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.012, 0.016, 0.035, 1.0)
        bg.inputs["Strength"].default_value = 0.45

def setup_camera_and_render_settings(collection):
    """Sets wide establishing camera, Color Management to AgX, and EEVEE render engine."""
    scene = bpy.context.scene

    # Render engine & resolution
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = 24

    # Color Management
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'

    # Wide establishing camera (35mm lens)
    cam_data = bpy.data.cameras.new("Cam_Wide")
    cam_data.lens = 35.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 150.0

    cam_obj = bpy.data.objects.new("Cam_Wide", cam_data)
    cam_obj.location = (0.0, -7.4, 3.4)
    cam_obj.rotation_euler = (math.radians(70), 0, 0)
    collection.objects.link(cam_obj)
    scene.camera = cam_obj

def main():
    print("=" * 60)
    print("Building Procedural Campsite Environment...")
    print("=" * 60)

    clean_scene()

    # Create root environment collection
    env_collection = bpy.data.collections.new("Campsite_Environment")
    bpy.context.scene.collection.children.link(env_collection)

    build_terrain(env_collection)
    build_aframe_tent(env_collection, location=(-3.2, 1.8, 0.0), rot_z_deg=25)
    build_campfire(env_collection)
    build_perimeter_trees(env_collection)
    setup_cinema_lighting(env_collection)
    setup_camera_and_render_settings(env_collection)

    # Ensure output directory exists
    out_dir = os.path.abspath("assets/environments")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "campsite.blend")

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"Successfully generated and saved environment to: {out_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
