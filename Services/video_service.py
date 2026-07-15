import os
import base64
import tempfile
import cv2                          # opencv for frame extraction
from moviepy import VideoFileClip
from groq import Groq
from dotenv import load_dotenv
from Services.audio_service import transcribe_audio

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# How often to extract a frame — every 30 seconds by default
# Lower = more frames = more API calls = more detail but slower
FRAME_INTERVAL_SECONDS = 30

def extract_audio_from_video(video_path: str) -> bytes:
    """
    Extracts audio track from video file.
    Returns audio as bytes (mp3 format).
    """
    # Load video
    video = VideoFileClip(video_path)

    # Write audio to a temp file, then read as bytes
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
        temp_audio_path = temp_audio.name
    
    if video.audio is None:
        raise ValueError("The video has no audio track")
    video.audio.write_audiofile(temp_audio_path, logger=None)  # logger=None suppresses output
    video.close()

    with open(temp_audio_path, "rb") as f:
        audio_bytes = f.read()

    os.unlink(temp_audio_path)  # clean up temp file
    return audio_bytes


def extract_key_frames(video_path: str) -> list[bytes]:
    """
    Extracts one frame every FRAME_INTERVAL_SECONDS from the video.
    Returns list of JPEG image bytes.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)                    # frames per second
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if fps<=0:
        raise ValueError("Frames is less than or equal to zero")
    duration = total_frames / fps                       # video duration in seconds

    frame_bytes_list = []
    current_second = 0

    while current_second < duration:
        # Jump to the frame at current_second
        frame_number = int(current_second * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        success, frame = cap.read()
        if not success:
            break

        # Encode frame as JPEG bytes
        success, buffer = cv2.imencode(".jpg", frame)
        if success:
            frame_bytes_list.append(buffer.tobytes())

        current_second += FRAME_INTERVAL_SECONDS

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
    Returns dict with transcript, frame_descriptions, combined_summary
    """
    
    # Step 1 — Extract and transcribe audio
    print(f"[Video] Extracting audio from {filename}...")
    audio_bytes = extract_audio_from_video(video_path)
    transcript = transcribe_audio(audio_bytes, filename.replace(".mp4", ".mp3"))

    # Step 2 — Extract key frames
    print(f"[Video] Extracting key frames...")
    frames = extract_key_frames(video_path)
    print(f"[Video] Extracted {len(frames)} frames. Describing each...")

    # Step 3 — Describe each frame
    frame_descriptions = []
    for i, frame_bytes in enumerate(frames):
        print(f"[Video] Describing frame {i + 1}/{len(frames)}...")
        description = describe_frame(frame_bytes, i + 1)
        frame_descriptions.append(f"Frame {i + 1}: {description}")

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
        "transcript": transcript,
        "frame_descriptions": frame_descriptions,
        "combined_summary": combined_summary
    }