"""Builds the extension repo (the `repo` branch) from freshly built extensions.

Usage: python publish-repo.py <build-root> <repo-dir> <owner/repo> <signing-key-sha256>

Writes into <repo-dir>:
  apk/<name>.apk, apk/<name>.jar   built extensions
  icon/<package>.png               extension icons
  index.min.json                   legacy index (Tachimanga, older Tachiyomi forks)
  index.pb                         current Mihon index (gzipped protobuf)
  index.json                       human-readable copy of index.pb
  repo.json                        repo metadata
"""

import gzip
import json
import shutil
import sys
from pathlib import Path

import index_pb2
from google.protobuf import json_format

build_root = Path(sys.argv[1]).resolve()
repo_dir = Path(sys.argv[2]).resolve()
repo_name = sys.argv[3]
signing_key = sys.argv[4].lower().replace(":", "")

owner = repo_name.split("/")[0]
raw_base = f"https://raw.githubusercontent.com/{repo_name}/repo"
ICON_FILE = "res/mipmap-xhdpi/ic_launcher.png"

apk_dir = repo_dir / "apk"
icon_dir = repo_dir / "icon"
# Every run rebuilds everything, so the build output is the source of truth.
shutil.rmtree(apk_dir, ignore_errors=True)
shutil.rmtree(icon_dir, ignore_errors=True)
apk_dir.mkdir(parents=True)
icon_dir.mkdir(parents=True)

legacy_index = []
extensions = []

for info_file in sorted(build_root.glob("src/*/*/build/keiyoushi-source-info.json")):
    info = json.loads(info_file.read_text(encoding="utf-8"))
    build_dir = info_file.parent
    module_dir = build_dir.parent
    package_name = info["packageName"]

    apk = next((build_dir / "outputs/apk/release").glob("*.apk"), None)
    if apk is None:
        raise FileNotFoundError(f"{package_name}: no release apk under {build_dir}")
    jar = next((build_dir / "outputs/jar/release").glob("*.jar"), None)

    shutil.copy2(apk, apk_dir / apk.name)
    if jar is not None:
        shutil.copy2(jar, apk_dir / jar.name)

    icon_src = module_dir / ICON_FILE
    if not icon_src.exists():
        icon_src = build_root / "core/src/main" / ICON_FILE
    shutil.copy2(icon_src, icon_dir / f"{package_name}.png")

    langs = {source["lang"] for source in info["sources"]}
    legacy_index.append(
        {
            "name": f"Tachiyomi: {info['name']}",
            "pkg": package_name,
            "apk": apk.name,
            "lang": langs.pop() if len(langs) == 1 else "all",
            "code": info["versionCode"],
            "version": info["versionName"],
            "nsfw": 1 if info["contentWarning"] == index_pb2.CONTENT_WARNING_NSFW else 0,
            "sources": [
                {
                    "name": source["name"],
                    "lang": source["lang"],
                    "id": str(source["id"]),
                    "baseUrl": source["baseUrl"],
                }
                for source in info["sources"]
            ],
        }
    )

    resources = index_pb2.Resources(
        apkUrl=f"{raw_base}/apk/{apk.name}",
        iconUrl=f"{raw_base}/icon/{package_name}.png",
    )
    if jar is not None:
        resources.jarUrl = f"{raw_base}/apk/{jar.name}"

    extensions.append(
        index_pb2.Extension(
            name=info["name"],
            packageName=package_name,
            resources=resources,
            extensionLib=info["extensionLib"],
            versionCode=info["versionCode"],
            versionName=info["versionName"],
            contentWarning=info["contentWarning"],
            sources=[
                index_pb2.Source(
                    id=int(source["id"]),
                    name=source["name"],
                    language=source["lang"],
                    homeUrl=source["baseUrl"],
                    mirrorUrls=source.get("mirrorUrls", []),
                )
                for source in info["sources"]
            ],
        )
    )

if not extensions:
    sys.exit("No built extensions found")

legacy_index.sort(key=lambda ext: ext["pkg"])
extensions.sort(key=lambda ext: ext.packageName)

website = f"https://github.com/{repo_name}"
index = index_pb2.Index(
    name=owner,
    badgeLabel=owner[:4].upper(),
    signingKey=signing_key,
    contact=index_pb2.Contact(website=website),
    extensionList=index_pb2.ExtensionList(extensions=extensions),
)

(repo_dir / "index.min.json").write_text(
    json.dumps(legacy_index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
)
(repo_dir / "index.pb").write_bytes(
    gzip.compress(index.SerializeToString(deterministic=True), mtime=0)
)
(repo_dir / "index.json").write_text(
    json_format.MessageToJson(index, preserving_proto_field_name=True), encoding="utf-8"
)
(repo_dir / "repo.json").write_text(
    json.dumps(
        {
            "index_v2": f"{raw_base}/index.pb",
            "meta": {
                "name": owner,
                "shortName": owner,
                "website": website,
                "signingKeyFingerprint": signing_key,
            },
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print(f"Published {len(extensions)} extensions:")
for ext in extensions:
    print(f"  {ext.name} {ext.versionName} ({ext.packageName})")
