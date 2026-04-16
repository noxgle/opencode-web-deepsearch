# AGENTS.md

## Project Overview

This is an OpenCode plugin that provides a DuckDuckGo web search tool with deep search capabilities. It's an npm package (`opencode-web-deepsearch`) that registers a `web-deepsearch` tool.

## Key Commands

```bash
npm run build      # Compile TypeScript
npm run test       # Run e2e tests (requires Python deps)
```

## Requirements

- **Python 3.8+** with: `ddgs`, `beautifulsoup4`, `requests`, `aiohttp`, `lxml`
- **Node.js 18+**
- **Bun** (for running the tool in OpenCode)

## How It Works

1. OpenCode loads the plugin via npm
2. The plugin registers the `web-deepsearch` tool
3. On execution, it runs `scripts/WebSearchAgent.py` using Bun's backtick syntax
4. The Python script searches DuckDuckGo and extracts page content

## Known Issues

- The Python `ddgs` library occasionally returns empty results for certain queries (rate limiting)
- Vitest e2e tests don't run properly in this environment - manual testing with `python3 scripts/WebSearchAgent.py` is more reliable