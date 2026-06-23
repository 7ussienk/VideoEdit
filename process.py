import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SCRIPT_DIR = Path(__file__).parent.resolve()
theme = json.load(open(SCRIPT_DIR / "theme.json"))

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def validate_video(input_path):
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"الملف غير موجود: {input_path}")

    if path.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        raise ValueError(f"صيغة غير مدعومة: {path.suffix} — المدعوم: mp4, mov, mkv")

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"فشل ffprobe: {result.stderr}")

    info = json.loads(result.stdout)
    duration = float(info["format"]["duration"])

    max_dur = theme["output"]["maxDurationSeconds"]
    if duration > max_dur:
        raise ValueError(f"الفيديو طويل جداً: {duration:.0f} ثانية (الحد الأقصى {max_dur} ثانية)")

    return duration


def extract_audio(input_path):
    audio_path = "temp_audio.mp3"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-q:a", "0", "-map", "a", audio_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"فشل استخراج الصوت: {result.stderr}")
    return audio_path


def transcribe(audio_path, language="ar"):
    with open(audio_path, "rb") as f:
        response = _get_client().audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            language=language
        )
    return [{"start": s.start, "end": s.end, "text": s.text} for s in response.segments]


def _seconds_to_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape_ass_text(text):
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    return text


def generate_ass(segments, language="ar"):
    ass_path = "temp_captions.ass"

    header = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Cairo Bold,52,&H00FFFFFF,&H000000FF,&H00000000,&H40FFFFFF,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    for seg in segments:
        start = _seconds_to_ass_time(seg["start"])
        end = _seconds_to_ass_time(seg["end"])
        text = _escape_ass_text(seg["text"].strip())
        if language == "ar":
            text = "‫" + text
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")

    return ass_path


def render_video(input_path, use_music=False):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = f"output/final_{timestamp}.mp4"

    logo_path = theme["watermark"]["path"]
    has_logo = Path(logo_path).exists()
    music_path = theme["music"]["path"]
    has_music = use_music and theme["music"]["enabled"] and Path(music_path).exists()

    fonts_dir = str(SCRIPT_DIR / "assets" / "fonts")
    ass_path_escaped = "temp_captions.ass".replace(":", "\\:")

    inputs = ["-i", str(input_path)]
    input_idx = 1

    logo_idx = None
    if has_logo:
        inputs += ["-i", logo_path]
        logo_idx = input_idx
        input_idx += 1

    music_idx = None
    if has_music:
        inputs = inputs[:2] + ["-stream_loop", "-1", "-i", music_path] + inputs[2:]
        if has_logo:
            logo_idx += 1
            music_idx = 1
        else:
            music_idx = input_idx
        input_idx += 1

    filter_parts = []

    if has_logo:
        scale_pct = theme["watermark"]["scalePercent"] / 100
        opacity = theme["watermark"]["opacity"]
        mx = theme["watermark"]["marginX"]
        my = theme["watermark"]["marginY"]
        filter_parts.append(
            f"[0:v]subtitles='{ass_path_escaped}':fontsdir='{fonts_dir}'[sub]"
        )
        filter_parts.append(
            f"[{logo_idx}:v]scale=iw*{scale_pct}:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity}[logo]"
        )
        filter_parts.append(
            f"[sub][logo]overlay=W-w-{mx}:{my}[v]"
        )
    else:
        filter_parts.append(
            f"[0:v]subtitles='{ass_path_escaped}':fontsdir='{fonts_dir}'[v]"
        )

    audio_out = []
    if has_music:
        vol = theme["music"]["volume"]
        filter_parts.append(f"[{music_idx}:a]volume={vol}[mv]")
        filter_parts.append(f"[0:a][mv]amix=inputs=2:duration=first[a]")
        audio_out = ["-map", "[a]"]
    else:
        audio_out = ["-c:a", "copy"]

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[v]",
    ] + audio_out + [
        "-c:v", "libx264", "-b:v", theme["output"]["videoBitrate"],
    ]

    if has_music:
        cmd += ["-c:a", "aac", "-b:a", theme["output"]["audioBitrate"]]
    elif audio_out == ["-c:a", "copy"]:
        pass
    else:
        cmd += ["-c:a", "aac", "-b:a", theme["output"]["audioBitrate"]]

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"فشل FFmpeg:\n{result.stderr}")

    return output_path


def cleanup():
    for f in ["temp_audio.mp3", "temp_captions.ass"]:
        try:
            os.remove(f)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Video Theme Applier")
    parser.add_argument("--input", required=True, help="مسار الفيديو")
    parser.add_argument("--music", action="store_true", help="تفعيل الموزيك الخلفي")
    parser.add_argument("--lang", default="ar", choices=["ar", "en"], help="لغة النص")
    args = parser.parse_args()

    print("\n\U0001f3ac Video Theme Applier")
    print("━" * 40)

    try:
        print("① التحقق من الفيديو...", end=" ", flush=True)
        duration = validate_video(args.input)
        print(f"✅ ({duration:.0f} ثانية)")

        print("② استخراج الصوت...", end=" ", flush=True)
        audio = extract_audio(args.input)
        print("✅")

        print("③ Whisper API...", end=" ", flush=True)
        segments = transcribe(audio, args.lang)
        print(f"✅ ({len(segments)} جملة)")

        print("④ توليد Captions...", end=" ", flush=True)
        generate_ass(segments, args.lang)
        print("✅")

        print("⑤ تطبيق الثيم...", end=" ", flush=True)
        output = render_video(args.input, args.music)
        print("✅")

        print("━" * 40)
        print(f"✅ الفيديو جاهز: {output}\n")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
