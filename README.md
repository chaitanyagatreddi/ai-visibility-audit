# AI Visibility Audit Agent

Real agent that scans brand visibility across AI search platforms using **Browserbase** + **Claude** + **GEO recommendations**.

Enter any website URL or brand name. Get a live visibility score, competitor leaderboard, gap analysis, and actionable GEO recommendations.

## What it does

1. **Browserbase** spins up a cloud browser
2. Navigates **Google AI Overviews** and **Perplexity AI** with generated queries
3. **Claude** analyzes extracted text for brand mentions and positioning
4. Scores visibility 0-100, identifies gaps, generates recommendations from the Princeton GEO paper

## Deploy

### One-click deploy to Render (free tier)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/chaitanyagatreddi/ai-visibility-audit)

### One-click deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/new?repo=https://github.com/chaitanyagatreddi/ai-visibility-audit)

### Environment variables needed

| Variable | Description |
|---|---|
| `BROWSERBASE_API_KEY` | From [browserbase.com](https://browserbase.com) |
| `BROWSERBASE_PROJECT_ID` | Your Browserbase project ID |
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |

### Run locally

```bash
git clone https://github.com/chaitanyagatreddi/ai-visibility-audit.git
cd ai-visibility-audit
pip install -r requirements.txt
playwright install chromium

export BROWSERBASE_API_KEY=...
export BROWSERBASE_PROJECT_ID=...
export ANTHROPIC_API_KEY=...

python3 app.py
# Open http://localhost:5001
```

### CLI usage

```bash
# Scan any brand
python3 agent.py --brand Freshworks --industry saas --city bangalore

# Scan any website URL (auto-detects brand + industry)
python3 agent.py --url https://exotel.com --city bangalore

# Limit queries
python3 agent.py --brand Kapiva --industry health_wellness --queries 3
```

## Live results

| Brand | Score | Gaps |
|---|---|---|
| Freshworks | 46.7/100 | Invisible in 2/3 generic SaaS queries |
| Exotel | 0.0/100 | Completely invisible across all queries |

## Architecture

```
agent.py          -- Main agent: Browserbase + Claude orchestration
scanner.py        -- Query generation, brand detection, scoring, GEO recs
app.py            -- Flask web UI
run_audit.py      -- CLI runner with demo data
```

## GEO Recommendations (Princeton KDD 2024)

- Quotation addition: **+41% visibility**
- Statistics addition: **+32% visibility**
- Cite sources: **+30% visibility**
- Table formatting: **2.5x citation rate**

## Built with

- [Browserbase](https://browserbase.com) -- headless cloud browser
- [Anthropic Claude](https://anthropic.com) -- AI analysis
- [Playwright](https://playwright.dev) -- browser automation
- [Flask](https://flask.palletsprojects.com) -- web framework

---

*Crazyheads 2.0 x Writesonic GEO Platform*
