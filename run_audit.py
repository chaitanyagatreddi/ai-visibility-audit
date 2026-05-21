"""
AI Visibility Audit Runner
============================
Orchestration script that:
1. Loads query plan from scanner.py output
2. Runs Browserbase scans (called by Claude Code agent)
3. Processes scan results through gap analyzer
4. Generates final audit report with GEO recommendations

Usage:
  python run_audit.py scan <brand> <industry> [city]    -- generate queries + scan plan
  python run_audit.py process <results_json>             -- process scan results into report
  python run_audit.py demo                               -- run with pre-collected scan data
"""

import json
import sys
from datetime import datetime
from scanner import (
    VisibilityAudit, QueryResult, BrandMention,
    detect_brand_mentions, build_audit_report,
    generate_queries, KNOWN_BRANDS, GEO_STRATEGIES,
)


# Pre-collected scan data from Browserbase sessions (May 20, 2026)
# These are real results from our earlier scans.
DEMO_SCAN_DATA = {
    "brand": "Freshworks",
    "industry": "saas",
    "city": "bangalore",
    "scans": [
        {
            "query": "best saas tools for startups bangalore",
            "platform": "google_aio",
            "ai_overview_present": True,
            "raw_text": "Some of the best SaaS tools for startups in Bangalore include Keka for HR management, Zoho Books for accounting, Slack for communication, and Notion for project management. Bangalore's startup ecosystem also benefits from tools like Razorpay for payments and Postman for API development.",
            "brands_mentioned": ["Keka", "Zoho", "Slack", "Notion", "Razorpay", "Postman"],
        },
        {
            "query": "best saas tools for startups bangalore",
            "platform": "perplexity",
            "ai_overview_present": True,
            "raw_text": "Bangalore-based startups commonly use several SaaS tools. For HR, Keka and Darwinbox are popular. Zoho offers a comprehensive suite. For payments, Razorpay dominates. Developer tools include Postman and Hasura. CRM options include Freshworks CRM and LeadSquared.",
            "brands_mentioned": ["Keka", "Darwinbox", "Zoho", "Razorpay", "Postman", "Hasura", "Freshworks", "LeadSquared"],
        },
        {
            "query": "top saas companies in bangalore india",
            "platform": "google_aio",
            "ai_overview_present": True,
            "raw_text": "Bangalore is home to several major SaaS companies including Freshworks (CRM, ITSM), Zoho (business suite), Razorpay (payments), Postman (API platform), and BrowserStack (testing). Other notable companies include Chargebee (subscription billing), MoEngage (customer engagement), and Clevertap (analytics).",
            "brands_mentioned": ["Freshworks", "Zoho", "Razorpay", "Postman", "BrowserStack", "Chargebee", "MoEngage", "Clevertap"],
        },
        {
            "query": "top saas companies in bangalore india",
            "platform": "perplexity",
            "ai_overview_present": True,
            "raw_text": "Bangalore's top SaaS companies include Freshworks (valued at $12B+, CRM and IT service management), Razorpay (payments infrastructure), Postman (API development platform), Zoho (comprehensive business suite based in Chennai but with major Bangalore operations), BrowserStack (cross-browser testing), Chargebee (subscription management), and LeadSquared (marketing automation).",
            "brands_mentioned": ["Freshworks", "Razorpay", "Postman", "Zoho", "BrowserStack", "Chargebee", "LeadSquared"],
        },
        {
            "query": "recommended saas software bangalore",
            "platform": "google_aio",
            "ai_overview_present": True,
            "raw_text": "For startups in Bangalore, recommended SaaS software includes Zoho One for an all-in-one business suite, Keka for payroll and HR, Razorpay for payment processing, and Slack or Microsoft Teams for communication. For customer support, Freshdesk by Freshworks is widely used.",
            "brands_mentioned": ["Zoho", "Keka", "Razorpay", "Slack", "Microsoft Teams", "Freshworks"],
        },
        {
            "query": "saas tools used by startups in bangalore",
            "platform": "google_aio",
            "ai_overview_present": False,
            "raw_text": "",
            "brands_mentioned": [],
        },
        {
            "query": "Freshworks reviews bangalore",
            "platform": "google_aio",
            "ai_overview_present": True,
            "raw_text": "Freshworks, headquartered in Chennai with significant operations in Bangalore, offers a suite of business software. Reviews highlight its ease of use and competitive pricing compared to Salesforce and Zendesk. G2 rating: 4.4/5. Common praise: intuitive UI, good customer support. Common complaints: limited customization for enterprise.",
            "brands_mentioned": ["Freshworks", "Salesforce", "Zendesk"],
        },
    ],
}

# Demo data for a brand with LOW visibility (the real pitch)
DEMO_SCAN_DATA_LOW = {
    "brand": "Exotel",
    "industry": "saas",
    "city": "bangalore",
    "scans": [
        {
            "query": "best saas tools for startups bangalore",
            "platform": "google_aio",
            "ai_overview_present": True,
            "raw_text": "Some of the best SaaS tools for startups in Bangalore include Keka for HR management, Zoho Books for accounting, Slack for communication, and Notion for project management.",
            "brands_mentioned": ["Keka", "Zoho", "Slack", "Notion"],
        },
        {
            "query": "best saas tools for startups bangalore",
            "platform": "perplexity",
            "ai_overview_present": True,
            "raw_text": "Bangalore-based startups commonly use Keka, Zoho, Razorpay, Postman, and Freshworks CRM.",
            "brands_mentioned": ["Keka", "Zoho", "Razorpay", "Postman", "Freshworks"],
        },
        {
            "query": "best cloud telephony bangalore",
            "platform": "google_aio",
            "ai_overview_present": True,
            "raw_text": "For cloud telephony in Bangalore, popular options include Knowlarity, MyOperator, and Ozonetel. These platforms offer IVR, call tracking, and CRM integrations suitable for Indian businesses.",
            "brands_mentioned": ["Knowlarity", "MyOperator", "Ozonetel"],
        },
        {
            "query": "best cloud telephony bangalore",
            "platform": "perplexity",
            "ai_overview_present": True,
            "raw_text": "Leading cloud telephony providers in India include Knowlarity, Exotel, MyOperator, and Ozonetel. Exotel is based in Bangalore and serves over 6000 businesses. Knowlarity has the largest market share.",
            "brands_mentioned": ["Knowlarity", "Exotel", "MyOperator", "Ozonetel"],
        },
    ],
}


def process_scan_results(scan_data: dict) -> dict:
    """Process raw scan results into a full audit report."""
    brand = scan_data["brand"]
    industry = scan_data["industry"]
    city = scan_data["city"]

    audit = VisibilityAudit(
        brand=brand,
        industry=industry,
        city=city,
    )

    query_results = {}  # group by query

    for scan in scan_data["scans"]:
        query = scan["query"]
        if query not in query_results:
            query_results[query] = {
                "query": query,
                "category": industry,
                "city": city,
                "platforms_scanned": [],
                "mentions": [],
                "brands_found": [],
                "ai_overview_present": False,
                "raw_responses": {},
            }

        qr = query_results[query]
        platform = scan["platform"]
        qr["platforms_scanned"].append(platform)
        qr["raw_responses"][platform] = scan.get("raw_text", "")

        if scan.get("ai_overview_present"):
            qr["ai_overview_present"] = True

        # Detect mentions from raw text
        if scan.get("raw_text"):
            found = detect_brand_mentions(scan["raw_text"], industry, brand)
            for m in found:
                m["platform"] = platform
                m["query"] = query
                qr["mentions"].append(m)
                if m["brand"] not in qr["brands_found"]:
                    qr["brands_found"].append(m["brand"])

        # Also use pre-detected brands from scan
        for b in scan.get("brands_mentioned", []):
            if b not in qr["brands_found"]:
                qr["brands_found"].append(b)
            # Add as mention if not already detected
            already_found = any(
                m.get("brand", "").lower() == b.lower() and m.get("platform") == platform
                for m in qr["mentions"]
            )
            if not already_found:
                qr["mentions"].append({
                    "brand": b,
                    "platform": platform,
                    "query": query,
                    "position": len([m for m in qr["mentions"] if m.get("platform") == platform]) + 1,
                    "context": f"Mentioned in {platform} answer for '{query}'",
                })

    audit.queries = list(query_results.values())
    report = build_audit_report(audit)

    return report


def format_report(report: dict) -> str:
    """Format audit report as readable text."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  AI VISIBILITY AUDIT REPORT")
    lines.append(f"{'='*60}")
    lines.append(f"  Brand: {report['brand']}")
    lines.append(f"  Industry: {report['industry']}")
    lines.append(f"  City: {report['city']}")
    lines.append(f"  Date: {report['scan_date'][:10]}")
    lines.append(f"  Visibility Score: {report['visibility_score']}/100")
    lines.append(f"{'='*60}")

    # Visibility by query
    lines.append(f"\n📊 VISIBILITY BY QUERY")
    lines.append(f"{'-'*40}")
    for qr in report["queries"]:
        brand_found = any(
            m.get("brand", "").lower() == report["brand"].lower()
            for m in qr.get("mentions", [])
        )
        status = "✅ VISIBLE" if brand_found else "❌ INVISIBLE"
        lines.append(f"  {status} | {qr['query']}")
        platforms = qr.get("platforms_scanned", [])
        lines.append(f"           Platforms: {', '.join(platforms)}")
        if qr.get("brands_found"):
            lines.append(f"           Brands found: {', '.join(qr['brands_found'][:5])}")
        lines.append("")

    # Competitor leaderboard
    if report.get("competitor_mentions"):
        lines.append(f"\n🏆 COMPETITOR VISIBILITY LEADERBOARD")
        lines.append(f"{'-'*40}")
        for i, (comp, count) in enumerate(report["competitor_mentions"].items(), 1):
            bar = "█" * count
            lines.append(f"  {i}. {comp:<20} {bar} ({count} mentions)")

    # Gaps
    if report.get("gaps"):
        lines.append(f"\n⚠️  VISIBILITY GAPS ({len(report['gaps'])} found)")
        lines.append(f"{'-'*40}")
        for gap in report["gaps"]:
            sev = "🔴" if gap["severity"] == "high" else "🟡"
            lines.append(f"  {sev} Query: {gap['query']}")
            if gap.get("competitors_visible"):
                lines.append(f"     Competitors visible: {', '.join(gap['competitors_visible'][:3])}")

    # Recommendations
    if report.get("recommendations"):
        lines.append(f"\n💡 GEO RECOMMENDATIONS")
        lines.append(f"{'-'*40}")
        for rec in report["recommendations"][:5]:
            lines.append(f"  {rec['priority']}. {rec['strategy'].replace('_', ' ').title()}")
            lines.append(f"     {rec['description']}")
            lines.append(f"     Expected lift: {rec['expected_lift']}")
            if rec.get("specific_action"):
                lines.append(f"     → {rec['specific_action']}")
            lines.append("")

    lines.append(f"{'='*60}")
    lines.append(f"  Powered by Batman AI Visibility Audit")
    lines.append(f"  Batman GEO Platform")
    lines.append(f"{'='*60}")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_audit.py demo              -- run with pre-collected data")
        print("  python run_audit.py demo-low           -- run with low-visibility brand")
        print("  python run_audit.py process <file.json> -- process scan results")
        sys.exit(1)

    command = sys.argv[1]

    if command == "demo":
        print("Running demo audit with pre-collected Browserbase scan data...")
        report = process_scan_results(DEMO_SCAN_DATA)
        print(format_report(report))

        # Save JSON report
        output_path = "/Users/chaitanyagatreddi/ws-pm-agent/report_freshworks_bangalore.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Full JSON report: {output_path}")

    elif command == "demo-low":
        print("Running demo audit for LOW visibility brand...")
        report = process_scan_results(DEMO_SCAN_DATA_LOW)
        print(format_report(report))

        output_path = "/Users/chaitanyagatreddi/ws-pm-agent/report_exotel_bangalore.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Full JSON report: {output_path}")

    elif command == "process":
        if len(sys.argv) < 3:
            print("Error: provide path to scan results JSON")
            sys.exit(1)
        with open(sys.argv[2]) as f:
            scan_data = json.load(f)
        report = process_scan_results(scan_data)
        print(format_report(report))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
