# opencode-web-deepsearch

DuckDuckGo web search tool for OpenCode with deep search capabilities.

## Features

- **DuckDuckGo Search**: Uses DuckDuckGo for web searching (no API key required)
- **Deep Search**: Iterative search refinement that finds more relevant results
- **Content Extraction**: Extracts clean text content from web pages
- **Source Deduplication**: Automatically deduplicates sources by domain
- **Raw JSON Output**: Returns structured data for AI evaluation

## Installation

### 1. Install Python dependencies

```bash
pip install ddgs beautifulsoup4 requests aiohttp lxml
```

### 2. Add plugin to OpenCode

The npm package name is `opencode-web-deepsearch`.

Add to your `opencode.json`:

```json
{
  "plugin": ["opencode-web-deepsearch"]
}
```

OpenCode will automatically install the plugin from npm using Bun.

### Alternative: MCP Server

You can also use this tool as a standalone MCP server. See [mcp-web-deepsearch](https://github.com/noxgle/mcp-web-deepsearch) for installation and configuration instructions.

## Usage

The tool is available as `web-deepsearch` in OpenCode.

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `query` | string | required | Search query |
| `max_sources` | number | 3 | Maximum sources to extract |
| `deep_search` | boolean | true | Enable iterative search refinement |
| `max_iterations` | number | 5 | Maximum refinement rounds (1–10) |
| `max_content_length` | number | 8000 | Maximum extracted characters per page (500–8000) |
| `timeout` | number | 30 | Per-request timeout in seconds (5–60) |
| `max_total_time` | number | 60 | Maximum total search time in seconds (10–120) |

### Example

```
Use the web-deepsearch tool to search for "TypeScript 5.x features"
```

Or with explicit arguments:

```json
{
  "query": "TypeScript 5.x new features",
  "max_sources": 5,
  "deep_search": true,
  "max_iterations": 5,
  "max_content_length": 8000,
  "timeout": 30,
  "max_total_time": 60
}
```

## Output Format

```json
{
  "query": "TypeScript 5.x new features",
  "sources": [
    {
      "title": "TypeScript 5.0 - Major Changes",
      "url": "https://example.com/typescript-5",
      "snippet": "TypeScript 5.0 brings...",
      "content": "Full extracted content...",
      "domain": "example.com"
    }
  ],
  "iterations_used": 3,
  "source_count": 5,
  "domain_count": 3
}
```

## Response size and compact mode

Each extracted page is capped by the public `max_content_length` argument (default 8,000 characters, range 500–8,000). Independently, the complete indented JSON response is capped at 10,000 UTF-8 bytes to avoid host-side output truncation. This is not a guarantee about any host's own serialization or display limit.

Responses that fit retain the legacy full-response shape. Oversized responses switch to `mode: "compact"` and include `truncated`, `retained_content_count`, `omitted_content_count`, `total_content_length`, and `recovery_hint`. Compact sources retain `title`, `url`, `snippet`, `domain`, and original `content_length`; `content` is empty when omitted and may remain populated for prioritized sources that fit. Fetch important omitted URLs separately with an available page-fetching tool. Reduce `max_sources` if fewer sources are needed, but note that this does not replace the total response limit.

Example compact response:

```json
{
  "query": "example",
  "mode": "compact",
  "truncated": true,
  "retained_content_count": 1,
  "omitted_content_count": 2,
  "total_content_length": 24000,
  "recovery_hint": "Fetch source URLs separately to retrieve omitted page content.",
  "sources": [
    {
      "title": "Example page",
      "url": "https://example.com/article",
      "snippet": "A short search snippet",
      "domain": "example.com",
      "content_length": 8000,
      "content": "... possibly retained full content ..."
    }
  ]
}
```

`content_length` counts extracted Python characters; the response budget measures serialized UTF-8 bytes after JSON escaping.

## Requirements

- Python 3.8+
- `ddgs`
- `beautifulsoup4`
- `requests`
- `aiohttp`
- `lxml`

## Development

```bash
# Install dependencies
pip install ddgs beautifulsoup4 requests aiohttp lxml

# Build TypeScript
npm run build

# Test Python script directly
python3 scripts/WebSearchAgent.py --query "test" --max-sources 1 --deep-search false

# Test with Docker
docker build -f Dockerfile.test -t opencode-plugin-test .
docker run -it opencode-plugin-test bash
```

## Comparison with OpenCode's Built-in Search (Exa)

| Aspect | web-deepsearch | Standard OpenCode (Exa) |
|--------|---------------|-------------------------|
| **API Key** | Not required | Optional (for higher limits) |
| **Cost** | Free | Limited free tier |
| **Code search** | Not included | Via `get_code_context_exa` |
| **Deep search** | Iterative refinement | Not available |
| **Content extraction** | Full page extraction | Via `web_fetch_exa` |
| **Latency** | Slower (DuckDuckGo) | Faster (Exa API) |
| **Reliability** | Depends on DuckDuckGo | More stable (Exa) |

### When web-deepsearch is better:
- You don't have an Exa API key
- You need iterative deep search
- You want a free solution without limits

### When Exa is better:
- You need code search (GitHub code search)
- You need faster results
- You have an API key and need higher limits

---

## License

MIT
