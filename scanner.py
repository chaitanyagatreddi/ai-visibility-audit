"""
AI Visibility Audit Scanner
============================
Scans brand visibility across AI search platforms:
- Google AI Overviews (via Browserbase)
- Perplexity AI (via Browserbase)
- ChatGPT web (via Browserbase)

Input: brand name + category queries
Output: JSON audit report with visibility gaps and recommendations

Uses Browserbase MCP for headless browser scanning.
This script is orchestrated by Claude Code -- it calls Browserbase MCP tools
through the agent, not directly via API.

For the Writesonic PM demo: Crazyheads 2.0 agency pitching GEO services
to Bangalore D2C and SaaS brands.
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class BrandMention:
    """A single brand mention found in an AI answer."""
    platform: str          # google_aio, perplexity, chatgpt
    query: str             # the search query used
    brand_mentioned: str   # brand name as it appeared
    position: int          # order in the answer (1 = first mentioned)
    context: str           # surrounding text snippet
    citation_url: Optional[str] = None  # if the AI cited a specific URL
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class QueryResult:
    """Results from scanning one query across platforms."""
    query: str
    category: str          # e.g. "saas", "d2c_fashion", "health_wellness"
    city: str              # e.g. "bangalore"
    platforms_scanned: list = field(default_factory=list)
    mentions: list = field(default_factory=list)       # list of BrandMention dicts
    brands_found: list = field(default_factory=list)   # all brands mentioned
    ai_overview_present: bool = False                  # did Google show an AI Overview?
    raw_responses: dict = field(default_factory=dict)  # platform -> raw text


@dataclass
class VisibilityAudit:
    """Complete audit for one brand."""
    brand: str
    industry: str
    city: str
    scan_date: str = ""
    queries: list = field(default_factory=list)        # list of QueryResult dicts
    visibility_score: float = 0.0                      # 0-100
    competitor_mentions: dict = field(default_factory=dict)  # competitor -> count
    gaps: list = field(default_factory=list)            # platforms/queries where brand is invisible
    recommendations: list = field(default_factory=list)

    def __post_init__(self):
        if not self.scan_date:
            self.scan_date = datetime.utcnow().isoformat()


# --- Query Templates ---
# These are the queries we scan for each vertical + city combo.

QUERY_TEMPLATES = {
    "saas": [
        "best {category} tools for startups {city}",
        "top {category} companies in {city} india",
        "recommended {category} software {city}",
        "{category} tools used by startups in {city}",
    ],
    "d2c_fashion": [
        "best d2c fashion brands {city} india",
        "top clothing brands from {city}",
        "affordable fashion brands in {city}",
        "trending d2c brands {city} 2024",
    ],
    "health_wellness": [
        "best ayurvedic supplements brand in {city}",
        "top health and wellness brands {city} india",
        "organic health products {city}",
        "best wellness startups {city}",
    ],
    "fintech": [
        "best fintech startups {city} india",
        "top payment companies {city}",
        "fintech apps for small business {city}",
    ],
    "edtech": [
        "best edtech startups {city} india",
        "online learning platforms from {city}",
        "top education companies {city}",
    ],
}

# Known brands per vertical (Bangalore focused) -- used to detect mentions
KNOWN_BRANDS = {
    "saas": [
        "Freshworks", "Chargebee", "LeadSquared", "Clevertap", "Exotel",
        "Zoho", "Keka", "Razorpay", "Postman", "BrowserStack",
        "Hasura", "Slintel", "MoEngage", "WebEngage", "Hevo Data",
    ],
    "d2c_fashion": [
        "Snitch", "House of Rare", "BlissClub", "Bewakoof", "The Souled Store",
        "Urbanic", "Nykaa Fashion", "Myntra", "AJIO",
    ],
    "health_wellness": [
        "Himalaya Wellness", "Kapiva", "Kerala Ayurveda", "Kama Ayurveda",
        "Dabur", "Baidyanath", "Wellbeing Nutrition", "Anveshan",
        "Open Secret", "Oziva", "HealthKart",
    ],
    "fintech": [
        "Razorpay", "PhonePe", "Jupiter", "Fi Money", "Niyo",
        "Smallcase", "Zerodha", "Groww", "CRED",
    ],
    "edtech": [
        "Byju's", "Unacademy", "Vedantu", "Simplilearn", "upGrad",
        "Scaler", "Newton School", "Masai School",
    ],
}


def generate_queries(brand: str, industry: str, city: str = "bangalore") -> list:
    """Generate search queries for a brand audit."""
    templates = QUERY_TEMPLATES.get(industry, QUERY_TEMPLATES["saas"])
    queries = []
    for template in templates:
        q = template.format(
            category=industry.replace("_", " "),
            city=city,
            brand=brand,
        )
        queries.append(q)

    # Add brand-specific queries
    queries.append(f"{brand} reviews {city}")
    queries.append(f"is {brand} good for {industry.replace('_', ' ')}")
    queries.append(f"{brand} alternatives {city}")

    return queries


def detect_brand_mentions(text: str, industry: str, target_brand: str = "") -> list:
    """Find brand mentions in AI-generated text."""
    found = []
    text_lower = text.lower()

    brands_to_check = KNOWN_BRANDS.get(industry, [])
    if target_brand and target_brand not in brands_to_check:
        brands_to_check = [target_brand] + brands_to_check

    for i, brand in enumerate(brands_to_check):
        if brand.lower() in text_lower:
            # Find context around the mention
            idx = text_lower.index(brand.lower())
            start = max(0, idx - 50)
            end = min(len(text), idx + len(brand) + 50)
            context = text[start:end].strip()

            found.append({
                "brand": brand,
                "position": len(found) + 1,
                "context": context,
            })

    return found


def calculate_visibility_score(audit: VisibilityAudit) -> float:
    """
    Score 0-100 based on:
    - Brand mentioned in AI answers (40 pts)
    - Position when mentioned -- earlier = better (20 pts)
    - Coverage across platforms (20 pts)
    - Coverage across query types (20 pts)
    """
    if not audit.queries:
        return 0.0

    total_queries = len(audit.queries)
    brand = audit.brand.lower()

    # How many queries mention the brand?
    queries_with_mention = 0
    total_position_score = 0
    platforms_with_mention = set()

    for qr in audit.queries:
        qr_data = qr if isinstance(qr, dict) else asdict(qr)
        brand_found = False
        for mention in qr_data.get("mentions", []):
            m = mention if isinstance(mention, dict) else mention
            if isinstance(m, dict) and m.get("brand", "").lower() == brand:
                brand_found = True
                # Position score: 1st = 10, 2nd = 8, 3rd = 6, etc.
                pos = m.get("position", 5)
                total_position_score += max(0, 10 - (pos - 1) * 2)
                # Track platform
                platforms_with_mention.add(qr_data.get("platforms_scanned", ["unknown"])[0] if qr_data.get("platforms_scanned") else "unknown")

        if brand_found:
            queries_with_mention += 1

    # Mention rate (40 pts)
    mention_score = (queries_with_mention / total_queries) * 40

    # Position quality (20 pts)
    max_position_score = queries_with_mention * 10 if queries_with_mention else 1
    position_score = (total_position_score / max_position_score) * 20 if max_position_score else 0

    # Platform coverage (20 pts) -- out of 3 platforms
    platform_score = (len(platforms_with_mention) / 3) * 20

    # Query coverage (20 pts)
    query_score = (queries_with_mention / total_queries) * 20

    return round(mention_score + position_score + platform_score + query_score, 1)


def generate_gap_analysis(audit: VisibilityAudit) -> list:
    """Identify where the brand is invisible."""
    gaps = []
    brand = audit.brand.lower()

    for qr in audit.queries:
        qr_data = qr if isinstance(qr, dict) else asdict(qr)
        brand_found = any(
            (m.get("brand", "").lower() if isinstance(m, dict) else "") == brand
            for m in qr_data.get("mentions", [])
        )

        if not brand_found:
            competitors_visible = [
                m.get("brand", "") if isinstance(m, dict) else str(m)
                for m in qr_data.get("mentions", [])
            ]
            gaps.append({
                "query": qr_data.get("query", ""),
                "platforms": qr_data.get("platforms_scanned", []),
                "competitors_visible": competitors_visible[:5],
                "severity": "high" if competitors_visible else "medium",
            })

    return gaps


# --- GEO Recommendations Engine (Princeton GEO paper) ---

GEO_STRATEGIES = [
    {
        "strategy": "quotation_addition",
        "description": "Add expert quotes and testimonials to key pages",
        "expected_lift": "+41% visibility",
        "priority": 1,
        "implementation": "Add 2-3 expert/customer quotes per product page. Format as blockquotes with attribution.",
    },
    {
        "strategy": "statistics_addition",
        "description": "Add specific data points and numbers",
        "expected_lift": "+32% visibility",
        "priority": 2,
        "implementation": "Include specific metrics: user counts, growth rates, performance benchmarks. AI models prefer concrete numbers.",
    },
    {
        "strategy": "cite_sources",
        "description": "Reference authoritative sources in content",
        "expected_lift": "+30% visibility",
        "priority": 3,
        "implementation": "Link to industry reports, research papers, government data. AI models weight cited content higher.",
    },
    {
        "strategy": "table_formatting",
        "description": "Use comparison tables for feature/price data",
        "expected_lift": "2.5x citation rate",
        "priority": 4,
        "implementation": "Convert lists to HTML tables. Comparison tables are cited 2.5x more often by AI models.",
    },
    {
        "strategy": "structured_data",
        "description": "Add Schema.org markup (FAQ, HowTo, Product)",
        "expected_lift": "improves AI parsing",
        "priority": 5,
        "implementation": "Add JSON-LD structured data. FAQ schema is especially effective for AI answer extraction.",
    },
]


def generate_recommendations(audit: VisibilityAudit) -> list:
    """Generate GEO recommendations based on gaps."""
    recs = []
    gaps = audit.gaps if audit.gaps else generate_gap_analysis(audit)

    if not gaps:
        return [{"strategy": "maintain", "description": "Brand has good AI visibility. Monitor monthly."}]

    high_severity = [g for g in gaps if g.get("severity") == "high"]

    for strategy in GEO_STRATEGIES:
        rec = {
            **strategy,
            "applicable_gaps": len(gaps),
            "high_priority_gaps": len(high_severity),
        }

        # Customize based on industry
        if audit.industry == "saas":
            if strategy["strategy"] == "statistics_addition":
                rec["specific_action"] = f"Add metrics to {audit.brand}'s homepage: active users, uptime %, integrations count, customer logos"
            elif strategy["strategy"] == "table_formatting":
                rec["specific_action"] = f"Create comparison table: {audit.brand} vs top 3 competitors on pricing, features, support"

        elif audit.industry == "health_wellness":
            if strategy["strategy"] == "quotation_addition":
                rec["specific_action"] = f"Add Ayurvedic practitioner endorsements and clinical study references for {audit.brand}"
            elif strategy["strategy"] == "cite_sources":
                rec["specific_action"] = f"Reference AYUSH certifications, clinical trials, ingredient sourcing data"

        recs.append(rec)

    return recs


def build_audit_report(audit: VisibilityAudit) -> dict:
    """Build the final audit report."""
    audit.visibility_score = calculate_visibility_score(audit)
    audit.gaps = generate_gap_analysis(audit)
    audit.recommendations = generate_recommendations(audit)

    # Build competitor leaderboard
    competitor_counts = {}
    for qr in audit.queries:
        qr_data = qr if isinstance(qr, dict) else asdict(qr)
        for m in qr_data.get("mentions", []):
            brand_name = m.get("brand", "") if isinstance(m, dict) else str(m)
            if brand_name.lower() != audit.brand.lower():
                competitor_counts[brand_name] = competitor_counts.get(brand_name, 0) + 1

    audit.competitor_mentions = dict(
        sorted(competitor_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    )

    return asdict(audit)


# --- CLI ---

def main():
    """Run audit from command line."""
    if len(sys.argv) < 3:
        print("Usage: python scanner.py <brand> <industry> [city]")
        print("Industries: saas, d2c_fashion, health_wellness, fintech, edtech")
        print("Example: python scanner.py Freshworks saas bangalore")
        sys.exit(1)

    brand = sys.argv[1]
    industry = sys.argv[2]
    city = sys.argv[3] if len(sys.argv) > 3 else "bangalore"

    # Generate queries
    queries = generate_queries(brand, industry, city)
    print(f"\n🔍 AI Visibility Audit: {brand}")
    print(f"   Industry: {industry} | City: {city}")
    print(f"   Queries to scan: {len(queries)}")
    print(f"\n   Queries:")
    for i, q in enumerate(queries, 1):
        print(f"   {i}. {q}")

    # Create empty audit structure
    audit = VisibilityAudit(
        brand=brand,
        industry=industry,
        city=city,
    )

    # Note: actual scanning happens via Browserbase MCP calls from Claude Code.
    # This script generates the queries and processes the results.
    # Save query list for the agent to scan.
    output = {
        "brand": brand,
        "industry": industry,
        "city": city,
        "queries": queries,
        "scan_instructions": {
            "platforms": ["google_aio", "perplexity", "chatgpt"],
            "per_query": "Search each query on each platform. Extract: brands mentioned, their order, any citations/URLs, full AI answer text.",
            "browserbase_flow": [
                "1. Start Browserbase session",
                "2. For each query + platform:",
                "   - Navigate to platform search",
                "   - Enter query",
                "   - Wait for AI answer to render",
                "   - Extract answer text via observe/extract",
                "3. End session",
            ],
        },
    }

    output_path = f"/Users/chaitanyagatreddi/ws-pm-agent/audit_{brand.lower()}_{city}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n   📄 Query plan saved to: {output_path}")
    print(f"   Next: Run Browserbase scans via Claude Code agent")


if __name__ == "__main__":
    main()
