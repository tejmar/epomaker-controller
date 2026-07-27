# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.9] - 2026-07-28

### Added
- Built-in keyboard model registry and CLI: `models list`, `models show`, `models set`
- Model `CAPABILITIES` in main config (`per_key_rgb`, `rt100_screen`, `dynatab_screen`) with DynaTab migration
- Typed exception hierarchy (`DeviceNotOpenError`, `ProtocolError`, `ConfigError`, …)
- `EpomakerController` context manager (`with` closes the HID device)
- `send_dynatab_frames()` for direct pixel upload (no temp GIF)
- Protocol timing constants (`ERASE_DELAY_S`, `PACKET_DELAY_S`, `SCREEN_FLASH_WAIT_S`)
- Pytest suite and GitHub Actions CI (Python 3.10–3.12)
- Optional dev extra: `pip install -e ".[dev]"`
- Contributor Covenant Code of Conduct

### Changed
- All key-RGB paths use hardware-safe erase (250 ms) and packet (10 ms) pacing
- CLI device open/close centralized via `open_controller` / `_run_with_device`
- Signal handlers are opt-in (`install_signal_handlers=True` for the daemon)
- Screen designer title/neutral branding; upload uses capability checks
- README/CONTRIBUTING: Python 3.10+, real repo URL, models docs, broader usage
- GUI fonts resolve best available sans-serif at runtime

### Fixed
- Right-side keys no longer risk silent failure from unpaced CLI RGB sends
- Config rejects unknown keys with clear errors; missing keys raise `ConfigError`

## [0.0.8] - 2026-07-27

### Added
- Initial public release: CLI + key backlight GUI + DynaTab screen designer
- Support packaging for RT100, DynaTab 75X, EP64, Gamakay TK68-HE

[0.0.9]: https://github.com/tejmar/epomaker-controller/compare/v0.0.8...v0.0.9
[0.0.8]: https://github.com/tejmar/epomaker-controller/releases/tag/v0.0.8
