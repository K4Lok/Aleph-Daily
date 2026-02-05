# Daily News Collections

Automated daily news aggregation using CCS (with GLM model) and the `news-aggregator-skill`. Collects top news, sends to Telegram, and archives to GitHub.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Run the aggregator
python scripts/daily_news.py
```

## Configuration

### Prerequisites

Install CCS (Claude Code Switch) for running with GLM LLM:

```bash
npm install -g @kaitranntt/ccs
```

Then configure your GLM API key:

```bash
ccs config
```

This opens the dashboard where you can configure your GLM profile.

### Environment Variables (`.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes (for TG) |
| `TELEGRAM_CHAT_ID` | Your chat/channel ID | Yes (for TG) |
| `GITHUB_TOKEN` | Personal Access Token with `repo` scope | Yes (for GH) |
| `GITHUB_REPO` | Repository in `username/repo` format | Yes (for GH) |
| `GITHUB_BRANCH` | Branch to push to (default: `main`) | No |
| `CLAUDE_MODEL` | Model to use: `sonnet`, `opus`, `haiku` | No |
| `CCS_PROFILE` | CCS profile to use (default: `glm`) | No |
| `NEWS_PRESET` | Default preset (see below) | No |
| `GIT_USER_NAME` | Git commit author name | No |
| `GIT_USER_EMAIL` | Git commit author email | No |

### News Presets

Available presets in `config/presets.json`:

| Preset | Description | Sources |
|--------|-------------|---------|
| `ai_tech` | AI & Tech news | Hacker News, GitHub, Product Hunt |
| `china_tech` | Chinese tech ecosystem | 36Kr, Tencent, Weibo |
| `global_scan` | Full global scan | All sources |
| `finance` | Financial markets | WallStreetCN |
| `dev_community` | Developer communities | GitHub, HN, V2EX |

## Usage

```bash
# Use defaults from .env
python scripts/daily_news.py

# Use specific preset
python scripts/daily_news.py --preset ai_tech

# Use different model
python scripts/daily_news.py --model opus

# Dry run (no TG/GitHub)
python scripts/daily_news.py --dry-run

# Skip specific outputs
python scripts/daily_news.py --skip-telegram
python scripts/daily_news.py --skip-github

# List available presets
python scripts/daily_news.py --list-presets

# Custom timeout (for slow networks)
python scripts/daily_news.py --timeout 600
```

## Scheduling (Cron)

Add to crontab for daily automation:

```bash
# Run daily at 9:00 AM
0 9 * * * cd /path/to/daily-news-collections && /usr/bin/python3 scripts/daily_news.py >> /var/log/daily-news.log 2>&1
```

## Project Structure

```
daily-news-collections/
├── scripts/
│   ├── daily_news.py       # Main orchestrator
│   ├── skill_manager.py    # Skill installation
│   ├── claude_runner.py    # CCS CLI wrapper
│   ├── telegram_sender.py  # Telegram integration
│   └── github_pusher.py    # Git operations
├── config/
│   ├── presets.json        # News presets
│   └── settings.py         # Settings loader
├── news/                   # Generated markdown files
├── .env.example            # Environment template
└── requirements.txt        # Dependencies
```

## Error Handling

- **News collection fails**: Script exits immediately
- **Telegram fails**: Logs error, continues to GitHub
- **GitHub fails**: Logs error, continues (news already saved locally)

This ensures you always have the local markdown file even if external services fail.

## License

MIT
