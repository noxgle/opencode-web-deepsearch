# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.13] - 2026-10-02

### Added
- Response size budget enforcement to prevent oversized JSON output
- Compact mode for responses exceeding the 10,000-byte budget
- Truncation metadata (`mode`, `truncated`, `retained_content_count`, `omitted_content_count`, `total_content_length`, `recovery_hint`)
- Public tuning parameters: `max_iterations`, `max_content_length`, `timeout`, `max_total_time`
- Docker test environment (`Dockerfile.test`)

### Changed
- Default `max_sources` reduced from 5 to 3
- Improved script path detection using `import.meta.url` for Bun compatibility
- Enhanced SSRF protection with IP validation and redirect controls

### Fixed
- Script path resolution when installed via Bun in OpenCode's cache directory
- Removed peer dependency on `opencode` (not available on public npm)

## [1.0.11] - 2026-09-XX

### Added
- MCP server alternative installation documentation

## [1.0.10] - 2026-09-XX

### Changed
- Optimized speed, package size, and security
- Improved WebSearchAgent reliability and diagnostics

## [1.0.9] - 2026-09-XX

### Fixed
- Script path resolution from package root

## [1.0.8] - 2026-09-XX

### Fixed
- Removed opencode peer dependency

## [1.0.7] - 2026-09-XX

### Fixed
- ESM path detection for script location

## [1.0.6] - 2026-09-XX

### Added
- E2E tests via OpenCode plugin context

---

[Unreleased]: https://github.com/noxgle/opencode-web-deepsearch/compare/v1.0.13...HEAD
[1.0.13]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.13
[1.0.11]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.11
[1.0.10]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.10
[1.0.9]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.9
[1.0.8]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.8
[1.0.7]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.7
[1.0.6]: https://github.com/noxgle/opencode-web-deepsearch/releases/tag/v1.0.6
