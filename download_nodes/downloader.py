import ipaddress
import mimetypes
import os
import socket
import tempfile
from urllib.parse import urlparse

import numpy as np
import requests
import torch
import torchaudio
from PIL import Image

import folder_paths


ALLOWED_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

ALLOWED_AUDIO_MIMES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/ogg",
    "audio/x-flac",
    "audio/mp4",
}

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}


def _is_blocked_ip(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return True

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue

        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    # Accept http/https with host
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        if _is_blocked_ip(parsed.hostname):
            raise ValueError("Refusing to access private or invalid host")
        return url
    # Accept file:// or local paths (absolute or relative to ComfyUI input dir)
    if parsed.scheme == "file":
        path = parsed.path
    elif parsed.scheme == "" and parsed.netloc == "":
        # First try as-is, then relative to input directory
        if os.path.exists(url):
            path = url
        else:
            candidate = os.path.join(folder_paths.get_input_directory(), url)
            path = candidate if os.path.exists(candidate) else url
    else:
        raise ValueError("URL must be http/https with a host or an existing local path")
    if not os.path.exists(path):
        raise ValueError(f"Local file not found: {path}")
    return path


def _download_to_temp(url: str, max_bytes: int, timeout: tuple[float, float]):
    headers = {
        "User-Agent": "ComfyUI-DownloadFile/1.0 (+https://github.com/serious-factory/ComfyUI-DownloadFile)"
    }
    response = requests.get(url, stream=True, timeout=timeout, allow_redirects=True, headers=headers)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    suffix = ""
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext:
        suffix = ext
    else:
        guessed = mimetypes.guess_extension(content_type) if content_type else None
        if guessed:
            suffix = guessed

    temp_dir = folder_paths.get_temp_directory()
    temp_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=suffix or "")
    temp_path = temp_file.name
    written = 0

    try:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            written += len(chunk)
            if written > max_bytes:
                raise ValueError("File exceeds allowed size limit")
            temp_file.write(chunk)
    finally:
        temp_file.close()
        if written == 0:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise ValueError("Empty response body")

    try:
        folder_paths.add_temp_file(os.path.basename(temp_path))
    except Exception:
        # Non-fatal; continue even if registration fails
        pass

    return temp_path, content_type


def _load_image(path: str):
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        array = np.asarray(rgb).astype(np.float32) / 255.0
        tensor = torch.from_numpy(array).unsqueeze(0)
    return tensor


def _load_audio(path: str):
    waveform, sample_rate = torchaudio.load(path)
    return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}


class DownloadFile:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": "https://example.com/file.jpg"}),
            },
            "optional": {
                "expect_type": (["auto", "image", "audio"], {"default": "auto"}),
                "max_mb": ("INT", {"default": 50, "min": 1, "max": 200, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING", "STRING")
    RETURN_NAMES = ("image", "audio", "filepath", "mime")
    FUNCTION = "download_file"
    CATEGORY = "Utilities/Download"

    def download_file(self, url, expect_type="auto", max_mb=50):
        empty_image = torch.zeros((1, 1, 1, 3), dtype=torch.float32)
        empty_audio = {"waveform": torch.zeros((1, 1, 1)), "sample_rate": 44100}

        safe_url = _validate_url(url)
        timeout = (5.0, 15.0)
        max_bytes = max_mb * 1024 * 1024
        try:
            if safe_url.startswith("http"):
                temp_path, content_type = _download_to_temp(safe_url, max_bytes=max_bytes, timeout=timeout)
            else:
                # Local file path
                temp_path = safe_url
                content_type = mimetypes.guess_type(temp_path)[0] or ""
        except Exception as e:
            raise ValueError(f"DownloadFile error: {e}")

        ext = os.path.splitext(temp_path)[1].lower()

        def is_image():
            if expect_type == "image":
                return True
            if content_type in ALLOWED_IMAGE_MIMES:
                return True
            return ext in ALLOWED_IMAGE_EXTS

        def is_audio():
            if expect_type == "audio":
                return True
            if content_type in ALLOWED_AUDIO_MIMES:
                return True
            return ext in ALLOWED_AUDIO_EXTS

        if is_image():
            image = _load_image(temp_path)
            return (image, empty_audio, temp_path, content_type or "")

        if is_audio():
            audio = _load_audio(temp_path)
            return (empty_image, audio, temp_path, content_type or "")

        raise ValueError("Unsupported file type; only image/audio are allowed")


NODE_CLASS_MAPPINGS = {
    "DownloadFile": DownloadFile,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DownloadFile": "Download File",
}
