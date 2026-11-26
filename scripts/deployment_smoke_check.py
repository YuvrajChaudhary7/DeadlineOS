"""Verify an authenticated upload survives an Azure Container App revision."""
import argparse
import hashlib
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


def request_bytes(url, method="GET", token=None, body=None, content_type=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HTTP {error.code} for {method} {url}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Request failed for {method} {url}: {error.reason}") from error


def json_request(url, method="GET", token=None, value=None):
    body = json.dumps(value).encode("utf-8") if value is not None else None
    _, response = request_bytes(url, method, token, body, "application/json" if body else None)
    return json.loads(response) if response else {}


def login(base_url):
    email = os.environ.get("DEADLINEOS_SMOKE_EMAIL", "")
    password = os.environ.get("DEADLINEOS_SMOKE_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("Set DEADLINEOS_SMOKE_EMAIL and DEADLINEOS_SMOKE_PASSWORD for the upload smoke check")
    response = json_request(f"{base_url}/api/auth/login", "POST", value={"email": email, "password": password})
    token = response.get("access_token")
    if not token:
        raise RuntimeError("Login did not return an access token")
    return token


def prepare(args):
    token = login(args.base_url)
    nonce = uuid.uuid4().hex
    filename = f"deadlineos-smoke-{nonce}.txt"
    payload = f"DeadlineOS persistence check {nonce}\n".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    boundary = f"----DeadlineOS{nonce}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n\r\n"
    ).encode("ascii") + payload + f"\r\n--{boundary}--\r\n".encode("ascii")
    _, response = request_bytes(
        f"{args.base_url}/api/projects/{args.project_id}/files",
        "POST", token, body, f"multipart/form-data; boundary={boundary}"
    )
    file_id = json.loads(response).get("id")
    if not file_id:
        raise RuntimeError("Upload did not return a file id")
    if args.output:
        with open(args.output, "a", encoding="utf-8") as output:
            output.write(f"file_id={file_id}\nsha256={digest}\n")
    print(f"Prepared upload persistence check (file id {file_id}).")


def verify(args):
    token = login(args.base_url)
    url = f"{args.base_url}/api/projects/{args.project_id}/files/{args.file_id}"
    _, payload = request_bytes(url, token=token)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != args.sha256:
        raise RuntimeError("Uploaded file content did not survive the deployment unchanged")
    print("Uploaded file survived the new revision unchanged.")


def cleanup(args):
    token = login(args.base_url)
    url = f"{args.base_url}/api/projects/{args.project_id}/files/{args.file_id}"
    try:
        request_bytes(url, "DELETE", token)
    except RuntimeError as error:
        if "HTTP 404" not in str(error):
            raise
    print("Removed the temporary persistence-check upload.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify", "cleanup"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--base-url", required=True)
        sub.add_argument("--project-id", required=True, type=int)
        if command != "prepare":
            sub.add_argument("--file-id", required=True, type=int)
        if command == "verify":
            sub.add_argument("--sha256", required=True)
        if command == "prepare":
            sub.add_argument("--output")
    args = parser.parse_args()
    args.base_url = args.base_url.rstrip("/")
    try:
        {"prepare": prepare, "verify": verify, "cleanup": cleanup}[args.command](args)
    except RuntimeError as error:
        parser.exit(1, f"Smoke check failed: {error}\n")


if __name__ == "__main__":
    main()