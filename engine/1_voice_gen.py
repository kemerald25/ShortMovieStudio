"""
1_voice_gen.py
Reads script.json, generates neural voice MP3s and .srt subtitles using edge-tts,
calculates exact start_frame and end_frame for each shot at 24 FPS,
and saves compiled_timeline.json.
"""

import sys
import os
import json
import asyncio
import socket
from datetime import timedelta
import aiohttp
import mutagen.mp3
import edge_tts

async def synthesize_shot(text, voice, out_mp3_path, out_srt_path):
    """Synthesizes text using edge-tts and creates both MP3 audio and SRT subtitles."""
    # Force IPv4 socket to prevent Windows IPv6 DNS timeouts
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    communicate = edge_tts.Communicate(
        text,
        voice,
        boundary="WordBoundary",
        connector=connector,
        connect_timeout=30
    )
    sub_maker = edge_tts.SubMaker()
    
    with open(out_mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                sub_maker.feed(chunk)
                
    srt_content = sub_maker.get_srt()
    # Fallback to full line subtitle if word boundary cues are empty
    if not srt_content.strip():
        audio = mutagen.mp3.MP3(out_mp3_path)
        dur = timedelta(seconds=audio.info.length)
        srt_content = f"1\n00:00:00,000 --> {str(dur)[:11].replace('.', ',')}\n{text}\n"

    with open(out_srt_path, "w", encoding="utf-8") as srt_file:
        srt_file.write(srt_content)

def offset_srt(srt_text, offset_sec, start_index=1):
    """Offsets timestamps in an SRT block by offset_sec."""
    lines = srt_text.strip().split("\n")
    output_lines = []
    idx = start_index

    def format_td(td):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        millis = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    def parse_time_str(tstr):
        parts = tstr.replace(",", ".").split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return timedelta(hours=h, minutes=m, seconds=s)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.isdigit() and i + 1 < len(lines) and "-->" in lines[i + 1]:
            time_line = lines[i + 1].strip()
            arrow_split = time_line.split("-->")
            t_start = parse_time_str(arrow_split[0].strip()) + timedelta(seconds=offset_sec)
            t_end = parse_time_str(arrow_split[1].strip()) + timedelta(seconds=offset_sec)

            output_lines.append(str(idx))
            output_lines.append(f"{format_td(t_start)} --> {format_td(t_end)}")
            idx += 1
            i += 2
            while i < len(lines) and lines[i].strip() and not (lines[i].strip().isdigit() and i + 1 < len(lines) and "-->" in lines[i + 1]):
                output_lines.append(lines[i].strip())
                i += 1
            output_lines.append("")
        else:
            i += 1

    return "\n".join(output_lines), idx

async def compile_voices(episode_dir):
    """Processes script.json and creates audio files + compiled_timeline.json."""
    script_path = os.path.join(episode_dir, "script.json")
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script file not found: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    fps = script.get("fps", 24)
    audio_dir = os.path.join(episode_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    characters = script.get("characters", {})
    shots = script.get("shots", [])

    print("=" * 60)
    print(f"Compiling voices for episode: {script.get('title', episode_dir)}")
    print(f"Target FPS: {fps}")
    print("=" * 60)

    compiled_shots = []
    current_frame = 1
    master_srt_blocks = []
    srt_counter = 1

    for idx, shot in enumerate(shots):
        shot_id = shot["shot_id"]
        speaker = shot["speaker"]
        text = shot["text"]
        camera = shot.get("camera", "Cam_Wide")
        pause_sec = shot.get("pause_after_sec", 0.5)

        char_data = characters.get(speaker, {})
        voice = char_data.get("voice", "en-US-ChristopherNeural")

        mp3_name = f"{shot_id}_{speaker}.mp3"
        srt_name = f"{shot_id}_{speaker}.srt"
        mp3_path = os.path.join(audio_dir, mp3_name)
        srt_path = os.path.join(audio_dir, srt_name)

        print(f"\n--- Shot {idx + 1}/{len(shots)}: [{shot_id}] Speaker: {speaker} ({voice}) ---")
        print(f"Generating line: \"{text}\"")

        await synthesize_shot(text, voice, mp3_path, srt_path)

        # Compute duration
        audio_info = mutagen.mp3.MP3(mp3_path)
        duration_sec = audio_info.info.length
        duration_frames = int(round(duration_sec * fps))
        pause_frames = int(round(pause_sec * fps))
        total_shot_frames = duration_frames + pause_frames

        start_frame = current_frame
        end_frame = current_frame + total_shot_frames - 1

        print(f"Audio duration: {duration_sec:.2f}s ({duration_frames} frames) + Pause: {pause_sec:.2f}s ({pause_frames} frames)")
        print(f"Timeline frame range: {start_frame} -> {end_frame} (Total {total_shot_frames} frames)")

        # Master SRT offset calculation
        start_time_sec = (start_frame - 1) / fps
        with open(srt_path, "r", encoding="utf-8") as sf:
            raw_srt = sf.read()
        shifted_srt, srt_counter = offset_srt(raw_srt, start_time_sec, srt_counter)
        if shifted_srt.strip():
            master_srt_blocks.append(shifted_srt.strip())

        compiled_shots.append({
            "shot_id": shot_id,
            "speaker": speaker,
            "camera": camera,
            "text": text,
            "audio_file": os.path.abspath(mp3_path).replace("\\", "/"),
            "audio_file_rel": f"audio/{mp3_name}",
            "srt_file": os.path.abspath(srt_path).replace("\\", "/"),
            "audio_duration_sec": duration_sec,
            "duration_frames": duration_frames,
            "pause_frames": pause_frames,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "total_shot_frames": total_shot_frames
        })

        current_frame = end_frame + 1

    total_frames = current_frame - 1
    total_duration_sec = total_frames / fps

    compiled_timeline = {
        "title": script.get("title", "YouTube Shorts Episode"),
        "episode": script.get("episode", os.path.basename(episode_dir)),
        "fps": fps,
        "characters": characters,
        "total_frames": total_frames,
        "total_duration_sec": total_duration_sec,
        "shots": compiled_shots
    }

    timeline_json_path = os.path.join(episode_dir, "compiled_timeline.json")
    with open(timeline_json_path, "w", encoding="utf-8") as f:
        json.dump(compiled_timeline, f, indent=2)

    master_srt_path = os.path.join(episode_dir, "subtitles.srt")
    with open(master_srt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(master_srt_blocks) + "\n")

    print("\n" + "=" * 60)
    print(f"Compiled timeline saved to: {timeline_json_path}")
    print(f"Master subtitles saved to: {master_srt_path}")
    print(f"Total Movie Length: {total_frames} frames ({total_duration_sec:.2f} seconds at {fps} FPS)")
    print("=" * 60)

def main():
    if len(sys.argv) > 1:
        ep_dir = sys.argv[1]
    else:
        ep_dir = "episodes/ep01_campfire"

    asyncio.run(compile_voices(ep_dir))

if __name__ == "__main__":
    main()
