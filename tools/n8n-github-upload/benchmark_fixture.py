#!/usr/bin/env python3
"""Reproduce the 100-file, 30,000,000-byte connector corpus. No network or credentials."""
import argparse
import hashlib
import json
import pathlib
import uuid

def fixture(index, salt):
    value = (salt ^ (((index + 1) * 0x9E3779B1) & 0xFFFFFFFF)) & 0xFFFFFFFF
    data = bytearray(300000)
    for position in range(len(data)):
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= value >> 17
        value ^= (value << 5) & 0xFFFFFFFF
        value &= 0xFFFFFFFF
        data[position] = value & 255
    return bytes(data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--salt", type=int, default=202611061621)
    parser.add_argument("--upload-id", default=None)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    files = []
    for index in range(100):
        relative = f"Раздел {index // 20 + 1}/вложенная папка/Файл {index + 1:03}.bin"
        data = fixture(index, args.salt)
        target = args.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({
            "field": f"f{index:03}", "path": relative, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "gitBlobSha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
        })
    upload_id = args.upload_id or str(uuid.uuid4())
    manifest = {
        "uploadId": upload_id,
        "files": [{key: row[key] for key in ("field", "path", "bytes", "sha256")} for row in files],
    }
    (args.root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    corpus = {
        "schema": 1, "salt": args.salt, "fileCount": 100, "totalBytes": 30000000,
        "files": files, "note": "manifest.json and corpus.json are metadata, excluded from the 100-file upload",
    }
    (args.root / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(corpus, ensure_ascii=False))

if __name__ == "__main__":
    main()
