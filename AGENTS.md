# AGENTS.md

## Project Overview

OpenCode plugin providing DuckDuckGo web search with iterative deep search refinement. npm package: `opencode-web-deepsearch`

## Architecture

- `src/index.ts` - Plugin entry, exports `web-deepsearch` tool
- `scripts/WebSearchAgent.py` - Python search script (bundled with npm); owns search/extraction logic, CLI validation, and serialized-output size enforcement
- `e2e/test_response_budget.py` - deterministic Python unit/CLI regression tests for response limits and public CLI argument validation
- `e2e/test_plugin.test.ts` - Vitest integration tests; filename must match `vitest.config.ts` include pattern (`e2e/**/*.test.ts`)
- **Important**: `import.meta.url` resolves to `dist/index.js`, so path must go up one level to find `scripts/`

## Key Commands

```bash
npm run build      # Compile TypeScript
npm test           # Run Vitest tests (requires OpenCode for the plugin-load test)
python3 -m unittest e2e/test_response_budget.py  # Run deterministic Python tests without network
```

## Testing Plugin Locally

```bash
# 1. Install Python dependencies
pip install ddgs beautifulsoup4 requests aiohttp lxml

# 2. Test Python script directly
python3 scripts/WebSearchAgent.py --query "test" --max-sources 1 --deep-search false

# Optional tuning parameters (bounded by CLI validation)
python3 scripts/WebSearchAgent.py --query "test" --max-sources 3 --max-iterations 3 --max-content-length 4000 --timeout 20 --max-total-time 45

# 3. Test with Docker (OpenCode + plugin)
docker build -f Dockerfile.test -t opencode-plugin-test .
docker run -it opencode-plugin-test bash
```

## Public Tool Parameters

The OpenCode tool exposes `query`, `max_sources`, `deep_search`, `max_iterations`, `max_content_length`, `timeout`, and `max_total_time`. Keep TypeScript schema bounds/defaults in `src/index.ts` aligned with CLI validation/defaults in `scripts/WebSearchAgent.py` and the argument documentation in `README.md`.

Current bounds: `max_sources` 1–50, `max_iterations` 1–10, `max_content_length` 500–8000 characters per page, `timeout` 5–60 seconds per request, and `max_total_time` 10–120 seconds. The total serialized response budget (`response_budget_bytes`, currently 10,000 UTF-8 bytes) is an internal safety setting, not a public tool argument. Preserve the same JSON serialization settings when measuring and printing responses.

## Requirements

- **Python 3.8+**: `ddgs`, `beautifulsoup4`, `requests`, `aiohttp`, `lxml`
- **Bun** - OpenCode uses Bun to install plugins, not npm
- **Node.js 18+** - for building

## Critical Notes

- **No peer dependency on `opencode`** - it doesn't exist on public npm
- OpenCode installs plugins via `bun add`, caches in `~/.cache/opencode/packages/`
- Plugin must work when installed by Bun in OpenCode's cache directory

## Publishing

```bash
npm run build && npm version patch && npm publish
git push
```
