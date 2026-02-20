import os
import tempfile
from pathlib import Path

import httpx
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MAX_FILE_SIZE_MB = 24  # Whisper API limit is 25 MB


def transcribe_audio(audio_source: str | Path) -> str:
    """
    Транскрибирует аудио через OpenAI Whisper API.
    Принимает либо локальный путь, либо HTTP(S) URL.
    Если файл > 24 MB — режет на чанки и склеивает транскрипты.
    Язык: грузинский (ka).
    """
    source = str(audio_source)

    if source.startswith("http://") or source.startswith("https://"):
        return _transcribe_url(source)

    return _transcribe_file(Path(source))


def _transcribe_url(url: str) -> str:
    """Скачивает аудио по URL во временный файл и транскрибирует."""
    # Определяем расширение из URL (до query string)
    clean_url = url.split("?")[0]
    suffix = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ".mp3"
    if len(suffix) > 5:  # нет расширения или оно странное — считаем mp3
        suffix = ".mp3"

    with httpx.Client(timeout=120) as http:
        response = http.get(url)
        response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = Path(tmp.name)

    try:
        return _transcribe_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _transcribe_file(audio_path: Path) -> str:
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

    chunks_dir = Path(tempfile.mkdtemp())
    chunk_pattern = str(chunks_dir / "chunk_%03d.mp3")

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

    for chunk in chunks:
        chunk.unlink()
    chunks_dir.rmdir()

    return " ".join(transcripts)
