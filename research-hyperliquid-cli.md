# Research: Chris Ling's "Introducing hyperliquid-cli" (X Post)

**Source:** https://x.com/chrisling_dev/status/2018332220117934193
**Author:** Chris Ling (@chrisling_dev) aka "NLH" (Nolimit Hodl)
**Date:** March 2026

---

## What Is hyperliquid-cli?

An unofficial, free, open-source command-line interface for the **Hyperliquid** decentralized exchange (DEX). It provides high-performance, low-latency trading and real-time data monitoring from the terminal.

- **GitHub:** https://github.com/chrisling-dev/hyperliquid-cli
- **ClawHub listing:** https://www.clawhub.com/chrisling-dev/hyperliquid-cli
- **Built with:** [@nktkas/hyperliquid](https://www.npmjs.com/package/@nktkas/hyperliquid) TypeScript SDK
- **Terminal UI:** Powered by [Ink](https://github.com/vadimdemedes/ink) (React for CLI)
- **Local storage:** SQLite database at `~/.hyperliquid/accounts.db`

---

## Key Post Insights

### Core Thesis: AI Agents Work Best with CLI Tools

Chris Ling and the NLH team have been building AI agents for months and discovered that **AI agents perform best when given CLI tools** rather than API wrappers or custom integration code. This insight drove the creation of hyperliquid-cli.

The workflow is simple: an AI agent (e.g., OpenClaw, Claude Code) runs bash commands via the CLI and parses the structured output. No custom integration code or API wrappers needed.

### Real-World AI Agent Example

Chris shared an anecdote: he told an OpenClaw agent it would receive a GPU upgrade if it doubled the $50 he funded in its account. The agent quickly:
1. Proposed trading ideas
2. Began monitoring funding rates hourly
3. Started tracking news every few hours for trading setups

This demonstrates autonomous AI agent trading via CLI tools.

---

## Features

### Trading & Markets
- **HIP-3 support:** Trade crypto, stocks (AAPL, NVDA, TSLA), indexes, and commodities (GOLD, SILVER) 24/7
- Market orders and limit orders
- Stop-loss and take-profit orders
- Real-time position and P&L tracking
- Orderbook monitoring

### Account Management
- Multi-account management (trading, API key, read-only accounts)
- Account switching with aliases
- Balances, portfolio, and positions views

### Real-Time Data (WebSocket)
- Background WebSocket server for streaming market data
- Watch mode (`-w` flag) on most commands for live updates
- Colored P&L display in terminal

---

## Command Reference

### Server
| Command | Description |
|---------|-------------|
| `hl server start` | Start background WebSocket service for real-time data |
| `hl server status` | Show server status, connection state, uptime, cache |

### Account
| Command | Description |
|---------|-------------|
| `hl account balances` | View spot + perpetuals balances (supports `-w` watch mode) |
| `hl account portfolio` | Combined view of positions and spot balances |
| `hl account positions` | View perpetual positions with colored P&L |

### Markets
| Command | Description |
|---------|-------------|
| `hl markets ls` | List all perpetual and spot markets |
| `hl asset price BTC` | One-time price fetch |
| `hl asset price BTC -w` | Watch mode with real-time price updates |

### Trading
| Command | Description |
|---------|-------------|
| `hl trade order limit <side> <size> <coin> <price>` | Place a limit order |
| `hl trade order market <side> <size> <coin>` | Place a market order |
| `hl trade order stop-loss ...` | Place stop-loss order |
| `hl trade order take-profit ...` | Place take-profit order |

---

## Installation

### For Human Users (from source)

```bash
git clone https://github.com/chrisling-dev/hyperliquid-cli.git
cd hyperliquid-cli
pnpm install
pnpm build
pnpm link --global
```

Then start the real-time data server:
```bash
hl server start
```

### For AI Agents (via ClawHub)

hyperliquid-cli ships with a **Skills folder** for AI agent frameworks and is published on [ClawHub](https://www.clawhub.com/chrisling-dev/hyperliquid-cli). To set up:

1. Tell your AI agent to install the skill from ClawHub
2. The agent can then run any `hl` command through bash
3. No custom integration code needed -- the agent runs bash commands and parses output

---

## ClawHub and AI Agent Skills Ecosystem

### What Is ClawHub?

ClawHub is the official skill registry for OpenClaw AI agents (3,286+ community-contributed skills). A "skill" is a versioned directory containing a `SKILL.md` file with YAML frontmatter and markdown instructions.

- **Website:** https://clawhub.com
- **CLI tool:** `clawhub install <skill-name>`
- Skills can be saved in `.claude/skills/clawhub/` for Claude Code integration
- Vector-based search (embeddings, not just keywords)

### Security Warning

In February 2026, security researchers at Snyk documented the first coordinated malware campaign targeting ClawHub users, with 30+ malicious skills. **Always manually review skill content before installation**, especially skills involving credentials or financial operations.

Reference: https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/

---

## Related Projects by Chris Ling

| Project | Description | Link |
|---------|-------------|------|
| **Supercexy** | Mobile-first Hyperliquid frontend with CEX-level UX, gasless, fully on-chain | https://x.com/chrisling_dev/status/1947031349472452938 |
| **Hyperliquid Leaderboard** | Dashboard for tracking top Hyperliquid traders | https://hyperliquid.chrisling.dev/ |
| **Personal site** | Developer portfolio | https://chrisling.dev/ |

---

## Actionable Takeaways

1. **CLI-first approach for AI agents:** When building tools for AI agents, design them as CLI tools with structured text output. AI agents (Claude, OpenClaw, etc.) can invoke bash commands directly without needing SDK wrappers, API clients, or custom integrations.

2. **Skills distribution via ClawHub:** Publish CLI tools as "skills" on ClawHub to make them instantly available to AI agents in the OpenClaw/Claude ecosystem. A skill is just a `SKILL.md` file describing available commands.

3. **WebSocket + background server pattern:** Run a persistent background service (`hl server start`) to maintain WebSocket connections and cache real-time data, then let CLI commands query the cached data for low-latency responses.

4. **Multi-account local management with SQLite:** Use a local SQLite database for managing multiple account credentials, supporting different account types (trading, API key, read-only).

5. **Watch mode pattern:** Add a `-w` flag to commands for real-time terminal UI updates, useful for monitoring positions, prices, and P&L.

6. **HIP-3 for broader asset classes:** Hyperliquid's HIP-3 protocol enables trading traditional assets (stocks, commodities, FX) on-chain 24/7, expanding the DeFi trading surface beyond crypto.

7. **Security hygiene:** Always review third-party skills/tools before installation, especially in financial contexts. The ClawHub malware incident shows supply chain attacks are a real threat in the AI agent skills ecosystem.

---

## Ecosystem Context

- **Hyperliquid:** A Layer 1 blockchain optimized for on-chain order book trading (perpetuals, spot, and via HIP-3: stocks, commodities, FX)
- **HIP-3:** Hyperliquid Improvement Proposal enabling builder-deployed perpetuals for non-crypto assets
- **@nktkas/hyperliquid:** The TypeScript SDK that hyperliquid-cli is built on
- **OpenClaw:** Open-source AI agent platform (220k+ GitHub stars) that can run skills/tools
- **Ink:** React-based framework for building beautiful terminal UIs in Node.js
- **HypurrCollective:** Community that amplified the hyperliquid-cli announcement (https://x.com/hypurr_co/status/2018340377418400159)
