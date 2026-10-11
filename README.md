# My Mihon Extension Store

Template that publishes a Mihon v2 extension store (`index.pb`) to the `repo` branch.

1. Put your Keiyoushi-style Gradle extension project in this repo (or drop prebuilt signed APKs in `apk/` and remove the Gradle step).
2. Add secrets: `SIGNING_KEY` (base64 .jks), `ALIAS`, `KEY_STORE_PASSWORD`, `KEY_PASSWORD`.
3. Edit `manifest.json` (one entry per APK, bump `versionCode` on every release).
4. Push to `main`. Users add: `https://github.com/<you>/<repo>/raw/repo/index.pb`

Local test:
    pip install grpcio-tools protobuf
    python -m grpc_tools.protoc -I scripts --python_out=scripts scripts/index.proto
    python scripts/build_index.py manifest.json out --signing-key <sha256>
