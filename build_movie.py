"""
build_movie.py
Master one-click runner for the 3D YouTube Shorts Movie Studio.
1. Automatically detects Blender 5.2 executable.
2. Procedurally generates campsite.blend if not present.
3. Runs engine/1_voice_gen.py to synthesize dialogue audio and timeline frames.
4. Runs engine/2_blender_director.py in headless Blender to direct and render the final vertical MP4.
"""

import sys
import os
import shutil
import subprocess

DEFAULT_BLENDER_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
]

def find_blender():
    """Detects Blender 5.2 executable or falls back to system PATH."""
    env_blender = os.environ.get("BLENDER_PATH")
    if env_blender and os.path.exists(env_blender):
        return env_blender

    for p in DEFAULT_BLENDER_PATHS:
        if os.path.exists(p):
            return p

    path_blender = shutil.which("blender")
    if path_blender:
        return path_blender

    raise FileNotFoundError(
        "Blender 5.2 executable not found! Checked:\n" +
        "\n".join(f" - {p}" for p in DEFAULT_BLENDER_PATHS) +
        "\nPlease set the BLENDER_PATH environment variable."
    )

def run_command(cmd, desc):
    """Runs a subprocess command with clear logging."""
    print("\n" + "=" * 60)
    print(f"STEP: {desc}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd, check=True)
    return result

def main():
    print("=" * 70)
    print("   3D YOUTUBE SHORTS MOVIE STUDIO - MASTER BUILD PIPELINE   ")
    print("=" * 70)

    # 1. Parse episode directory
    episode_dir = "episodes/ep01_campfire"
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                episode_dir = arg
                break

    episode_dir = os.path.normpath(episode_dir)
    print(f"Target Episode: {episode_dir}")

    # 2. Locate Blender
    blender_exe = find_blender()
    print(f"Blender Executable: {blender_exe}")

    # 3. Check or generate environment
    env_file = os.path.join("assets", "environments", "campsite.blend")
    if not os.path.exists(env_file):
        print(f"\nEnvironment file '{env_file}' not found. Generating procedurally...")
        run_command(
            [blender_exe, "--factory-startup", "-b", "-P", "engine/0_build_environments.py"],
            "Generating procedural campsite environment"
        )
    else:
        print(f"Environment found: {env_file}")

    # 4. Generate dialogue audio and timeline
    python_exe = sys.executable
    run_command(
        [python_exe, "engine/1_voice_gen.py", episode_dir],
        "Synthesizing dialogue voices & compiling timeline"
    )

    # 5. Direct and render 3D movie in Blender
    run_command(
        [blender_exe, "--factory-startup", "-b", "-P", "engine/2_blender_director.py", "--", episode_dir],
        "Directing 3D movie & rendering vertical MP4"
    )

    # 6. Verify output
    out_dir = os.path.join(episode_dir, "output")
    mp4_files = [f for f in os.listdir(out_dir) if f.endswith(".mp4")] if os.path.exists(out_dir) else []

    print("\n" + "=" * 70)
    print("   MOVIE PIPELINE EXECUTION COMPLETE   ")
    print("=" * 70)
    if mp4_files:
        for mp4 in mp4_files:
            p = os.path.join(out_dir, mp4)
            size_mb = os.path.getsize(p) / (1024 * 1024)
            print(f"OUTPUT VIDEO: {p} ({size_mb:.2f} MB)")
        srt_path = os.path.join(episode_dir, "subtitles.srt")
        if os.path.exists(srt_path):
            print(f"SUBTITLES   : {srt_path}")
    else:
        print("Warning: No MP4 file detected in output directory.")
    print("=" * 70)

if __name__ == "__main__":
    main()
