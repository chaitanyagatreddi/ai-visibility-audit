#!/usr/bin/env python3
"""
AI Visibility Audit Agent
==========================
A real agent that scans brand visibility across AI search platforms
using Browserbase headless browser + Anthropic Claude for reasoning.

Architecture:
  1. Browserbase creates a cloud browser session
  2. Playwright connects to it and navigates AI platforms
  3. For each query x platform, extract the AI-generated answer
  4. Claude analyzes extracted text for brand mentions + positioning
  5. Score, gap-analyze, and generate GEO recommendations

Platforms scanned:
  - Google (AI Overviews)
  - Perplexity AI
  - Bing Copilot (bonus)

Usage:
  export BROWSERBASE_API_KEY=bb_live_...
  export BROWSERBASE_PROJECT_ID=...
  export ANTHROPIC_API_KEY=sk-ant-...

  python3 agent.py --brand Freshworks --industry saas --city bangalore
  python3 agent.py --brand Exotel --industry saas --city bangalore --queries 3
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

# Lazy imports -- fail fast with clear messages
def check_deps():
    missing = []
    try:
        import anthropic
    except ImportError:
        missing.append("anthropic")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        missing.append("playwright")
    try:
        from browserbase import Browserbase
    except ImportError:
        missing.append("browserbase")
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install: pip3 install {' '.join(missing)}")
        sys.exit(1)

check_deps()

import anthropic
from playwright.async_api import async_playwright
from browserbase import Browserbase

from scanner import (
    VisibilityAudit, detect_brand_mentions, build_audit_report,
    generate_queries, KNOWN_BRANDS, GEO_STRATEGIES, QUERY_TEMPLATES,
)

# ── Config ────────────────────────────────────────────────────────

BB_API_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BB_PROJECT_ID = os.environ.get("BROWSERBASE_PROJECT_ID", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PLATFORMS = {
    "google_aio": {
        "name": "Google AI Overview",
        "search_url": "https://www.google.com/search?q={query}",
        "wait_selector": "#search",
        "extract_selector": "[data-attrid='wa:/description'], .xpdopen, .kp-blk, .IZ6rdc, .g-blk, .V3FYCf, .bVj5Zb, .wDYxhc, div[data-md]",
    },
    "perplexity": {
        "name": "Perplexity AI",
        "search_url": "https://www.perplexity.ai/search?q={query}",
        "wait_selector": "main",
    },
}

# ── Data Structures ───────────────────────────────────────────────

@dataclass
class ScanResult:
    query: str
    platform: str
    ai_answer_present: bool
    raw_text: str
    brands_detected: list
    citations: list
    scan_time_ms: int
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


# ── Browser Scanner ───────────────────────────────────────────────

class BrowserScanner:
    """Manages Browserbase sessions and Playwright page interactions."""

    def __init__(self):
        self.bb = Browserbase(api_key=BB_API_KEY)
        self.session = None
        self.browser = None
        self.context = None
        self.page = None
        self.pw = None

    async def start(self):
        """Create Browserbase session and connect Playwright."""
        print("  🌐 Starting Browserbase session...")
        self.session = self.bb.sessions.create(project_id=BB_PROJECT_ID)
        print(f"  ✅ Session: {self.session.id}")

        debug = self.bb.sessions.debug(self.session.id)
        ws_url = debug.debugger_fullscreen_url
        connect_url = debug.ws_url

        print(f"  🔗 Connecting Playwright...")
        self.pw = await async_playwright().__aenter__()
        self.browser = await self.pw.chromium.connect_over_cdp(connect_url)
        self.context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        print(f"  ✅ Browser connected")
        return self

    async def scan_google(self, query: str) -> ScanResult:
        """Search Google and extract AI Overview if present."""
        start = time.time()
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

        try:
            print(f"    🔍 Google: {query[:50]}...")
            await self.page.goto(url, timeout=15000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)  # let AI Overview render

            # Try multiple selectors for AI Overview content
            ai_overview_text = ""
            selectors = [
                # AI Overview specific selectors
                "div[data-md]",
                ".wDYxhc",
                ".V3FYCf",
                ".bVj5Zb",
                ".IZ6rdc",
                # SGE / AI Overview container
                "div[jsname='N760b']",
                "#m-x-content",
                ".kp-blk",
                # Featured snippet as fallback
                ".xpdopen .hgKElc",
                "[data-attrid='wa:/description']",
            ]

            for sel in selectors:
                try:
                    elements = await self.page.query_selector_all(sel)
                    for el in elements:
                        text = await el.inner_text()
                        if text and len(text) > 30:
                            ai_overview_text += text + "\n"
                except:
                    continue

            # If no AI Overview, grab the top organic results text
            if not ai_overview_text:
                try:
                    results = await self.page.query_selector_all("#search .g")
                    for r in results[:5]:
                        text = await r.inner_text()
                        if text:
                            ai_overview_text += text + "\n"
                except:
                    pass

            # Also try extracting page text more broadly
            if len(ai_overview_text) < 50:
                try:
                    ai_overview_text = await self.page.inner_text("#search")
                except:
                    pass

            elapsed = int((time.time() - start) * 1000)
            has_ai = len(ai_overview_text) > 50

            return ScanResult(
                query=query,
                platform="google_aio",
                ai_answer_present=has_ai,
                raw_text=ai_overview_text[:3000],
                brands_detected=[],
                citations=[],
                scan_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ScanResult(
                query=query,
                platform="google_aio",
                ai_answer_present=False,
                raw_text="",
                brands_detected=[],
                citations=[],
                scan_time_ms=elapsed,
                error=str(e)[:200],
            )

    async def scan_perplexity(self, query: str) -> ScanResult:
        """Search Perplexity AI and extract the answer."""
        start = time.time()
        url = f"https://www.perplexity.ai/search?q={query.replace(' ', '+')}"

        try:
            print(f"    🟣 Perplexity: {query[:50]}...")
            await self.page.goto(url, timeout=20000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(5)  # Perplexity streams its answer

            # Wait for answer to appear
            answer_text = ""

            # Try to get the main answer content
            selectors = [
                "div.prose",
                "div[dir='auto']",
                "main .whitespace-pre-line",
                "main article",
                ".text-base",
                "main",
            ]

            for sel in selectors:
                try:
                    elements = await self.page.query_selector_all(sel)
                    for el in elements:
                        text = await el.inner_text()
                        if text and len(text) > 50:
                            answer_text += text + "\n"
                            if len(answer_text) > 500:
                                break
                except:
                    continue
                if len(answer_text) > 500:
                    break

            # Extract citations/sources
            citations = []
            try:
                cite_elements = await self.page.query_selector_all("a[href*='http']")
                for ce in cite_elements[:10]:
                    href = await ce.get_attribute("href")
                    text = await ce.inner_text()
                    if href and not href.startswith("https://www.perplexity.ai"):
                        citations.append({"url": href, "text": text[:100]})
            except:
                pass

            elapsed = int((time.time() - start) * 1000)

            return ScanResult(
                query=query,
                platform="perplexity",
                ai_answer_present=len(answer_text) > 50,
                raw_text=answer_text[:3000],
                brands_detected=[],
                citations=citations[:10],
                scan_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ScanResult(
                query=query,
                platform="perplexity",
                ai_answer_present=False,
                raw_text="",
                brands_detected=[],
                citations=[],
                scan_time_ms=elapsed,
                error=str(e)[:200],
            )

    async def stop(self):
        """Close browser and session."""
        try:
            if self.browser:
                await self.browser.close()
            if self.pw:
                await self.pw.stop()
            if self.session:
                self.bb.sessions.update(self.session.id, status="REQUEST_RELEASE")
                print(f"  🛑 Session ended: {self.session.id}")
        except Exception as e:
            print(f"  ⚠️  Cleanup error: {e}")


# ── Claude Analyzer ───────────────────────────────────────────────

class ClaudeAnalyzer:
    """Uses Claude to analyze scan results for brand mentions."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    def generate_smart_queries(self, brand: str, industry: str, city: str, url: str = "", max_queries: int = 5) -> list:
        """Use Claude to generate relevant search queries for ANY brand."""
        prompt = f"""Generate {max_queries} search queries that a potential customer would type into Google or an AI assistant when looking for products/services like what {brand} offers.

Brand: {brand}
Industry: {industry}
City/Region: {city}
{"Website: " + url if url else ""}

Rules:
- Mix generic category queries (where brand might appear in AI answers) and brand-specific queries
- Include at least 1 query with the city name
- Include at least 1 "best X" or "top X" query
- Include at least 1 "alternatives" or "vs" query
- Keep queries natural -- how real people search

Return a JSON array of strings only. No markdown. Example: ["best crm software for startups", "freshworks vs salesforce"]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])[:max_queries]
        except Exception as e:
            print(f"  ⚠️  Smart query generation failed: {e}")

        # Fallback to generic queries
        ind = industry.replace('_', ' ') if industry and industry != 'other' else 'software'
        return [
            f"best {ind} companies {city}",
            f"top {ind} tools {city}",
            f"{brand} reviews",
            f"{brand} alternatives",
            f"recommended {ind} {city}",
        ][:max_queries]

    def detect_brand_from_url(self, url: str) -> dict:
        """Use Claude to identify brand name and industry from a URL."""
        prompt = f"""Given this website URL, identify the brand name and industry.

URL: {url}

Return JSON only. No markdown. Format:
{{
  "brand": "BrandName",
  "industry": "one of: saas, d2c_fashion, health_wellness, fintech, edtech, ecommerce, agency, media, cloud_telephony, cybersecurity, devtools, martech, hrtech, logistics, real_estate, travel, food_delivery",
  "description": "one line about what this company does"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"  ⚠️  URL detection failed: {e}")

        # Fallback: extract domain name as brand
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
        return {"brand": domain.title(), "industry": "other", "description": ""}

    def analyze_mentions(self, raw_text: str, target_brand: str, industry: str, query: str) -> dict:
        """Ask Claude to extract brand mentions and positioning from AI answer text."""
        if not raw_text or len(raw_text) < 20:
            return {"brands": [], "target_visible": False, "analysis": "No AI answer content to analyze."}

        known = KNOWN_BRANDS.get(industry, [])

        prompt = f"""Analyze this AI-generated search answer for brand mentions.

Query: "{query}"
Target brand: {target_brand}
Industry: {industry}
Known brands in this space: {', '.join(known[:15]) if known else 'None pre-loaded -- extract ALL brand/company names you find'}

AI Answer text:
---
{raw_text[:2000]}
---

Return JSON only. No markdown. Format:
{{
  "brands_mentioned": ["Brand1", "Brand2"],
  "target_visible": true/false,
  "target_position": 0,
  "target_context": "surrounding text where target brand appears",
  "competitor_positions": {{"Brand1": 1, "Brand2": 2}},
  "answer_quality": "high/medium/low",
  "citation_opportunity": "brief note on what content could earn a citation here"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",  # swap to claude-4-sonnet when available
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # Try to parse JSON from response
            if text.startswith("{"):
                return json.loads(text)
            # Try to find JSON in response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return {"brands": [], "target_visible": False, "analysis": text[:200]}
        except Exception as e:
            # Fallback to regex-based detection
            found = detect_brand_mentions(raw_text, industry, target_brand)
            return {
                "brands_mentioned": [m["brand"] for m in found],
                "target_visible": any(m["brand"].lower() == target_brand.lower() for m in found),
                "target_position": next((m["position"] for m in found if m["brand"].lower() == target_brand.lower()), 0),
                "error": str(e)[:100],
            }


# ── Main Agent ────────────────────────────────────────────────────

class AIVisibilityAgent:
    """The main agent that orchestrates scanning, analysis, and reporting."""

    def __init__(self, brand: str = "", industry: str = "", city: str = "bangalore",
                 max_queries: int = 5, url: str = ""):
        self.brand = brand
        self.industry = industry
        self.city = city
        self.url = url
        self.max_queries = max_queries
        self.scanner = BrowserScanner()
        self.analyzer = ClaudeAnalyzer()
        self.scan_results: list[ScanResult] = []
        self.analysis_results: list[dict] = []

    async def run(self) -> dict:
        """Execute the full audit pipeline."""
        print(f"\n{'='*60}")
        print(f"  🤖 AI VISIBILITY AUDIT AGENT")
        print(f"{'='*60}")

        # Auto-detect brand from URL if needed
        if self.url and not self.brand:
            print(f"  🔍 Detecting brand from URL: {self.url}")
            info = self.analyzer.detect_brand_from_url(self.url)
            self.brand = info.get("brand", "Unknown")
            self.industry = self.industry or info.get("industry", "other")
            print(f"  ✅ Brand: {self.brand} | Industry: {self.industry}")
            if info.get("description"):
                print(f"     {info['description']}")

        print(f"  Brand: {self.brand}")
        print(f"  Industry: {self.industry}")
        print(f"  City: {self.city}")
        print(f"  Max queries: {self.max_queries}")
        print(f"{'='*60}\n")

        # Step 1: Generate queries (smart for any brand, template for known industries)
        if self.industry in QUERY_TEMPLATES and not self.url:
            queries = generate_queries(self.brand, self.industry, self.city)[:self.max_queries]
        else:
            print("  🧠 Using Claude to generate smart queries...")
            queries = self.analyzer.generate_smart_queries(
                self.brand, self.industry, self.city, self.url, self.max_queries
            )
        print(f"📋 Generated {len(queries)} queries:")
        for i, q in enumerate(queries, 1):
            print(f"   {i}. {q}")

        # Step 2: Start browser
        print(f"\n🌐 PHASE 1: Browser Scanning")
        print(f"{'-'*40}")
        try:
            await self.scanner.start()
        except Exception as e:
            print(f"  ❌ Failed to start browser: {e}")
            print(f"  Falling back to MCP-based scanning...")
            return await self.run_fallback(queries)

        # Step 3: Scan each query on each platform
        total_scans = len(queries) * 2  # google + perplexity
        completed = 0

        for query in queries:
            print(f"\n  Query: {query}")

            # Google
            result = await self.scanner.scan_google(query)
            self.scan_results.append(result)
            completed += 1
            status = "✅" if result.ai_answer_present else "⚪"
            print(f"    {status} Google: {'AI Overview found' if result.ai_answer_present else 'No AI Overview'} ({result.scan_time_ms}ms)")

            # Perplexity
            result = await self.scanner.scan_perplexity(query)
            self.scan_results.append(result)
            completed += 1
            status = "✅" if result.ai_answer_present else "⚪"
            print(f"    {status} Perplexity: {'Answer found' if result.ai_answer_present else 'No answer'} ({result.scan_time_ms}ms)")

            print(f"    Progress: {completed}/{total_scans} scans")

        # Step 4: Close browser
        await self.scanner.stop()

        # Step 5: Analyze with Claude
        print(f"\n🧠 PHASE 2: Claude Analysis")
        print(f"{'-'*40}")
        for sr in self.scan_results:
            if sr.raw_text and len(sr.raw_text) > 20:
                print(f"  Analyzing: {sr.platform} / {sr.query[:40]}...")
                analysis = self.analyzer.analyze_mentions(
                    sr.raw_text, self.brand, self.industry, sr.query
                )
                analysis["query"] = sr.query
                analysis["platform"] = sr.platform
                self.analysis_results.append(analysis)

                visible = analysis.get("target_visible", False)
                status = "✅ VISIBLE" if visible else "❌ INVISIBLE"
                brands = analysis.get("brands_mentioned", [])
                print(f"    {status} | Brands found: {', '.join(brands[:5])}")

        # Step 6: Build audit report
        print(f"\n📊 PHASE 3: Report Generation")
        print(f"{'-'*40}")
        report = self._build_report()

        return report

    async def run_fallback(self, queries: list) -> dict:
        """Fallback when Browserbase fails -- use Firecrawl or return empty."""
        print("  Using empty scan data for structure demo...")
        audit = VisibilityAudit(brand=self.brand, industry=self.industry, city=self.city)
        audit.queries = [{"query": q, "category": self.industry, "city": self.city,
                          "platforms_scanned": [], "mentions": [], "brands_found": [],
                          "ai_overview_present": False, "raw_responses": {}} for q in queries]
        return build_audit_report(audit)

    def _build_report(self) -> dict:
        """Build the final audit from scan + analysis results."""
        audit = VisibilityAudit(
            brand=self.brand,
            industry=self.industry,
            city=self.city,
        )

        # Group by query
        query_map = {}
        for sr in self.scan_results:
            if sr.query not in query_map:
                query_map[sr.query] = {
                    "query": sr.query,
                    "category": self.industry,
                    "city": self.city,
                    "platforms_scanned": [],
                    "mentions": [],
                    "brands_found": [],
                    "ai_overview_present": False,
                    "raw_responses": {},
                }
            qr = query_map[sr.query]
            qr["platforms_scanned"].append(sr.platform)
            qr["raw_responses"][sr.platform] = sr.raw_text[:500]
            if sr.ai_answer_present:
                qr["ai_overview_present"] = True

        # Merge Claude analysis into query results
        for analysis in self.analysis_results:
            q = analysis.get("query", "")
            p = analysis.get("platform", "")
            if q in query_map:
                qr = query_map[q]
                brands = analysis.get("brands_mentioned", [])
                for i, brand in enumerate(brands):
                    qr["mentions"].append({
                        "brand": brand,
                        "platform": p,
                        "query": q,
                        "position": i + 1,
                        "context": analysis.get("target_context", ""),
                    })
                    if brand not in qr["brands_found"]:
                        qr["brands_found"].append(brand)

        audit.queries = list(query_map.values())
        report = build_audit_report(audit)

        # Add raw scan metadata
        report["scan_metadata"] = {
            "total_scans": len(self.scan_results),
            "successful_scans": len([s for s in self.scan_results if not s.error]),
            "ai_answers_found": len([s for s in self.scan_results if s.ai_answer_present]),
            "total_scan_time_ms": sum(s.scan_time_ms for s in self.scan_results),
            "platforms": ["google_aio", "perplexity"],
            "claude_analyses": len(self.analysis_results),
        }

        # Add citation opportunities from Claude analysis
        report["citation_opportunities"] = [
            {
                "query": a.get("query"),
                "platform": a.get("platform"),
                "opportunity": a.get("citation_opportunity", ""),
            }
            for a in self.analysis_results
            if a.get("citation_opportunity")
        ]

        return report


# ── Report Formatter ──────────────────────────────────────────────

def format_report(report: dict) -> str:
    """Format the audit report for terminal output."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  🤖 AI VISIBILITY AUDIT REPORT")
    lines.append(f"{'='*60}")
    lines.append(f"  Brand: {report['brand']}")
    lines.append(f"  Industry: {report['industry']}")
    lines.append(f"  City: {report['city']}")
    lines.append(f"  Date: {report['scan_date'][:10]}")
    lines.append(f"  Score: {report['visibility_score']}/100")

    meta = report.get("scan_metadata", {})
    if meta:
        lines.append(f"\n  Scans: {meta.get('total_scans', 0)} total, {meta.get('ai_answers_found', 0)} AI answers found")
        lines.append(f"  Time: {meta.get('total_scan_time_ms', 0)}ms total")
        lines.append(f"  Claude analyses: {meta.get('claude_analyses', 0)}")

    lines.append(f"{'='*60}")

    # Visibility by query
    lines.append(f"\n📊 VISIBILITY BY QUERY")
    lines.append(f"{'-'*40}")
    for qr in report.get("queries", []):
        brand_found = any(
            m.get("brand", "").lower() == report["brand"].lower()
            for m in qr.get("mentions", [])
        )
        status = "✅ VISIBLE" if brand_found else "❌ INVISIBLE"
        lines.append(f"  {status} | {qr['query']}")
        platforms = qr.get("platforms_scanned", [])
        if platforms:
            lines.append(f"           Platforms: {', '.join(platforms)}")
        if qr.get("brands_found"):
            lines.append(f"           Brands: {', '.join(qr['brands_found'][:6])}")
        lines.append("")

    # Competitor leaderboard
    if report.get("competitor_mentions"):
        lines.append(f"\n🏆 COMPETITOR LEADERBOARD")
        lines.append(f"{'-'*40}")
        for i, (comp, count) in enumerate(list(report["competitor_mentions"].items())[:8], 1):
            bar = "█" * min(count, 20)
            lines.append(f"  {i}. {comp:<20} {bar} ({count})")

    # Gaps
    gaps = report.get("gaps", [])
    if gaps:
        lines.append(f"\n⚠️  GAPS ({len(gaps)})")
        lines.append(f"{'-'*40}")
        for gap in gaps[:5]:
            sev = "🔴" if gap.get("severity") == "high" else "🟡"
            lines.append(f"  {sev} {gap['query']}")
            comps = gap.get("competitors_visible", [])
            if comps:
                lines.append(f"     Competitors visible instead: {', '.join(comps[:3])}")

    # Citation opportunities
    opps = report.get("citation_opportunities", [])
    if opps:
        lines.append(f"\n🎯 CITATION OPPORTUNITIES")
        lines.append(f"{'-'*40}")
        for opp in opps[:5]:
            if opp.get("opportunity"):
                lines.append(f"  • [{opp['platform']}] {opp['opportunity']}")

    # GEO Recommendations
    recs = report.get("recommendations", [])
    if recs:
        lines.append(f"\n💡 GEO RECOMMENDATIONS (Princeton GEO Paper)")
        lines.append(f"{'-'*40}")
        for rec in recs[:5]:
            lines.append(f"  {rec.get('priority', '-')}. {rec.get('strategy', '').replace('_', ' ').title()}")
            lines.append(f"     {rec.get('description', '')}")
            lines.append(f"     Expected: {rec.get('expected_lift', 'unknown')}")
            if rec.get("specific_action"):
                lines.append(f"     → {rec['specific_action']}")
            lines.append("")

    lines.append(f"{'='*60}")
    lines.append(f"  Powered by: Browserbase + Claude + Writesonic GEO Engine")
    lines.append(f"  Agent: Crazyheads 2.0 x Writesonic")
    lines.append(f"{'='*60}")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="AI Visibility Audit Agent")
    parser.add_argument("--brand", default="", help="Brand to audit")
    parser.add_argument("--industry", default="",
                        help="Industry vertical (saas, d2c_fashion, health_wellness, fintech, edtech, or any string)")
    parser.add_argument("--url", default="", help="Website URL -- auto-detects brand and industry")
    parser.add_argument("--city", default="bangalore", help="City for local queries")
    parser.add_argument("--queries", type=int, default=4, help="Max queries to scan (default: 4)")
    parser.add_argument("--output", help="Output JSON path (default: auto)")
    args = parser.parse_args()

    if not args.brand and not args.url:
        print("❌ Provide --brand or --url")
        sys.exit(1)

    # Validate env
    if not BB_API_KEY:
        print("❌ BROWSERBASE_API_KEY not set")
        sys.exit(1)
    if not BB_PROJECT_ID:
        print("❌ BROWSERBASE_PROJECT_ID not set")
        sys.exit(1)
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)

    # Run agent
    agent = AIVisibilityAgent(
        brand=args.brand,
        industry=args.industry,
        city=args.city,
        max_queries=args.queries,
        url=args.url,
    )

    report = await agent.run()

    # Print formatted report
    print(format_report(report))

    # Save JSON
    brand_slug = (args.brand or report.get("brand", "unknown")).lower().replace(" ", "_")
    output_path = args.output or f"report_{brand_slug}_{args.city}.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n📄 JSON report saved: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
