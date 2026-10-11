# Scanlations

Personal [Tachimanga](https://tachimanga.app/) / [Mihon](https://mihon.app/) extension repository.

| Extension | Site |
|---|---|
| Comix | https://comix.to |
| Asura Scans | https://asurascans.com |

## Add to Tachimanga

Browse → Extensions → settings → Extension Repos → **+**, then paste:

```
https://raw.githubusercontent.com/Hwangbot/Scanlations/repo/index.min.json
```

Mihon users can use `https://raw.githubusercontent.com/Hwangbot/Scanlations/repo/index.pb` instead.

## How it works

- `main` holds the Kotlin source. Each extension lives in `src/<lang>/<name>/`.
- Every push to `main` runs `.github/workflows/build.yml`, which builds and signs every extension and publishes `apk/`, `icon/`, `index.min.json`, `index.pb` and `repo.json` to the `repo` branch.
- Apps only offer an update when `versionCode` in an extension's `build.gradle.kts` goes up.

## One-time setup

Add these repository secrets (Settings → Secrets and variables → Actions): `SIGNING_KEY` (base64 of the keystore), `ALIAS`, `KEY_STORE_PASSWORD`, `KEY_PASSWORD`. Never change the signing key once extensions are installed.

## Credits

Build system, core library and extension source are from [keiyoushi/extensions-source](https://github.com/keiyoushi/extensions-source), licensed under Apache 2.0 (see `LICENSE`).
