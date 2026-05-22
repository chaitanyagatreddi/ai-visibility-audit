---
title: AI Visibility Audit
emoji: 🔍
colorFrom: red
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Batman — AI Visibility Audit

Scans any brand's visibility across AI search platforms (Google AI Overviews, Perplexity AI, ChatGPT) and generates actionable GEO recommendations to improve AI citation rates.

**Live demo:** [ai-visibility-audit-chaitanya67.replit.app](https://ai-visibility-audit-chaitanya67.replit.app)

## What it does

Enter any website URL or brand name. The agent spins up parallel cloud browsers, searches AI platforms with category-specific queries, extracts brand mentions, and produces a visibility audit with competitor analysis and optimization recommendations.

### How it works

1. **Input** — Brand name or website URL (auto-detects brand, industry, and competitors)
2. **Query Generation** — Creates industry-specific search queries (SaaS, D2C Fashion, Health/Wellness, Fintech, Edtech)
3. **Live Scanning** — Browserbase cloud browsers navigate Google AI Overviews and Perplexity AI, extract AI-generated answers
4. **AI Analysis** — OpenAI gpt-4o-mini analyzes extracted text for brand mentions, positioning, and competitor presence
5. **Scoring** — Visibility score 0-100 based on mention rate (40pts), position quality (20pts), platform coverage (20pts), query coverage (20pts)
6. **Report** — Competitor leaderboard, gap analysis, GEO recommendations, cost of inaction estimate

### Agent Swarm UI

Live SSE-streaming interface showing parallel agents working in real-time:
- **Orchestrator** — Coordinates the scan workflow
- **Browser Agent** — Manages Browserbase cloud browser sessions
- **Google AIO Scanner** — Extracts AI Overview answers from Google
- **Perplexity Scanner** — Extracts AI answers from Perplexity
- **Analysis Engine** — Processes mentions and generates scores

## GEO Recommendations (Princeton KDD 2024)

Based on the Generative Engine Optimization research paper:

| Strategy | Expected Lift | Implementation |
|---|---|---|
| Quotation Addition | +41% visibility | Add expert quotes and testimonials to key pages |
| Statistics Addition | +32% visibility | Include specific metrics: user counts, growth rates, benchmarks |
| Cite Sources | +30% visibility | Reference industry reports, research papers, government data |
| Table Formatting | 2.5x citation rate | Convert lists to HTML comparison tables |
| Structured Data | Improves AI parsing | Add Schema.org markup (FAQ, HowTo, Product) |

## Architecture

```
app.py (Flask + SSE)
  |
  ├── /api/audit/stream  → SSE endpoint, streams agent status + results
  ├── agent.py            → Browserbase + OpenAI orchestration
  │     ├── create_session()     → Browserbase cloud browser
  │     ├── scan_google_aio()    → Google AI Overview extraction
  │     ├── scan_perplexity()    → Perplexity AI extraction
  │     └── analyze_mentions()   → OpenAI brand mention analysis
  |
  ├── scanner.py          → Query generation, brand detection, scoring
  │     ├── generate_queries()          → Industry-specific search queries
  │     ├── detect_brand_mentions()     → Brand mention detection in AI text
  │     ├── calculate_visibility_score()→ 0-100 scoring algorithm
  │     ├── generate_gap_analysis()     → Identify invisible queries/platforms
  │     └── generate_recommendations()  → GEO strategy recommendations
  |
  └── run_audit.py        → CLI runner with demo data
```

## Tech Stack

- **Browser Automation:** Browserbase SDK + Playwright (headless cloud browsers)
- **AI Analysis:** OpenAI gpt-4o-mini
- **Backend:** Flask + Gunicorn
- **Streaming:** Server-Sent Events (SSE) for live agent status
- **Deployment:** Docker (HuggingFace Spaces, Replit, Render, Railway)

## Supported Industries

| Industry | Example Brands | Query Types |
|---|---|---|
| SaaS | Freshworks, Zoho, Razorpay, Postman | Best tools, top companies, recommended software |
| D2C Fashion | Snitch, BlissClub, Bewakoof | Best brands, trending, affordable |
| Health/Wellness | Himalaya, Kapiva, Oziva | Best supplements, organic products |
| Fintech | Razorpay, PhonePe, Zerodha, CRED | Best startups, payment companies |
| Edtech | Unacademy, Vedantu, Scaler | Best startups, online platforms |

## Live Scan Results

| Brand | Score | Key Finding |
|---|---|---|
| Freshworks | 46.7/100 | Invisible in 2/3 generic SaaS queries on Google AIO |
| Exotel | 0.0/100 | Completely invisible across all AI platforms |

## Deploy

### Environment Variables

| Variable | Description |
|---|---|
| `BROWSERBASE_API_KEY` | From [browserbase.com](https://browserbase.com) |
| `BROWSERBASE_PROJECT_ID` | Your Browserbase project ID |
| `OPENAI_API_KEY` | From [platform.openai.com](https://platform.openai.com) |

### Run Locally

```bash
git clone https://github.com/chaitanyagatreddi/ai-visibility-audit.git
cd ai-visibility-audit
pip install -r requirements.txt
playwright install chromium

export BROWSERBASE_API_KEY=...
export BROWSERBASE_PROJECT_ID=...
export OPENAI_API_KEY=...

python3 app.py
# Open http://localhost:5001
```

### CLI

```bash
# Scan any brand
python3 agent.py --brand Freshworks --industry saas --city bangalore

# Scan any website URL (auto-detects brand + industry)
python3 agent.py --url https://exotel.com --city bangalore

# Limit queries
python3 agent.py --brand Kapiva --industry health_wellness --queries 3
```

### One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/chaitanyagatreddi/ai-visibility-audit)

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/new?repo=https://github.com/chaitanyagatreddi/ai-visibility-audit)

## Built With

- [Browserbase](https://browserbase.com) — Headless cloud browser infrastructure
- [OpenAI](https://openai.com) — AI analysis (gpt-4o-mini)
- [Playwright](https://playwright.dev) — Browser automation
- [Flask](https://flask.palletsprojects.com) — Web framework

---

*Batman — AI Visibility Audit*
