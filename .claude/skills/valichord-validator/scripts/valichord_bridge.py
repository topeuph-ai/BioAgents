#!/usr/bin/env python3
"""
ValiChord Bridge Script
Provides CLI access to the ValiChord bridge API for deposit submission,
hash computation, and attestation submission.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen, urlretrieve
from urllib.error import HTTPError, URLError

# Load .env from project root
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent.parent.parent
    load_dotenv(dotenv_path=project_root / ".env")
except ImportError:
    pass

DEFAULT_API_URL = "http://localhost:5000"


def _api_url() -> str:
    return os.environ.get("VALICHORD_API_URL", DEFAULT_API_URL).rstrip("/")


def _api_key() -> str | None:
    return os.environ.get("VALICHORD_API_KEY") or None


def compute_file_hash(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_download_and_hash(args) -> dict:
    """Download a URL (or hash a local file) and return data_hash + local_path."""
    if args.file:
        local_path = args.file
        if not Path(local_path).exists():
            raise FileNotFoundError(f"File not found: {local_path}")
    elif args.url:
        fd, tmp = tempfile.mkstemp(suffix=".zip", prefix="valichord_deposit_")
        os.close(fd)
        if args.verbose:
            print(f"Downloading {args.url} → {tmp}", file=sys.stderr)
        urlretrieve(args.url, tmp)
        local_path = tmp
    else:
        raise ValueError("Either --url or --file must be provided")

    data_hash = compute_file_hash(local_path)
    return {"data_hash": data_hash, "local_path": local_path}


def cmd_inspect(args) -> dict:
    """List files in a deposit ZIP and classify by type."""
    path = args.file
    if not path or not Path(path).exists():
        raise FileNotFoundError(f"File not found: {path}")

    DATA_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".parquet",
                 ".h5", ".hdf5", ".mat", ".rda", ".rdata", ".rds",
                 ".tif", ".tiff", ".nc", ".npy", ".npz"}
    CODE_EXTS = {".py", ".r", ".rmd", ".ipynb", ".sh", ".do", ".m",
                 ".jl", ".sas", ".spv", ".stata"}
    ENV_EXTS = {".txt", ".toml", ".lock", ".cfg", ".ini", ".yaml", ".yml"}

    scripts, data_files, readmes, env_files, other = [], [], [], [], []

    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            p = Path(name)
            parts = p.parts
            if "__MACOSX" in parts or p.name.startswith("._"):
                continue
            if p.name.lower() in {"readme.md", "readme.txt", "readme.rst", "readme"}:
                readmes.append(name)
            elif p.suffix.lower() in CODE_EXTS:
                scripts.append(name)
            elif p.suffix.lower() in DATA_EXTS:
                data_files.append(name)
            elif p.name.lower() in {"requirements.txt", "environment.yml",
                                     "environment.yaml", "renv.lock",
                                     "packages.txt", "install.R"} or \
                 (p.suffix.lower() in ENV_EXTS and
                  any(kw in p.name.lower() for kw in {"require", "environ", "depend",
                                                        "install", "setup", "lock"})):
                env_files.append(name)
            elif not p.name.endswith("/"):
                other.append(name)

    return {
        "scripts": scripts,
        "data_files": data_files,
        "readmes": readmes,
        "env_files": env_files,
        "other": other,
        "total_files": len(scripts) + len(data_files) + len(readmes) + len(env_files) + len(other),
    }


def cmd_submit_attestation(args) -> dict:
    """Submit a fast-path attestation to POST /attest."""
    api_url = args.api_url or _api_url()
    api_key = args.api_key or _api_key()

    if not args.data_hash or len(args.data_hash) != 64:
        raise ValueError("--data-hash must be a 64-character hex SHA-256 string")
    if args.outcome not in ("Reproduced", "PartiallyReproduced", "FailedToReproduce"):
        raise ValueError("--outcome must be Reproduced, PartiallyReproduced, or FailedToReproduce")
    if args.confidence not in ("High", "Medium", "Low"):
        raise ValueError("--confidence must be High, Medium, or Low")

    # Build multipart/form-data manually using urllib
    boundary = "----ValiChordBoundary7MA4YWxkTrZu0gW"
    lines = []

    def add_field(name: str, value: str):
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        lines.append(b"")
        lines.append(value.encode("utf-8"))

    add_field("data_hash", args.data_hash.lower())
    add_field("outcome", args.outcome)
    add_field("confidence", args.confidence)
    add_field("notes", (args.notes or "")[:2000])
    add_field("discipline", args.discipline or '{"type":"ComputationalBiology"}')
    lines.append(f"--{boundary}--".encode())

    body = b"\r\n".join(lines)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    if api_key:
        headers["X-API-Key"] = api_key

    url = f"{api_url}/attest"
    if args.verbose:
        print(f"POST {url}", file=sys.stderr)

    try:
        req = Request(url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body_text = e.read().decode() if e.fp else str(e)
        raise Exception(f"HTTP {e.code}: {body_text}")
    except URLError as e:
        raise Exception(f"Connection error: {e.reason}")


def cmd_get_result(args) -> dict:
    """Poll GET /result/<job_id> for a submitted deposit job."""
    api_url = args.api_url or _api_url()
    api_key = args.api_key or _api_key()
    job_id = args.job_id
    if not job_id:
        raise ValueError("--job-id is required for get-result mode")

    url = f"{api_url}/result/{job_id}"
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    if args.verbose:
        print(f"GET {url}", file=sys.stderr)

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body_text = e.read().decode() if e.fp else str(e)
        raise Exception(f"HTTP {e.code}: {body_text}")
    except URLError as e:
        raise Exception(f"Connection error: {e.reason}")


def main():
    parser = argparse.ArgumentParser(
        description="ValiChord Bridge CLI — interact with the ValiChord bridge API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:

  download-and-hash   Download a deposit URL (or hash a local file) and return data_hash.
  inspect             List and classify files inside a deposit ZIP.
  submit-attestation  Submit a validator attestation to POST /attest.
  get-result          Poll GET /result/<job_id> for a submitted deposit job.

Examples:

  # Download and hash a remote deposit
  %(prog)s --mode download-and-hash --url "https://osf.io/abc123/download"

  # Hash a local deposit file
  %(prog)s --mode download-and-hash --file /tmp/deposit.zip

  # Inspect deposit contents
  %(prog)s --mode inspect --file /tmp/deposit.zip

  # Submit attestation (conductor online)
  %(prog)s --mode submit-attestation \\
    --data-hash "$(cat hash.txt)" \\
    --outcome Reproduced \\
    --confidence High \\
    --discipline '{"type":"ComputationalBiology"}' \\
    --notes "Ran main_analysis.R; all 47 p-values reproduced within FP tolerance."

  # Poll for result of a deposit job
  %(prog)s --mode get-result --job-id "3f2a9c81-..."
        """
    )

    parser.add_argument("--mode", required=True,
                        choices=["download-and-hash", "inspect",
                                 "submit-attestation", "get-result"],
                        help="Operation mode")

    # Source
    parser.add_argument("--url", help="URL of the deposit ZIP to download")
    parser.add_argument("--file", help="Local path to a deposit ZIP")

    # API connection
    parser.add_argument("--api-url",
                        help=f"ValiChord bridge API base URL (default: $VALICHORD_API_URL or {DEFAULT_API_URL})")
    parser.add_argument("--api-key",
                        help="API key (default: $VALICHORD_API_KEY)")

    # Attestation fields
    parser.add_argument("--data-hash",
                        help="64-char hex SHA-256 of the deposit (required for submit-attestation)")
    parser.add_argument("--outcome",
                        choices=["Reproduced", "PartiallyReproduced", "FailedToReproduce"],
                        help="Replication verdict")
    parser.add_argument("--confidence",
                        choices=["High", "Medium", "Low"],
                        default="Medium",
                        help="Confidence level (default: Medium)")
    parser.add_argument("--discipline",
                        default='{"type":"ComputationalBiology"}',
                        help='Discipline JSON, e.g. \'{"type":"MachineLearning"}\'')
    parser.add_argument("--notes", default="",
                        help="Replication notes, max 2000 chars")

    # Job polling
    parser.add_argument("--job-id", help="Job ID for get-result mode")

    parser.add_argument("--verbose", action="store_true",
                        help="Print status messages to stderr")

    args = parser.parse_args()

    try:
        if args.mode == "download-and-hash":
            result = cmd_download_and_hash(args)
        elif args.mode == "inspect":
            result = cmd_inspect(args)
        elif args.mode == "submit-attestation":
            result = cmd_submit_attestation(args)
        elif args.mode == "get-result":
            result = cmd_get_result(args)
        else:
            print(f"Unknown mode: {args.mode}", file=sys.stderr)
            sys.exit(1)

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
