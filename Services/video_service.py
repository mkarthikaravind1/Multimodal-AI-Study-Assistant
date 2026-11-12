import os
import base64
import tempfile
import cv2                          # opencv for frame extraction
from moviepy import VideoFileClip
from groq import Groq
from dotenv import load_dotenv
from Services.audio_service import transcribe_with_segments
from Services.citations import format_timestamp

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Frame sampling: at most MAX_FRAMES frames, evenly spaced across the video,
# and never closer than MIN_FRAME_INTERVAL_SECONDS apart.
# Each frame is one vision API call, so this caps the cost of any video at
# MAX_FRAMES calls (the old fixed 30 s interval meant 120 calls for 1 hour).
MAX_FRAMES = 8
MIN_FRAME_INTERVAL_SECONDS = 5

def extract_audio_from_video(video_path: str) -> bytes | None:
    """
    Extracts audio track from video file.
    Returns audio as bytes (mp3 format), or None if the video has no audio
    (e.g. a silent screen recording).
    The video is always closed — on Windows an open handle would stop the
    caller from deleting the temp video file.
    """
    video = VideoFileClip(video_path)
    try:
        if video.audio is None:
            return None

        fd, temp_audio_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)   # moviepy opens the path itself
        try:
            video.audio.write_audiofile(temp_audio_path, logger=None)  # logger=None suppresses output
            with open(temp_audio_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(temp_audio_path)  # always clean up temp audio
    finally:
        video.close()


def extract_key_frames(video_path: str) -> list[tuple[float, bytes]]:
    """
    Extracts up to MAX_FRAMES evenly spaced frames from the video.
    Returns list of (timestamp_in_seconds, JPEG bytes).
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)                    # frames per second
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if fps <= 0:
        cap.release()   # release before raising so the file can be deleted
        raise ValueError("Could not read the video's frame rate — the file may be corrupt.")
    duration = total_frames / fps                       # video duration in seconds

    interval = max(MIN_FRAME_INTERVAL_SECONDS, duration / MAX_FRAMES)

    frame_bytes_list = []
    current_second = 0

    while current_second < duration and len(frame_bytes_list) < MAX_FRAMES:
        # Jump to the frame at current_second
        frame_number = int(current_second * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        success, frame = cap.read()
        if not success:
            break

        # Encode frame as JPEG bytes
        success, buffer = cv2.imencode(".jpg", frame)
        if success:
            frame_bytes_list.append((current_second, buffer.tobytes()))

        current_second += interval

    cap.release()
    return frame_bytes_list


def describe_frame(frame_bytes: bytes, frame_number: int) -> str:
    """
    Sends a single frame to Vision LLM.
    Returns description of what's in the frame.
    """
    base64_image = base64.b64encode(frame_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            f"This is frame {frame_number} from an educational video. "
                            "Describe what is shown — focus on any diagrams, text, "
                            "equations, code, or visual concepts that would help a "
                            "student understand the content."
                        )
                    }
                ]
            }
        ],
        temperature=0.5,
        max_tokens=512      # shorter per frame
    )

    return response.choices[0].message.content or ""


def analyze_video(video_path: str, filename: str) -> dict:
    """
    Full pipeline:
    1. Extract + transcribe audio
    2. Extract + describe key frames
    3. Combine into a structured analysis
    Returns dict with transcript, timed segments, timed frames and combined_summary
    """
    
    # Step 1 — Extract and transcribe audio
    print(f"[Video] Extracting audio from {filename}...")
    audio_bytes = extract_audio_from_video(video_path)
    if audio_bytes:
        # The bytes are always mp3, so the name must end in .mp3 whatever the
        # original extension was (.mov, .webm, .MP4 …) — Whisper uses it to detect format.
        audio_filename = os.path.splitext(filename)[0] + ".mp3"
        transcript, segments = transcribe_with_segments(audio_bytes, audio_filename)
    else:
        print(f"[Video] {filename} has no audio track — using frames only.")
        transcript, segments = "(This video has no audio track.)", []

    # Step 2 — Extract key frames
    print(f"[Video] Extracting key frames...")
    frames = extract_key_frames(video_path)
    print(f"[Video] Extracted {len(frames)} frames. Describing each...")

    # Step 3 — Describe each frame
    frame_descriptions = []
    timed_frames = []          # [{"start": seconds, "text": description}] for citations
    for i, (second, frame_bytes) in enumerate(frames):
        print(f"[Video] Describing frame {i + 1}/{len(frames)}...")
        description = describe_frame(frame_bytes, i + 1)
        frame_descriptions.append(f"Frame at {format_timestamp(second)}: {description}")
        timed_frames.append({"start": second, "text": description})

    # Step 4 — Combine transcript + frame descriptions into one summary
    combined_text = f"""
VIDEO TRANSCRIPT:
{transcript}

KEY FRAME DESCRIPTIONS:
{chr(10).join(frame_descriptions)}
"""

    # Step 5 — Ask LLM to create a unified summary from both sources
    summary_response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are an educational content summarizer."
            },
            {
                "role": "user",
                "content": (
                    f"Based on this video transcript and frame descriptions, "
                    f"create a comprehensive study summary:\n\n{combined_text}"
                )
            }
        ],
        temperature=0.7,
        max_tokens=1024
    )

    combined_summary = summary_response.choices[0].message.content or ""

    return {
        "has_audio": bool(audio_bytes),
        "transcript": transcript,
        "segments": segments,
        "frame_descriptions": frame_descriptions,
        "timed_frames": timed_frames,
        "combined_summary": combined_summary
    }