import os
import re
import subprocess
import ffmpeg
import imageio_ffmpeg
#import torch

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

def extract_audio(input_path: str, output_path: str):
    """FFmpeg extract audio from input, encode as 64 kbps mono MP3.

    Using MP3 instead of PCM WAV gives a 4× smaller temp file
    (≈0.48 MB/min vs ≈1.9 MB/min) while still being accepted natively
    by Groq's Whisper endpoint.  Speech intelligibility is not affected
    at 64 kbps.
    """
    (
        ffmpeg
        .input(input_path)
        .output(
            output_path,
            acodec='libmp3lame',
            audio_bitrate='64k',
            ac=1,           # mono
            ar='16000',     # 16 kHz — matches Whisper's native rate
        )
        .overwrite_output()
        .run(cmd=ffmpeg_path, quiet=True)
    )

def apply_vad(audio_path: str):
    """VAD disabled in production — torch not available.
    Returns original audio path unchanged."""
    return audio_path

def get_duration(audio_path: str) -> float:
    """Return duration in seconds by parsing ffmpeg stderr (no ffprobe needed)."""
    result = subprocess.run(
        [ffmpeg_path, '-i', audio_path],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    output = result.stderr.decode('utf-8', errors='ignore')
    match = re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', output)
    if not match:
        raise ValueError(f"Could not determine duration for: {audio_path}")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)

def chunk_audio(audio_path: str, chunk_min=10):
    """split into overlapping chunks"""
    duration = get_duration(audio_path)
    chunk_sec = chunk_min * 60
    
    if duration <= chunk_sec:
        return [audio_path]
        
    chunks = []
    overlap = 30  # 30 seconds overlap
    num_chunks = int(duration // chunk_sec) + (1 if duration % chunk_sec > 0 else 0)
    base, ext = os.path.splitext(audio_path)
    
    for i in range(num_chunks):
        start_time = max(0, i * chunk_sec - overlap)
        out_path = f"{base}_chunk_{i}{ext}"
        # Specify duration parameter (t) rather than end time (to) for overlapping
        t_arg = chunk_sec + (overlap * 2)
        
        (
            ffmpeg
            .input(audio_path, ss=start_time, t=t_arg)
            .output(out_path, acodec='libmp3lame', audio_bitrate='64k', ac=1, ar='16000')
            .overwrite_output()
            .run(cmd=ffmpeg_path, quiet=True)
        )
        chunks.append(out_path)
    
    return chunks
