# AGENTS.md

## Project Overview

OpenCode plugin providing DuckDuckGo web search with iterative deep search refinement. npm package: `opencode-web-deepsearch`

## Architecture

- `src/index.ts` - Plugin entry, exports `web-deepsearch` tool
- `scripts/WebSearchAgent.py` - Python search script (bundled with npm)
- **Important**: `import.meta.url` resolves to `dist/index.js`, so path must go up one level to find `scripts/`

## Key Commands

```bash
npm run build      # Compile TypeScript
npm test           # Run e2e tests (vitest)
```

## Testing Plugin Locally

```bash
# 1. Install Python dependencies
pip install ddgs beautifulsoup4 requests aiohttp lxml

# 2. Test Python script directly
python3 scripts/WebSearchAgent.py --query "test" --max-sources 1 --deep-search false

# 3. Test with Docker (OpenCode + plugin)
docker build -f Dockerfile.test -t opencode-plugin-test .
docker run -it opencode-plugin-test bash
```

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
