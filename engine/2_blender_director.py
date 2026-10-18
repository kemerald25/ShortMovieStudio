"""
2_blender_director.py
Automates the Blender 5.2 3D movie director pipeline:
1. Loads assets/environments/campsite.blend
2. Imports and places rigged human characters (Leo and Mia) facing each other across the campfire
3. Normalizes scale to ~1.7m tall and rotates to facing angles
4. Creates 85mm shallow Depth-of-Field close-up cameras focused at eye-level
5. Binds timeline markers for instant camera cuts per shot
6. Activates built-in human idle and movement animations
7. Adds dialogue audio strips into Blender 5.2's VSE using scene.sequence_editor.strips.new_sound
8. Renders vertical 1080x1920 (9:16) MP4 with H.264 video and AAC audio
"""

import sys
import os
import json
import math
import bpy
import mathutils

def point_camera_at(cam_obj, target_pos):
    """Rotates a camera object to point precisely at target_pos with zero roll."""
    direction = target_pos - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()

def import_and_setup_character(model_path, char_name, position, rot_z_deg, target_height_m, target_action_name, total_frames):
    """
    Imports a GLB character, normalizes height to target_height_m,
    positions and rotates it, and loops its action via NLA.
    """
    scene = bpy.context.scene
    abs_model_path = os.path.abspath(model_path)
    if not os.path.exists(abs_model_path):
        raise FileNotFoundError(f"Model file not found: {abs_model_path}")

    # Track objects before import to identify new objects
    existing_objects = set(bpy.data.objects)
    existing_actions = set(bpy.data.actions)

    print(f"Importing {char_name} from: {abs_model_path}...")
    bpy.ops.import_scene.gltf(filepath=abs_model_path)

    new_objects = [obj for obj in bpy.data.objects if obj not in existing_objects]
    new_actions = [a for a in bpy.data.actions if a not in existing_actions]

    # Find the armature object among imported objects
    armature = None
    for obj in new_objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break

    if not armature:
        raise RuntimeError(f"Could not find Armature object in imported {model_path}")

    armature.name = f"Armature_{char_name}"

    # Group into dedicated character collection
    char_collection = bpy.data.collections.new(f"Character_{char_name}")
    scene.collection.children.link(char_collection)
    for obj in new_objects:
        char_collection.objects.link(obj)
        if obj.name in scene.collection.objects:
            scene.collection.objects.unlink(obj)

    # Calculate current height of the character
    mesh_objs = [o for o in new_objects if o.type == 'MESH']
    current_height = 1.70
    if mesh_objs:
        max_dim = max(o.dimensions.z for o in mesh_objs if o.dimensions.z > 0.5) if any(o.dimensions.z > 0.5 for o in mesh_objs) else 1.70
        current_height = max_dim

    scale_factor = target_height_m / current_height if current_height > 0 else 1.0
    print(f"[{char_name}] Measured height: {current_height:.2f}m -> Target: {target_height_m:.2f}m (Scale: {scale_factor:.3f})")

    # Apply transform
    armature.scale = (scale_factor, scale_factor, scale_factor)
    armature.location = mathutils.Vector(position)
    armature.rotation_euler = (0.0, 0.0, math.radians(rot_z_deg))

    # Activate animation action
    action_to_use = None
    for act in new_actions:
        if target_action_name.lower() in act.name.lower():
            action_to_use = act
            break
    if not action_to_use and new_actions:
        # Fall back to first non-Tpose action
        for act in new_actions:
            if "tpose" not in act.name.lower():
                action_to_use = act
                break
        if not action_to_use:
            action_to_use = new_actions[0]

    if action_to_use:
        print(f"[{char_name}] Activating animation: {action_to_use.name}")
        if not armature.animation_data:
            armature.animation_data_create()
        armature.animation_data.action = action_to_use

        # Setup NLA track for seamless loop across timeline
        action_len = max(action_to_use.frame_range[1] - action_to_use.frame_range[0], 1.0)
        repeats = math.ceil(total_frames / action_len) + 2
        track = armature.animation_data.nla_tracks.new()
        strip = track.strips.new(f"{char_name}_Loop", 1, action_to_use)
        strip.repeat = float(repeats)
        print(f"[{char_name}] Created NLA strip loop ({repeats} repeats)")

    # Create eye-level focus empty for Depth of Field
    focus_z = position[2] + target_height_m * 0.88  # Approximate eye-level
    focus_empty = bpy.data.objects.new(f"FocusTarget_{char_name}", None)
    focus_empty.location = (position[0], position[1], focus_z)
    char_collection.objects.link(focus_empty)

    return armature, focus_empty

def setup_cameras(cam_collection, focus_leo, focus_mia):
    """Creates 85mm shallow Depth-of-Field close-up cameras focused at eye-level."""
    # 1. Close-up on Leo
    # Leo is at (-1.45, 0, 0) facing +X. Camera placed at (-0.45, -0.65, 1.52) looking at Leo
    leo_cam_data = bpy.data.cameras.new("Cam_CloseUp_Leo")
    leo_cam_data.lens = 85.0
    leo_cam_data.dof.use_dof = True
    leo_cam_data.dof.focus_object = focus_leo
    leo_cam_data.dof.aperture_fstop = 1.8

    leo_cam_obj = bpy.data.objects.new("Cam_CloseUp_Leo", leo_cam_data)
    leo_cam_obj.location = mathutils.Vector((-0.45, -0.68, 1.52))
    point_camera_at(leo_cam_obj, focus_leo.location)
    cam_collection.objects.link(leo_cam_obj)

    # 2. Close-up on Mia
    # Mia is at (1.45, 0, 0) facing -X. Camera placed at (0.45, -0.68, 1.48) looking at Mia
    mia_cam_data = bpy.data.cameras.new("Cam_CloseUp_Mia")
    mia_cam_data.lens = 85.0
    mia_cam_data.dof.use_dof = True
    mia_cam_data.dof.focus_object = focus_mia
    mia_cam_data.dof.aperture_fstop = 1.8

    mia_cam_obj = bpy.data.objects.new("Cam_CloseUp_Mia", mia_cam_data)
    mia_cam_obj.location = mathutils.Vector((0.45, -0.68, 1.48))
    point_camera_at(mia_cam_obj, focus_mia.location)
    cam_collection.objects.link(mia_cam_obj)

    print("Created close-up cameras: Cam_CloseUp_Leo (85mm f/1.8), Cam_CloseUp_Mia (85mm f/1.8)")

def setup_vse_and_markers(timeline_data):
    """Binds timeline markers for camera cuts and adds dialogue audio strips into VSE."""
    scene = bpy.context.scene

    # Clear any existing timeline markers
    scene.timeline_markers.clear()

    # Initialize VSE
    seq_ed = scene.sequence_editor_create()

    shots = timeline_data.get("shots", [])
    print(f"\nSetting up timeline markers and VSE audio for {len(shots)} shots:")

    for shot in shots:
        shot_id = shot["shot_id"]
        cam_name = shot["camera"]
        start_frame = shot["start_frame"]
        audio_path = os.path.abspath(shot["audio_file"])

        # 1. Timeline marker for instant camera cut
        cam_obj = bpy.data.objects.get(cam_name)
        if not cam_obj:
            print(f"Warning: Camera '{cam_name}' not found for shot {shot_id}. Defaulting to Cam_Wide")
            cam_obj = bpy.data.objects.get("Cam_Wide")

        marker = scene.timeline_markers.new(name=f"{shot_id}_{cam_name}", frame=start_frame)
        if cam_obj:
            marker.camera = cam_obj
            print(f" - Marker at frame {start_frame:03d} -> Cut to camera '{cam_obj.name}'")

        # 2. VSE audio strip using scene.sequence_editor.strips.new_sound
        if os.path.exists(audio_path):
            strip_name = f"Audio_{shot_id}_{shot['speaker']}"
            seq_ed.strips.new_sound(
                name=strip_name,
                filepath=audio_path,
                channel=2,
                frame_start=start_frame
            )
            print(f" - VSE sound strip '{strip_name}' added at frame {start_frame}")
        else:
            print(f"Warning: Audio file not found: {audio_path}")

def direct_movie(episode_dir):
    """Main orchestration function for 2_blender_director.py."""
    print("=" * 60)
    print("BLENDER DIRECTOR: Assembling 3D Movie Pipeline")
    print("=" * 60)

    # 1. Load compiled timeline
    timeline_path = os.path.join(episode_dir, "compiled_timeline.json")
    if not os.path.exists(timeline_path):
        raise FileNotFoundError(f"Compiled timeline not found: {timeline_path}. Run 1_voice_gen.py first.")

    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline_data = json.load(f)

    # 2. Open base campsite environment
    env_blend = os.path.abspath("assets/environments/campsite.blend")
    if not os.path.exists(env_blend):
        raise FileNotFoundError(f"Environment file not found: {env_blend}. Run 0_build_environments.py first.")

    print(f"Opening environment: {env_blend}")
    bpy.ops.wm.open_mainfile(filepath=env_blend)

    scene = bpy.context.scene
    total_frames = timeline_data.get("total_frames", 400)
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = timeline_data.get("fps", 24)

    # 3. Import and position human characters
    chars = timeline_data.get("characters", {})

    leo_config = chars.get("Leo", {
        "model": "assets/characters/Soldier.glb",
        "position": [-1.45, 0.0, 0.0],
        "rotation_z_deg": 90.0,
        "target_height": 1.75
    })
    arm_leo, focus_leo = import_and_setup_character(
        model_path=leo_config["model"],
        char_name="Leo",
        position=leo_config["position"],
        rot_z_deg=leo_config["rotation_z_deg"],
        target_height_m=leo_config.get("target_height", 1.75),
        target_action_name="Idle",
        total_frames=total_frames
    )

    mia_config = chars.get("Mia", {
        "model": "assets/characters/Michelle.glb",
        "position": [1.45, 0.0, 0.0],
        "rotation_z_deg": -90.0,
        "target_height": 1.68
    })
    arm_mia, focus_mia = import_and_setup_character(
        model_path=mia_config["model"],
        char_name="Mia",
        position=mia_config["position"],
        rot_z_deg=mia_config["rotation_z_deg"],
        target_height_m=mia_config.get("target_height", 1.68),
        target_action_name="SambaDance",
        total_frames=total_frames
    )

    # 4. Create close-up cameras
    cam_collection = bpy.data.collections.get("Campsite_Environment")
    if not cam_collection:
        cam_collection = scene.collection
    setup_cameras(cam_collection, focus_leo, focus_mia)

    # 5. Timeline markers and VSE audio strips
    setup_vse_and_markers(timeline_data)

    # 6. Render Settings for Vertical 9:16 Shorts
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 4

    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'

    # Configure Video + Audio encoding
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    scene.render.ffmpeg.ffmpeg_preset = 'REALTIME'
    scene.render.ffmpeg.audio_codec = 'AAC'
    scene.render.ffmpeg.audio_bitrate = 192

    # Output directory
    output_dir = os.path.abspath(os.path.join(episode_dir, "output"))
    os.makedirs(output_dir, exist_ok=True)
    ep_name = timeline_data.get("episode", "movie")
    out_mp4_path = os.path.join(output_dir, f"{ep_name}.mp4")
    scene.render.filepath = out_mp4_path

    # Save prepared movie blend for inspection/re-rendering
    movie_blend_path = os.path.join(output_dir, f"{ep_name}_scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=movie_blend_path)
    print(f"\nAssembled movie scene saved to: {movie_blend_path}")

    # 7. Render Final Movie Animation
    print("\n" + "=" * 60)
    print(f"Rendering {total_frames} frames to {out_mp4_path}...")
    print("=" * 60)
    bpy.ops.render.render(animation=True)

    if os.path.exists(out_mp4_path):
        size_mb = os.path.getsize(out_mp4_path) / (1024 * 1024)
        print(f"\nRENDER SUCCESSFUL: {out_mp4_path} ({size_mb:.2f} MB)")
    else:
        print(f"\nWarning: Output file not found at expected path: {out_mp4_path}")

    print("=" * 60)

def main():
    # Parse episode directory from arguments
    ep_dir = "episodes/ep01_campfire"
    for arg in sys.argv:
        if "episodes/" in arg or "episodes\\" in arg:
            ep_dir = arg
            break

    direct_movie(ep_dir)

if __name__ == "__main__":
    main()
