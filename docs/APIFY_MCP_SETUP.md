# Apify MCP Server — Setup for Claude Code

This connects Claude Code to Apify so it can discover and run the LinkedIn Jobs Scraper
(and other Actors) directly. It uses Apify's **hosted remote MCP server** at
`https://mcp.apify.com` — no local Node process to babysit.

## 1. Token

Your Apify API token lives in `My Context/Job Applications/pipeline_config.env` as
`APIFY_TOKEN`. (Rotate it — it was shared in chat. Get a fresh one at
https://console.apify.com/account#/integrations .)

## 2. Make the token available to Claude Code

The project `.mcp.json` references the token as `${APIFY_TOKEN}` rather than hardcoding it,
so the secret never lives in a committed file. Export it before launching Claude Code:

```bash
# macOS / Linux
export APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Windows PowerShell
$env:APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Or add it to your shell profile so it's always present.

## 3. The config

`job-pipeline/.mcp.json` (already created):

```json
{
  "mcpServers": {
    "apify": {
      "type": "http",
      "url": "https://mcp.apify.com?tools=actors,docs",
      "headers": { "Authorization": "Bearer ${APIFY_TOKEN}" }
    }
  }
}
```

Claude Code auto-detects `.mcp.json` at the project root and will prompt you to approve
the server the first time you open the project. Approve it.

`?tools=actors,docs` loads the Actor-discovery + run tools (`search-actors`,
`fetch-actor-details`, `call-actor`, `get-actor-output`) plus docs search. That's all the
pipeline needs. Add specific Actors to the URL to expose them as dedicated tools, e.g.
`?tools=actors,docs,apify/rag-web-browser`.

## 4. Verify

In Claude Code: `/mcp` should list **apify** as connected. Then ask it to
`search-actors` for "linkedin jobs" to confirm tool calls work.

## Alternatives

- **OAuth instead of token:** drop the `headers` block and use just
  `"url": "https://mcp.apify.com"`. Claude Code opens a browser to authorize on first use.
- **Local stdio** (if you can't use a remote server):
  ```json
  {
    "mcpServers": {
      "apify": {
        "command": "npx",
        "args": ["-y", "@apify/actors-mcp-server@latest"],
        "env": { "APIFY_TOKEN": "${APIFY_TOKEN}" }
      }
    }
  }
  ```
  Requires Node 18+.

## Notes

- Rate limit: 30 req/s per user.
- Free tier: $5/month in credits (~8,700 LinkedIn jobs/month at the quoted rate).
- This is a **Claude Code** config. Cowork (this environment) reaches Apify through its own
  connectors / the REST API, not this file.
