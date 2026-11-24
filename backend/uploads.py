"""Content validation and optional fail-closed ClamAV INSTREAM scanning."""
from io import BytesIO
import os
import socket
import struct
import zipfile

from werkzeug.utils import secure_filename


TEXT_TYPES = {"txt", "md", "py", "java", "cpp", "c", "js", "csv"}
ZIP_TYPES = {"zip", "docx", "xlsx"}


class UploadRejected(ValueError):
    status_code = 400


class UploadTooLarge(UploadRejected):
    status_code = 413


class ScannerUnavailable(RuntimeError):
    status_code = 503


def _verify_content(extension, payload):
    if extension == "pdf":
        return payload.startswith(b"%PDF-")
    if extension == "png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {"jpg", "jpeg"}:
        return payload.startswith(b"\xff\xd8\xff")
    if extension in ZIP_TYPES:
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                names = set(archive.namelist())
                if extension == "docx": return "[Content_Types].xml" in names and "word/document.xml" in names
                if extension == "xlsx": return "[Content_Types].xml" in names and "xl/workbook.xml" in names
                return bool(names)
        except (zipfile.BadZipFile, OSError):
            return False
    if extension in TEXT_TYPES:
        if b"\x00" in payload: return False
        try: payload.decode("utf-8-sig")
        except UnicodeDecodeError: return False
        return True
    return False


def _clamav_scan(payload):
    host = os.getenv("CLAMAV_HOST")
    required = os.getenv("CLAMAV_REQUIRED", "false").lower() == "true"
    if not host:
        if required: raise ScannerUnavailable("Malware scanning is required but CLAMAV_HOST is not configured")
        return
    try:
        with socket.create_connection((host, int(os.getenv("CLAMAV_PORT", "3310"))), timeout=5) as client:
            client.settimeout(20)
            client.sendall(b"zINSTREAM\0")
            for start in range(0, len(payload), 64 * 1024):
                block = payload[start:start + 64 * 1024]
                client.sendall(struct.pack("!I", len(block)) + block)
            client.sendall(struct.pack("!I", 0))
            response = bytearray()
            while len(response) < 1024 and not response.endswith(b"\n"):
                chunk = client.recv(128)
                if not chunk: break
                response.extend(chunk)
    except (OSError, ValueError) as error:
        if required: raise ScannerUnavailable("Malware scanner is unavailable; upload was rejected") from error
        raise ScannerUnavailable("Configured malware scanner is unavailable; upload was rejected") from error
    verdict = response.decode("utf-8", "replace").strip()
    if "FOUND" in verdict: raise UploadRejected("The uploaded file was flagged by malware scanning")
    if "OK" not in verdict: raise ScannerUnavailable("Malware scanner returned an invalid response; upload was rejected")


def validate_upload(upload, allowed_extensions, max_bytes):
    if not upload or not upload.filename:
        raise UploadRejected("file is required")
    filename = secure_filename(upload.filename)
    if not filename or "." not in filename:
        raise UploadRejected("file type not allowed")
    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in allowed_extensions:
        raise UploadRejected("file type not allowed")
    payload = upload.read(max_bytes + 1)
    upload.stream.seek(0)
    if not payload: raise UploadRejected("empty files are not allowed")
    if len(payload) > max_bytes: raise UploadTooLarge("file exceeds the per-file upload limit")
    if not _verify_content(extension, payload):
        raise UploadRejected("file content does not match its allowed file type")
    _clamav_scan(payload)
    upload.stream.seek(0)
    return filename, len(payload)
