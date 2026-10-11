#!/usr/bin/env python3
"""Build a Mihon v2 extension store (index.pb + repo.json) from a JSON manifest.

Output layout (publish this folder to the `repo` branch):
    repo/
      index.pb        gzip(protobuf Index)  <- the URL users add in Mihon
      index.json      human-readable debug dump (not read by the app)
      repo.json       {"index_v2": ..., "meta": {...}} for tools that discover via repo.json
      apk/ jar/ icon/ (copied in by CI)

Usage:
    python scripts/build_index.py manifest.json repo/ --signing-key <sha256-hex>
    python scripts/build_index.py manifest.json repo/ --apk-dir apk/   # derive + verify key from APKs
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from google.protobuf.json_format import MessageToDict

sys.path.insert(0, str(Path(__file__).parent))
import index_pb2 as pb  # generated from index.proto

WARN = {"SAFE": pb.CONTENT_WARNING_SAFE, "MIXED": pb.CONTENT_WARNING_MIXED, "NSFW": pb.CONTENT_WARNING_NSFW}


def source_id(name: str, lang: str, version_id: int = 1) -> int:
    """Default HttpSource id: first 8 bytes of MD5("name_lowercase/lang/versionId"), sign bit cleared.

    Only valid if the extension does NOT override `id`. If it does, put "id" in the manifest.
    """
    digest = hashlib.md5(f"{name.lower()}/{lang}/{version_id}".encode()).digest()
    return struct.unpack(">q", digest[:8])[0] & 0x7FFFFFFFFFFFFFFF


def apk_cert_sha256(apk: Path) -> str:
    """SHA-256 of the APK signing certificate, via apksigner (Android build-tools)."""
    out = subprocess.run(["apksigner", "verify", "--print-certs", str(apk)],
                         capture_output=True, text=True, check=True).stdout
    m = re.search(r"certificate SHA-256 digest:\s*([0-9a-f]{64})", out)
    if not m:
        raise RuntimeError(f"No SHA-256 cert digest found for {apk}")
    return m.group(1)


def build(manifest: dict, signing_key: str) -> pb.Index:
    base = manifest["baseUrl"].rstrip("/")
    idx = pb.Index(name=manifest["name"], badgeLabel=manifest.get("badgeLabel", ""), signingKey=signing_key)
    idx.contact.website = manifest["website"]
    if manifest.get("discord"):
        idx.contact.discord = manifest["discord"]

    seen_pkgs, seen_ids = set(), {}
    for e in sorted(manifest["extensions"], key=lambda x: x["packageName"]):
        if e["packageName"] in seen_pkgs:
            raise ValueError(f"Duplicate packageName {e['packageName']}")
        seen_pkgs.add(e["packageName"])

        ext = idx.extensionList.extensions.add(
            name=e["name"], packageName=e["packageName"], extensionLib=e["extensionLib"],
            versionCode=int(e["versionCode"]), versionName=e["versionName"],
            contentWarning=WARN[e["contentWarning"].upper()],
        )
        ext.resources.apkUrl = f"{base}/apk/{e['apk']}"
        ext.resources.iconUrl = f"{base}/{e['icon']}"
        if e.get("jar"):
            ext.resources.jarUrl = f"{base}/jar/{e['jar']}"

        for s in e["sources"]:
            sid = int(s["id"]) if "id" in s else source_id(s["name"], s["language"], s.get("versionId", 1))
            if sid in seen_ids:
                raise ValueError(f"Source id collision {sid}: {seen_ids[sid]} vs {e['packageName']}")
            seen_ids[sid] = e["packageName"]
            src = ext.sources.add(id=sid, name=s["name"], language=s["language"], homeUrl=s["homeUrl"])
            src.mirrorUrls.extend(s.get("mirrorUrls", []))
            if s.get("message"):
                src.message = s["message"]
    return idx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("out", type=Path)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--signing-key", help="SHA-256 hex of the signing cert (lowercase, no colons)")
    g.add_argument("--apk-dir", type=Path, help="Derive key from APKs and verify they all match")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())

    if args.apk_dir:
        fps = {apk.name: apk_cert_sha256(apk) for apk in sorted(args.apk_dir.glob("*.apk"))}
        if len(set(fps.values())) != 1:
            sys.exit(f"APKs signed with different keys: {json.dumps(fps, indent=2)}")
        signing_key = next(iter(fps.values()))
        missing = {e["apk"] for e in manifest["extensions"]} - set(fps)
        if missing:
            sys.exit(f"Manifest references APKs not in {args.apk_dir}: {sorted(missing)}")
    else:
        signing_key = args.signing_key.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", signing_key):
        sys.exit("Signing key must be a 64-char SHA-256 hex string")

    idx = build(manifest, signing_key)
    args.out.mkdir(parents=True, exist_ok=True)

    # Keiyoushi ships index.pb gzip-compressed (mtime=0 keeps the bytes reproducible -> clean git diffs).
    (args.out / "index.pb").write_bytes(gzip.compress(idx.SerializeToString(), compresslevel=9, mtime=0))
    (args.out / "index.json").write_text(json.dumps(MessageToDict(idx), indent=2, ensure_ascii=False))

    index_url = f"{manifest['baseUrl'].rstrip('/')}/index.pb"
    (args.out / "repo.json").write_text(json.dumps({
        "index_v2": index_url,
        "meta": {"name": manifest["name"], "website": manifest["website"], "signingKeyFingerprint": signing_key},
    }, indent=2))

    if args.apk_dir:
        shutil.copytree(args.apk_dir, args.out / "apk", dirs_exist_ok=True)

    n_src = sum(len(e.sources) for e in idx.extensionList.extensions)
    print(f"Wrote {len(idx.extensionList.extensions)} extensions / {n_src} sources -> {index_url}")


if __name__ == "__main__":
    main()
