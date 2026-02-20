import logging
import os
import tempfile
from pathlib import Path

import httpx
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
log = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 24  # Whisper API limit is 25 MB

# Языки, поддерживаемые Whisper API как явный параметр.
# Georgian ('ka') здесь отсутствует — для него используем translations endpoint.
WHISPER_SUPPORTED_LANGUAGES = {
    "af", "ar", "hy", "az", "be", "bs", "bg", "ca", "zh", "hr", "cs", "da",
    "nl", "en", "et", "fi", "fr", "gl", "de", "el", "he", "hi", "hu", "id",
    "it", "ja", "kn", "kk", "ko", "lv", "lt", "mk", "ms", "mr", "mi", "ne",
    "no", "fa", "pl", "pt", "ro", "ru", "sk", "sl", "es", "sw", "sv", "tl",
    "ta", "th", "tr", "uk", "ur", "vi", "cy",
}


def transcribe_audio(audio_source: str | Path, language: str = "ka") -> str:
    """
    Транскрибирует аудио через OpenAI Whisper API.
    Принимает либо локальный путь, либо HTTP(S) URL.

    Если язык не поддерживается Whisper API (напр. Georgian 'ka') —
    использует /audio/translations (→ English перевод).
    Если поддерживается — использует /audio/transcriptions с явным языком.

    Если файл > 24 МБ — нарезает на чанки через ffmpeg.
    """
    source = str(audio_source)

    if source.startswith("http://") or source.startswith("https://"):
        return _transcribe_url(source, language)

    return _transcribe_file(Path(source), language)


def _transcribe_url(url: str, language: str) -> str:
    """Скачивает аудио по URL во временный файл и транскрибирует."""
    clean_url = url.split("?")[0]
    suffix = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ".mp3"
    if len(suffix) > 5:
        suffix = ".mp3"

    with httpx.Client(timeout=120) as http:
        response = http.get(url)
        response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = Path(tmp.name)

    try:
        return _transcribe_file(tmp_path, language)
    finally:
        tmp_path.unlink(missing_ok=True)


def _transcribe_file(audio_path: Path, language: str) -> str:
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)

    if file_size_mb <= MAX_FILE_SIZE_MB:
        return _transcribe_single(audio_path, language)
    else:
        return _transcribe_chunked(audio_path, language)


def _transcribe_single(audio_path: Path, language: str) -> str:
    use_translation = language not in WHISPER_SUPPORTED_LANGUAGES

    with open(audio_path, "rb") as f:
        if use_translation:
            log.info(f"Language '{language}' not supported by Whisper API — using translations endpoint (→ English)")
            result = client.audio.translations.create(
                model="whisper-1",
                file=f,
                response_format="text",
                prompt="This is a sales call from a call center. Operator sells health products to a client.",
            )
        else:
            log.info(f"Using transcriptions endpoint with language='{language}'")
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=language,
                response_format="text",
            )

    return result


def _transcribe_chunked(audio_path: Path, language: str) -> str:
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
    transcripts = [_transcribe_single(chunk, language) for chunk in chunks]

    for chunk in chunks:
        chunk.unlink()
    chunks_dir.rmdir()

    return " ".join(transcripts)
