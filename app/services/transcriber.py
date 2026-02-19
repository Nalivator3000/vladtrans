import os
import math
from pathlib import Path
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MAX_FILE_SIZE_MB = 24  # Whisper API limit is 25 MB


def transcribe_audio(audio_path: str | Path) -> str:
    """
    Транскрибирует аудио файл через OpenAI Whisper API.
    Если файл > 24 MB — режет на чанки и склеивает транскрипты.
    Язык: грузинский (ka).
    """
    audio_path = Path(audio_path)
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)

    if file_size_mb <= MAX_FILE_SIZE_MB:
        return _transcribe_single(audio_path)
    else:
        return _transcribe_chunked(audio_path)


def _transcribe_single(audio_path: Path) -> str:
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ka",
            response_format="text",
        )
    return result


def _transcribe_chunked(audio_path: Path) -> str:
    """
    Режет аудио на чанки по ~10 минут через ffmpeg и транскрибирует каждый.
    Требует ffmpeg в системе.
    """
    import subprocess
    import tempfile

    chunks_dir = Path(tempfile.mkdtemp())
    chunk_pattern = str(chunks_dir / "chunk_%03d.mp3")

    # Нарезаем по 600 секунд (10 минут)
    subprocess.run(
        [
            "ffmpeg", "-i", str(audio_path),
            "-f", "segment", "-segment_time", "600",
            "-c", "copy", chunk_pattern,
        ],
        check=True,
        capture_output=True,
    )

    chunks = sorted(chunks_dir.glob("chunk_*.mp3"))
    transcripts = [_transcribe_single(chunk) for chunk in chunks]

    # Cleanup
    for chunk in chunks:
        chunk.unlink()
    chunks_dir.rmdir()

    return " ".join(transcripts)
