import logging
import os
import tempfile
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 24  # Whisper limit is 25 MB

# Groq поддерживает Georgian и ещё 98 языков (whisper-large-v3).
# Для языков НЕ поддерживаемых Groq используем OpenAI translations → English.
GROQ_SUPPORTED_LANGUAGES = {
    "af", "ar", "hy", "az", "be", "bs", "bg", "ca", "zh", "hr", "cs", "da",
    "nl", "en", "et", "fi", "fr", "gl", "de", "el", "he", "hi", "hu", "id",
    "it", "ja", "kn", "kk", "ko", "lv", "lt", "mk", "ms", "mr", "mi", "ne",
    "no", "fa", "pl", "pt", "ro", "ru", "sk", "sl", "es", "sw", "sv", "tl",
    "ta", "th", "tr", "uk", "ur", "vi", "cy",
    # Языки поддерживаемые Groq но не OpenAI Whisper API:
    "ka",   # Georgian
    "mn",   # Mongolian
    "si",   # Sinhala
    "am",   # Amharic
}


def _get_groq_client():
    """Создаёт Groq клиент. Требует GROQ_API_KEY в окружении."""
    try:
        from groq import Groq
        return Groq(api_key=os.environ["GROQ_API_KEY"])
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")
    except KeyError:
        raise RuntimeError("GROQ_API_KEY not set in environment")


def _get_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def transcribe_audio(audio_source: str | Path, language: str = "ka") -> str:
    """
    Транскрибирует аудио через Groq Whisper large-v3 (основной провайдер).
    Если язык не поддерживается Groq — fallback на OpenAI translations → English.
    Принимает локальный путь или HTTP(S) URL.
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
    if language in GROQ_SUPPORTED_LANGUAGES:
        return _transcribe_groq(audio_path, language)
    else:
        log.warning(f"Language '{language}' not supported by Groq — falling back to OpenAI translations")
        return _transcribe_openai_translation(audio_path)


def _to_wav(audio_path: Path) -> Path:
    """
    Конвертирует аудио в WAV 16kHz mono через ffmpeg.
    Нужно для нестандартных форматов (MPEG 2.5, 8kHz) которые Groq не принимает.
    """
    import subprocess
    wav_path = audio_path.with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-ar", "16000", "-ac", "1", "-f", "wav",
            str(wav_path),
        ],
        check=True,
        capture_output=True,
    )
    return wav_path


def _transcribe_groq(audio_path: Path, language: str) -> str:
    """Транскрипция через Groq Whisper large-v3-turbo (поддерживает Georgian).
    Перед отправкой конвертирует файл в WAV 16kHz — на случай нестандартных
    форматов АТС (MPEG 2.5 @ 8kHz и др.).
    """
    client = _get_groq_client()

    wav_path = None
    try:
        try:
            wav_path = _to_wav(audio_path)
            send_path = wav_path
            log.info(f"Converted {audio_path.name} → WAV 16kHz for Groq")
        except Exception as e:
            log.warning(f"ffmpeg conversion failed ({e}), sending original file")
            send_path = audio_path

        with open(send_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                language=language,
                response_format="text",
            )
    finally:
        if wav_path and wav_path.exists():
            wav_path.unlink(missing_ok=True)

    log.info(f"Groq transcription done for {audio_path.name}")
    return result


def _transcribe_openai_translation(audio_path: Path) -> str:
    """Fallback: OpenAI audio/translations → English (для неподдерживаемых языков)."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with open(audio_path, "rb") as f:
        result = client.audio.translations.create(
            model="whisper-1",
            file=f,
            response_format="text",
            prompt="This is a sales call from a call center.",
        )
    log.info(f"OpenAI translation done for {audio_path.name}")
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
