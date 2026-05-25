#!/usr/bin/env python3
"""
AI Visibility Audit - Web App
===============================
Flask web app wrapping the audit agent.
Enter a brand name, get a live AI visibility report.

Run locally:
  pip3 install flask
  export BROWSERBASE_API_KEY=... BROWSERBASE_PROJECT_ID=... OPENAI_API_KEY=...
  python3 app.py

Deploy anywhere: Replit, Railway, Render, Vercel (serverless).
"""

import asyncio
import json
import os
import sys
import traceback
from datetime import datetime

try:
    from flask import Flask, render_template_string, request, jsonify, Response
except ImportError:
    print("pip3 install flask")
    sys.exit(1)
import queue
import threading

from agent import AIVisibilityAgent
from scanner import KNOWN_BRANDS, QUERY_TEMPLATES

app = Flask(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Visibility Audit | Batman</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; }

  .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); padding: 2rem; text-align: center; border-bottom: 2px solid #e94560; }
  .header h1 { font-size: 1.8rem; color: #fff; margin-bottom: 0.3rem; }
  .header .subtitle { color: #e94560; font-size: 0.9rem; letter-spacing: 2px; text-transform: uppercase; }
  .header .tagline { color: #888; font-size: 0.85rem; margin-top: 0.5rem; }

  .container { max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }

  .form-card { background: #141414; border: 1px solid #2a2a2a; border-radius: 12px; padding: 2rem; margin-bottom: 2rem; }
  .form-row { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
  .form-group { flex: 1; min-width: 200px; }
  .form-group label { display: block; color: #888; font-size: 0.8rem; margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 1px; }
  .form-group input, .form-group select { width: 100%; padding: 0.75rem 1rem; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 1rem; }
  .form-group input:focus, .form-group select:focus { outline: none; border-color: #e94560; }

  .btn { background: #e94560; color: #fff; border: none; padding: 0.85rem 2rem; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600; transition: all 0.2s; }
  .btn:hover { background: #c73550; transform: translateY(-1px); }
  .btn:disabled { background: #444; cursor: not-allowed; transform: none; }
  .btn-row { text-align: center; margin-top: 1.5rem; }

  .agents-panel { display: none; margin: 2rem 0; background: #141414; border: 1px solid #2a2a2a; border-radius: 12px; padding: 1.5rem; }
  .agents-panel.active { display: block; }
  .agents-panel h3 { color: #e94560; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 1rem; }
  .agent-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0.75rem; margin: 0.3rem 0; background: #1a1a1a; border-radius: 8px; border-left: 3px solid #333; font-size: 0.85rem; transition: all 0.3s; }
  .agent-row.running { border-left-color: #f0c040; }
  .agent-row.done { border-left-color: #4ade80; }
  .agent-row.error { border-left-color: #e94560; }
  .agent-icon { width: 20px; text-align: center; }
  .agent-label { color: #ccc; font-weight: 600; min-width: 140px; }
  .agent-detail { color: #888; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .agent-row.running .agent-icon::after { content: '⏳'; }
  .agent-row.done .agent-icon::after { content: '✅'; }
  .agent-row.error .agent-icon::after { content: '❌'; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
  .agent-row.running { animation: pulse 1.5s ease-in-out infinite; }

  .cost-card { background: linear-gradient(135deg, #2a1a1a 0%, #1a1a2e 100%); border: 1px solid #e94560; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }
  .cost-card h3 { color: #e94560; margin-bottom: 1rem; font-size: 1rem; }
  .cost-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
  .cost-stat { text-align: center; padding: 1rem; background: rgba(0,0,0,0.3); border-radius: 8px; }
  .cost-stat .number { font-size: 1.6rem; font-weight: 700; color: #e94560; }
  .cost-stat .label { font-size: 0.75rem; color: #888; margin-top: 0.3rem; text-transform: uppercase; letter-spacing: 1px; }
  .cost-note { color: #666; font-size: 0.75rem; margin-top: 1rem; font-style: italic; }

  .progress { display: none; margin: 2rem 0; }
  .progress.active { display: block; }
  .progress-bar { height: 4px; background: #1a1a1a; border-radius: 2px; overflow: hidden; }
  .progress-fill { height: 100%; background: linear-gradient(90deg, #e94560, #ff6b81); width: 0%; transition: width 0.5s; border-radius: 2px; }
  .progress-text { color: #888; font-size: 0.85rem; margin-top: 0.5rem; text-align: center; }

  .report { display: none; }
  .report.active { display: block; }

  .score-card { background: linear-gradient(135deg, #141414, #1a1a2e); border: 1px solid #2a2a2a; border-radius: 12px; padding: 2rem; text-align: center; margin-bottom: 2rem; }
  .score-number { font-size: 4rem; font-weight: 800; }
  .score-low { color: #e94560; }
  .score-mid { color: #ffa502; }
  .score-high { color: #2ed573; }
  .score-label { color: #888; font-size: 0.9rem; margin-top: 0.3rem; }

  .section { background: #141414; border: 1px solid #2a2a2a; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
  .section h3 { color: #fff; margin-bottom: 1rem; font-size: 1.1rem; }

  .query-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 0; border-bottom: 1px solid #1a1a1a; }
  .query-row:last-child { border-bottom: none; }
  .query-status { font-size: 1.2rem; }
  .query-text { flex: 1; font-size: 0.9rem; }
  .query-brands { color: #888; font-size: 0.8rem; }

  .competitor-bar { display: flex; align-items: center; gap: 0.75rem; padding: 0.4rem 0; }
  .competitor-name { width: 150px; font-size: 0.9rem; text-align: right; }
  .competitor-fill { height: 20px; background: linear-gradient(90deg, #e94560, #ff6b81); border-radius: 4px; min-width: 4px; transition: width 0.5s; }
  .competitor-count { color: #888; font-size: 0.8rem; margin-left: 0.5rem; }

  .gap-item { padding: 0.75rem; background: #1a1a1a; border-radius: 8px; margin-bottom: 0.5rem; border-left: 3px solid #e94560; }
  .gap-item.medium { border-left-color: #ffa502; }
  .gap-query { font-size: 0.9rem; margin-bottom: 0.3rem; }
  .gap-competitors { color: #888; font-size: 0.8rem; }

  .rec-item { padding: 1rem; background: #1a1a1a; border-radius: 8px; margin-bottom: 0.75rem; }
  .rec-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
  .rec-strategy { font-weight: 600; color: #fff; }
  .rec-lift { color: #2ed573; font-size: 0.85rem; font-weight: 600; }
  .rec-desc { color: #aaa; font-size: 0.85rem; margin-bottom: 0.3rem; }
  .rec-action { color: #e94560; font-size: 0.85rem; font-style: italic; }

  .footer { text-align: center; padding: 2rem; color: #444; font-size: 0.8rem; }
  .footer a { color: #e94560; text-decoration: none; }

  .error { background: #2a1a1a; border: 1px solid #e94560; border-radius: 8px; padding: 1rem; color: #ff6b81; margin: 1rem 0; display: none; }
  .error.active { display: block; }
</style>
</head>
<body>

<div class="header">
  <h1>AI Visibility Audit</h1>
  <div class="subtitle">Generative Engine Optimization Scanner</div>
  <div class="tagline">See where your brand appears (and disappears) in AI search answers</div>
</div>

<div class="container">
  <div class="form-card">
    <div class="form-row">
      <div class="form-group" style="min-width:100%">
        <label>Website URL (or just enter brand name below)</label>
        <input type="text" id="url" placeholder="https://freshworks.com or https://exotel.com">
      </div>
      <div class="form-group">
        <label>Brand Name <span style="color:#555">(auto-detected from URL)</span></label>
        <input type="text" id="brand" placeholder="e.g. Freshworks, Exotel, Kapiva">
      </div>
      <div class="form-group">
        <label>Industry</label>
        <select id="industry">
          <option value="">Auto-detect</option>
          <option value="saas">SaaS / Software</option>
          <option value="d2c_fashion">D2C Fashion</option>
          <option value="health_wellness">Health & Wellness</option>
          <option value="fintech">Fintech</option>
          <option value="edtech">Edtech</option>
          <option value="ecommerce">E-commerce</option>
          <option value="agency">Agency</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div class="form-group">
        <label>City</label>
        <input type="text" id="city" placeholder="bangalore" value="bangalore">
      </div>
    </div>
    <div class="btn-row">
      <button class="btn" id="scanBtn" onclick="startAudit()">Run AI Visibility Audit</button>
    </div>
  </div>

  <div class="progress" id="progress">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-text" id="progressText">Starting Browserbase session...</div>
  </div>

  <div class="agents-panel" id="agentsPanel">
    <h3>🤖 Agent Swarm</h3>
    <div id="agentsList"></div>
  </div>

  <div class="error" id="error"></div>

  <div class="report" id="report">
    <div class="score-card">
      <div class="score-number" id="scoreNumber">--</div>
      <div class="score-label">AI Visibility Score (out of 100)</div>
    </div>

    <div class="cost-card" id="costCard">
      <h3>💰 Cost of Inaction</h3>
      <div class="cost-grid" id="costGrid"></div>
      <div class="cost-note">Estimates based on industry avg search volumes and AI answer click-through rates (Authoritas 2024 study).</div>
    </div>

    <div class="section">
      <h3>Visibility by Query</h3>
      <div id="queryResults"></div>
    </div>

    <div class="section">
      <h3>Competitor Leaderboard</h3>
      <div id="competitors"></div>
    </div>

    <div class="section">
      <h3>Visibility Gaps</h3>
      <div id="gaps"></div>
    </div>

    <div class="section">
      <h3>GEO Recommendations</h3>
      <div id="recommendations"></div>
    </div>
  </div>
</div>

<div class="footer">
  Powered by <a href="#">Browserbase</a> + OpenAI + GEO Engine<br>
  Batman &mdash; AI Visibility Services
</div>

<script>
async function startAudit() {
  const url = document.getElementById('url').value.trim();
  const brand = document.getElementById('brand').value.trim();
  const industry = document.getElementById('industry').value;
  const city = document.getElementById('city').value.trim() || 'bangalore';

  if (!brand && !url) { alert('Enter a website URL or brand name'); return; }

  const btn = document.getElementById('scanBtn');
  const agentsPanel = document.getElementById('agentsPanel');
  const agentsList = document.getElementById('agentsList');
  const report = document.getElementById('report');
  const error = document.getElementById('error');

  btn.disabled = true;
  btn.textContent = 'Agents Running...';
  agentsPanel.classList.add('active');
  agentsList.innerHTML = '';
  report.classList.remove('active');
  error.classList.remove('active');

  function updateAgent(id, status, label, detail) {
    let row = document.getElementById('agent-' + id);
    if (!row) {
      row = document.createElement('div');
      row.id = 'agent-' + id;
      row.className = 'agent-row ' + status;
      row.innerHTML = '<span class="agent-icon"></span><span class="agent-label">' + label + '</span><span class="agent-detail">' + detail + '</span>';
      agentsList.appendChild(row);
    } else {
      row.className = 'agent-row ' + status;
      row.querySelector('.agent-detail').textContent = detail;
    }
    row.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }

  try {
    const resp = await fetch('/api/audit/stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({brand, industry, city, url, max_queries: 3})
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});

      const lines = buffer.split(String.fromCharCode(10)+String.fromCharCode(10));
      buffer = lines.pop();

      for (const block of lines) {
        if (!block.trim()) continue;
        const eventMatch = block.match(/^event: (.+)$/m);
        const dataMatch = block.match(/^data: (.+)$/m);
        if (!eventMatch || !dataMatch) continue;
        const eventType = eventMatch[1];
        const payload = JSON.parse(dataMatch[1]);

        if (eventType === 'agent') {
          updateAgent(payload.id, payload.status, payload.label, payload.detail);
        } else if (eventType === 'result') {
          renderReport(payload);
        } else if (eventType === 'error') {
          error.textContent = 'Error: ' + payload.error;
          error.classList.add('active');
        }
      }
    }
  } catch (e) {
    error.textContent = 'Error: ' + e.message;
    error.classList.add('active');
  }

  btn.disabled = false;
  btn.textContent = 'Run AI Visibility Audit';
}

function renderReport(r) {
  const report = document.getElementById('report');
  report.classList.add('active');

  // Score
  const scoreEl = document.getElementById('scoreNumber');
  const score = r.visibility_score || 0;
  scoreEl.textContent = score.toFixed(1);
  scoreEl.className = 'score-number ' + (score < 30 ? 'score-low' : score < 60 ? 'score-mid' : 'score-high');

  // Cost of Inaction
  const totalQueries = (r.queries || []).length;
  const invisibleQueries = (r.queries || []).filter(q => !(q.mentions || []).some(m => m.brand && m.brand.toLowerCase() === r.brand.toLowerCase())).length;
  const competitorCount = Object.keys(r.competitor_mentions || {}).length;
  const avgMonthlySearches = totalQueries * 2400;
  const aiClickRate = 0.38;
  const missedClicks = Math.round(invisibleQueries * 2400 * aiClickRate);
  const missedLeads = Math.round(missedClicks * 0.03);
  const missedRevenue = missedLeads * 120;
  const costGrid = document.getElementById('costGrid');
  costGrid.innerHTML =
    '<div class="cost-stat"><div class="number">' + invisibleQueries + '/' + totalQueries + '</div><div class="label">Queries Invisible</div></div>' +
    '<div class="cost-stat"><div class="number">' + missedClicks.toLocaleString() + '</div><div class="label">Missed Clicks/Month</div></div>' +
    '<div class="cost-stat"><div class="number">' + missedLeads.toLocaleString() + '</div><div class="label">Lost Leads/Month</div></div>' +
    '<div class="cost-stat"><div class="number">$' + missedRevenue.toLocaleString() + '</div><div class="label">Revenue at Risk/Month</div></div>' +
    '<div class="cost-stat"><div class="number">' + competitorCount + '</div><div class="label">Competitors Ahead</div></div>';

  // Queries
  const qDiv = document.getElementById('queryResults');
  qDiv.innerHTML = (r.queries || []).map(q => {
    const visible = (q.mentions || []).some(m => m.brand && m.brand.toLowerCase() === r.brand.toLowerCase());
    return '<div class="query-row">' +
      '<span class="query-status">' + (visible ? '✅' : '❌') + '</span>' +
      '<div><div class="query-text">' + q.query + '</div>' +
      '<div class="query-brands">Brands: ' + (q.brands_found || []).slice(0,5).join(', ') + '</div></div></div>';
  }).join('');

  // Competitors
  const cDiv = document.getElementById('competitors');
  const comps = r.competitor_mentions || {};
  const maxCount = Math.max(...Object.values(comps), 1);
  cDiv.innerHTML = Object.entries(comps).slice(0,8).map(([name, count]) =>
    '<div class="competitor-bar">' +
    '<span class="competitor-name">' + name + '</span>' +
    '<div class="competitor-fill" style="width:' + (count/maxCount*200) + 'px"></div>' +
    '<span class="competitor-count">' + count + '</span></div>'
  ).join('');

  // Gaps
  const gDiv = document.getElementById('gaps');
  gDiv.innerHTML = (r.gaps || []).map(g =>
    '<div class="gap-item ' + (g.severity || '') + '">' +
    '<div class="gap-query">' + (g.severity === 'high' ? '🔴' : '🟡') + ' ' + g.query + '</div>' +
    '<div class="gap-competitors">Competitors visible: ' + (g.competitors_visible || []).slice(0,3).join(', ') + '</div></div>'
  ).join('') || '<p style="color:#888">No gaps found - great AI visibility!</p>';

  // Recommendations
  const rDiv = document.getElementById('recommendations');
  rDiv.innerHTML = (r.recommendations || []).slice(0,5).map(rec =>
    '<div class="rec-item">' +
    '<div class="rec-header"><span class="rec-strategy">' + (rec.strategy||'').replace(/_/g,' ').replace(/\\b\\w/g,l=>l.toUpperCase()) + '</span>' +
    '<span class="rec-lift">' + (rec.expected_lift||'') + '</span></div>' +
    '<div class="rec-desc">' + (rec.description||'') + '</div>' +
    (rec.specific_action ? '<div class="rec-action">' + rec.specific_action + '</div>' : '') + '</div>'
  ).join('');
}
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/audit", methods=["POST"])
def run_audit():
    data = request.json
    brand = data.get("brand", "").strip()
    industry = data.get("industry", "")
    city = data.get("city", "bangalore")
    url = data.get("url", "").strip()
    max_queries = min(data.get("max_queries", 3), 5)

    if not brand and not url:
        return jsonify({"error": "Brand name or URL required"}), 400

    try:
        agent = AIVisibilityAgent(
            brand=brand,
            industry=industry,
            city=city,
            url=url,
            max_queries=max_queries,
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        report = loop.run_until_complete(agent.run())
        loop.close()
        return jsonify(report)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/stream", methods=["POST"])
def run_audit_stream():
    """SSE streaming endpoint - shows agent steps live."""
    data = request.json
    brand = data.get("brand", "").strip()
    industry = data.get("industry", "")
    city = data.get("city", "bangalore")
    url = data.get("url", "").strip()
    max_queries = min(data.get("max_queries", 3), 5)

    if not brand and not url:
        return jsonify({"error": "Brand name or URL required"}), 400

    q = queue.Queue()

    def emit(event_type, payload):
        q.put(f"event: {event_type}\ndata: {json.dumps(payload)}\n\n")

    def run_agent():
        try:
            agent = AIVisibilityAgent(
                brand=brand, industry=industry, city=city,
                url=url, max_queries=max_queries,
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Phase 0: detect brand
            if url and not brand:
                emit("agent", {"id": "brand-detector", "status": "running", "label": "Brand Detector", "detail": f"Analyzing {url}"})
                info = agent.analyzer.detect_brand_from_url(url)
                agent.brand = info.get("brand", "Unknown")
                agent.industry = agent.industry or info.get("industry", "other")
                emit("agent", {"id": "brand-detector", "status": "done", "label": "Brand Detector", "detail": f"{agent.brand} ({agent.industry})"})

            # Phase 1: generate queries
            emit("agent", {"id": "query-gen", "status": "running", "label": "Query Generator", "detail": "Generating search queries..."})
            from scanner import QUERY_TEMPLATES, generate_queries
            if agent.industry in QUERY_TEMPLATES and not agent.url:
                queries = generate_queries(agent.brand, agent.industry, agent.city)[:max_queries]
            else:
                queries = agent.analyzer.generate_smart_queries(agent.brand, agent.industry, agent.city, agent.url, max_queries)
            emit("agent", {"id": "query-gen", "status": "done", "label": "Query Generator", "detail": f"{len(queries)} queries ready"})
            emit("queries", {"queries": queries})

            # Phase 2: start browser
            emit("agent", {"id": "browser", "status": "running", "label": "Browserbase", "detail": "Starting cloud browser..."})
            loop.run_until_complete(agent.scanner.start())
            emit("agent", {"id": "browser", "status": "done", "label": "Browserbase", "detail": "Browser ready"})

            # Phase 3: parallel scans per query
            for i, query in enumerate(queries):
                gid = f"google-{i}"
                pid = f"perplexity-{i}"
                emit("agent", {"id": gid, "status": "running", "label": f"Google AIO Scanner", "detail": query[:50]})
                emit("agent", {"id": pid, "status": "running", "label": f"Perplexity Scanner", "detail": query[:50]})

                g_result = loop.run_until_complete(agent.scanner.scan_google(query))
                agent.scan_results.append(g_result)
                g_status = "✅ AI Overview found" if g_result.ai_answer_present else "No AI Overview"
                emit("agent", {"id": gid, "status": "done", "label": "Google AIO Scanner", "detail": f"{g_status} ({g_result.scan_time_ms}ms)"})

                p_result = loop.run_until_complete(agent.scanner.scan_perplexity(query))
                agent.scan_results.append(p_result)
                p_status = "✅ Answer found" if p_result.ai_answer_present else "No answer"
                emit("agent", {"id": pid, "status": "done", "label": "Perplexity Scanner", "detail": f"{p_status} ({p_result.scan_time_ms}ms)"})

            # Phase 4: LLM analysis
            for sr in agent.scan_results:
                if sr.raw_text and len(sr.raw_text) > 20:
                    aid = f"analyze-{sr.platform}-{sr.query[:20]}"
                    emit("agent", {"id": aid, "status": "running", "label": "LLM Analyzer", "detail": f"{sr.platform}: {sr.query[:40]}"})
                    analysis = agent.analyzer.analyze_mentions(sr.raw_text, agent.brand, agent.industry, sr.query)
                    analysis["query"] = sr.query
                    analysis["platform"] = sr.platform
                    agent.analysis_results.append(analysis)
                    brands = analysis.get("brands_mentioned", [])
                    emit("agent", {"id": aid, "status": "done", "label": "LLM Analyzer", "detail": f"Found: {', '.join(brands[:4])}" if brands else "No brands found"})

            # Phase 5: stop browser
            loop.run_until_complete(agent.scanner.stop())

            # Phase 6: build report
            emit("agent", {"id": "report-builder", "status": "running", "label": "Report Builder", "detail": "Scoring & recommendations..."})
            report = agent._build_report()
            emit("agent", {"id": "report-builder", "status": "done", "label": "Report Builder", "detail": f"Score: {report.get('visibility_score', 0):.1f}/100"})

            loop.close()
            emit("result", report)
        except Exception as e:
            traceback.print_exc()
            emit("error", {"error": str(e)})
        finally:
            q.put(None)

    threading.Thread(target=run_agent, daemon=True).start()

    def generate():
        while True:
            item = q.get()
            if item is None:
                break
            yield item

    return Response(generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "browserbase": bool(os.environ.get("BROWSERBASE_API_KEY")),
        "anthropic": bool(os.environ.get("OPENAI_API_KEY")),
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── GitHub Radar ─────────────────────────────────────────────────

GITHUB_RADAR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitHub Radar | Batman</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
         background: #0d1117; color: #e6edf3; min-height: 100vh; padding: 24px; }
  .header { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; }
  .header h1 { font-size: 20px; font-weight: 700; color: #f0f6fc; }
  .header .badge { background: #21262d; border: 1px solid #30363d;
                   padding: 3px 10px; border-radius: 20px; font-size: 11px; color: #8b949e; }
  .back { color: #58a6ff; text-decoration: none; font-size: 13px; }
  .back:hover { text-decoration: underline; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          padding: 20px; margin-bottom: 16px; }
  .form-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
  input, select { background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
                  color: #e6edf3; padding: 9px 14px; font-size: 14px; outline: none; }
  input:focus, select:focus { border-color: #58a6ff; }
  input[type=text] { flex: 1; min-width: 220px; }
  button { background: #238636; color: #fff; border: none; border-radius: 6px;
           padding: 9px 20px; font-size: 14px; font-weight: 600; cursor: pointer;
           white-space: nowrap; }
  button:hover { background: #2ea043; }
  button:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
  .agents { display: flex; gap-10px; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .agent-chip { background: #21262d; border: 1px solid #30363d; border-radius: 20px;
                padding: 4px 12px; font-size: 12px; display: flex; align-items: center; gap: 6px; }
  .agent-chip.active { border-color: #58a6ff; color: #58a6ff; }
  .agent-chip.done   { border-color: #3fb950; color: #3fb950; }
  .log { background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
         padding: 12px; font-size: 12px; font-family: monospace; max-height: 220px;
         overflow-y: auto; margin-top: 12px; }
  .log-line { padding: 2px 0; border-bottom: 1px solid #161b22; color: #8b949e; }
  .log-line.highlight { color: #e6edf3; }
  .repos-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
  .repo-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 14px; }
  .repo-name { font-weight: 600; color: #58a6ff; font-size: 14px; margin-bottom: 6px; }
  .repo-desc { font-size: 12px; color: #8b949e; margin-bottom: 8px; line-height: 1.5; }
  .repo-meta { display: flex; gap: 10px; font-size: 11px; color: #8b949e; }
  .star { color: #d29922; }
  .contributors-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .contributors-table th { text-align: left; padding: 10px 12px;
                            border-bottom: 1px solid #30363d; color: #8b949e; font-weight: 600; font-size: 11px; text-transform: uppercase; }
  .contributors-table td { padding: 10px 12px; border-bottom: 1px solid #21262d; vertical-align: top; }
  .contributors-table tr:hover td { background: #161b22; }
  .username { font-weight: 600; color: #58a6ff; }
  .tier { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .tier-core     { background: rgba(63,185,80,0.15); color: #3fb950; }
  .tier-active   { background: rgba(88,166,255,0.15); color: #58a6ff; }
  .tier-emerging { background: rgba(210,153,34,0.15); color: #d29922; }
  .score-bar { width: 60px; height: 6px; background: #21262d; border-radius: 3px; margin-top: 4px; }
  .score-fill { height: 100%; border-radius: 3px; background: #58a6ff; }
  .hidden { display: none; }
  label { font-size: 12px; color: #8b949e; display: block; margin-bottom: 4px; }
  .tool-chip { background: #21262d; border: 1px solid #30363d; border-radius: 20px;
               padding: 4px 12px; font-size: 12px; color: #8b949e; cursor: pointer;
               transition: all .15s; user-select: none; }
  .tool-chip:hover { border-color: #58a6ff; color: #58a6ff; background: rgba(88,166,255,0.08); }
  .tool-chip.active { border-color: #3fb950; color: #3fb950; background: rgba(63,185,80,0.1); }
  .contributors-table tbody tr { cursor: pointer; }
  .contributors-table tbody tr.selected td { background: #1c2128; }
  /* Profile drawer */
  .drawer-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:99; }
  .drawer-overlay.open { display:block; }
  .profile-drawer { position:fixed; top:0; right:-440px; width:420px; height:100vh;
                    background:#161b22; border-left:1px solid #30363d; z-index:100;
                    overflow-y:auto; transition:right 0.25s ease; padding:24px; box-sizing:border-box; }
  .profile-drawer.open { right:0; }
  .drawer-close { position:absolute; top:16px; right:16px; background:none; border:none;
                  color:#8b949e; font-size:20px; cursor:pointer; padding:4px 8px; }
  .drawer-close:hover { color:#e6edf3; background:none; }
  .drawer-avatar { width:64px; height:64px; border-radius:50%; border:2px solid #30363d; }
  .drawer-name { font-size:18px; font-weight:700; margin:12px 0 2px; }
  .drawer-handle { color:#58a6ff; font-size:13px; margin-bottom:12px; }
  .drawer-section { margin-top:18px; }
  .drawer-section-title { font-size:11px; font-weight:600; text-transform:uppercase;
                           color:#8b949e; letter-spacing:.08em; margin-bottom:8px;
                           padding-bottom:6px; border-bottom:1px solid #21262d; }
  .drawer-meta { display:flex; flex-direction:column; gap:6px; font-size:13px; color:#8b949e; }
  .drawer-meta span { display:flex; align-items:center; gap:8px; }
  .drawer-meta strong { color:#e6edf3; }
  .drawer-bio { font-size:13px; color:#c9d1d9; line-height:1.6; }
  .drawer-tag { display:inline-block; background:#21262d; border:1px solid #30363d;
                border-radius:20px; padding:3px 10px; font-size:11px; color:#8b949e;
                margin:3px 2px; }
  .drawer-repo { background:#0d1117; border:1px solid #21262d; border-radius:6px;
                 padding:8px 12px; font-size:12px; margin-bottom:6px; }
  .drawer-summary { font-size:13px; color:#c9d1d9; line-height:1.6;
                    background:#0d1117; border-radius:6px; padding:12px; border:1px solid #21262d; }
  .drawer-score { display:flex; align-items:center; gap:12px; }
  .drawer-score-num { font-size:28px; font-weight:700; color:#58a6ff; }
  .drawer-score-bar { flex:1; height:8px; background:#21262d; border-radius:4px; overflow:hidden; }
  .drawer-score-fill { height:100%; border-radius:4px; background:linear-gradient(90deg,#1f6feb,#58a6ff); }
  .email-btn { display:inline-flex; align-items:center; gap:6px; background:rgba(88,166,255,0.1);
               border:1px solid rgba(88,166,255,0.3); border-radius:6px; padding:7px 14px;
               color:#58a6ff; font-size:13px; text-decoration:none; margin-top:4px; }
  .email-btn:hover { background:rgba(88,166,255,0.2); }
  .gh-btn { display:inline-flex; align-items:center; gap:6px; background:#21262d;
            border:1px solid #30363d; border-radius:6px; padding:7px 14px;
            color:#e6edf3; font-size:13px; text-decoration:none; margin-top:4px; margin-left:8px; }
  .gh-btn:hover { border-color:#58a6ff; }
</style>
</head>
<body>
<div class="header">
  <a href="/" class="back">← Batman</a>
  <h1>🛡️ GitHub Radar</h1>
  <span class="badge">Cybersecurity Contributors</span>
</div>

<div class="card">
  <div style="margin-bottom:12px">
    <label style="margin-bottom:6px">Popular tools</label>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">
      <span class="tool-chip" onclick="setKeyword('OWASP ZAP')">OWASP ZAP</span>
      <span class="tool-chip" onclick="setKeyword('nuclei')">Nuclei</span>
      <span class="tool-chip" onclick="setKeyword('metasploit')">Metasploit</span>
      <span class="tool-chip" onclick="setKeyword('nmap')">Nmap</span>
      <span class="tool-chip" onclick="setKeyword('burp suite')">Burp Suite</span>
      <span class="tool-chip" onclick="setKeyword('trivy')">Trivy</span>
      <span class="tool-chip" onclick="setKeyword('falco')">Falco</span>
      <span class="tool-chip" onclick="setKeyword('osquery')">osquery</span>
      <span class="tool-chip" onclick="setKeyword('semgrep')">Semgrep</span>
      <span class="tool-chip" onclick="setKeyword('snyk')">Snyk</span>
      <span class="tool-chip" onclick="setKeyword('wazuh SIEM')">Wazuh</span>
      <span class="tool-chip" onclick="setKeyword('openvas vulnerability scanner')">OpenVAS</span>
      <span class="tool-chip" onclick="setKeyword('wireshark')">Wireshark</span>
      <span class="tool-chip" onclick="setKeyword('suricata IDS')">Suricata</span>
      <span class="tool-chip" onclick="setKeyword('mimikatz')">Mimikatz</span>
      <span class="tool-chip" onclick="setKeyword('gobuster')">Gobuster</span>
      <span class="tool-chip" onclick="setKeyword('sqlmap')">sqlmap</span>
      <span class="tool-chip" onclick="setKeyword('hashcat')">Hashcat</span>
    </div>
  </div>
  <div class="form-row">
    <div style="flex:1; min-width:220px">
      <label>Keyword / tool name</label>
      <input type="text" id="keyword" placeholder="OWASP ZAP, nuclei, SIEM..." value="OWASP ZAP" />
    </div>
    <div>
      <label>Repos to scan</label>
      <select id="maxRepos">
        <option value="3">3 repos</option>
        <option value="5" selected>5 repos</option>
        <option value="8">8 repos</option>
      </select>
    </div>
    <div>
      <label>Contributors / repo</label>
      <select id="maxContributors">
        <option value="5">5</option>
        <option value="8" selected>8</option>
        <option value="12">12</option>
      </select>
    </div>
    <button id="scanBtn" onclick="startScan()">🔍 Scan GitHub</button>
  </div>

  <div class="agents" id="agents">
    <div class="agent-chip" id="chip-browser">🌐 Browser</div>
    <div class="agent-chip" id="chip-search">🔍 Search</div>
    <div class="agent-chip" id="chip-contributors">👥 Contributors</div>
    <div class="agent-chip" id="chip-profiles">👤 Profiles</div>
    <div class="agent-chip" id="chip-analysis">🤖 Analysis</div>
  </div>
  <div class="log" id="log"><div class="log-line">Ready. Enter a keyword and click Scan.</div></div>
</div>

<div class="card hidden" id="reposSection">
  <h3 style="font-size:13px; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; margin-bottom:12px">
    📦 Top Repos
  </h3>
  <div class="repos-grid" id="reposGrid"></div>
</div>

<div class="card hidden" id="contributorsSection">
  <h3 style="font-size:13px; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; margin-bottom:12px">
    👥 Top Contributors
  </h3>
  <table class="contributors-table">
    <thead>
      <tr>
        <th>Contributor</th>
        <th>Tier</th>
        <th>Score</th>
        <th>Email</th>
        <th>Summary</th>
        <th>Repos</th>
      </tr>
    </thead>
    <tbody id="contributorsBody"></tbody>
  </table>
</div>

<!-- Profile Drawer -->
<div class="drawer-overlay" id="drawerOverlay" onclick="closeDrawer()"></div>
<div class="profile-drawer" id="profileDrawer">
  <button class="drawer-close" onclick="closeDrawer()">✕</button>
  <div id="drawerContent"></div>
</div>

<script>
let contributorsData = [];

function openDrawer(c) {
  const score = Math.min(100, c.activity_score || 0);
  const tier = c.tier || 'active';
  const tierColors = { core: '#3fb950', active: '#58a6ff', emerging: '#d29922' };
  const tc = tierColors[tier] || '#58a6ff';

  const focusTags = (c.focus_areas || []).map(f =>
    '<span class="drawer-tag">' + f + '</span>').join('');

  const reposHtml = (c.repos_contributed || []).map(r =>
    '<div class="drawer-repo">📦 ' + r + '</div>').join('');

  const pinned = (c.pinned_repos || []).map(r =>
    '<div class="drawer-repo">📌 ' + r + '</div>').join('');

  const orgs = (c.orgs || []).map(o =>
    '<span class="drawer-tag">🏢 ' + o + '</span>').join('');

  document.getElementById('drawerContent').innerHTML = \`
    <img class="drawer-avatar" src="https://github.com/\${c.username}.png?size=128" onerror="this.src='https://github.com/ghost.png'">
    <div class="drawer-name">\${c.name || c.username}</div>
    <div class="drawer-handle">@\${c.username} &nbsp;·&nbsp; <span style="color:\${tc};background:rgba(88,166,255,0.1);padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600">\${tier}</span></div>

    <div style="margin-top:10px">
      <a href="\${c.profile_url}" target="_blank" class="gh-btn">🐙 GitHub Profile</a>
      \${c.email ? '<a href="mailto:' + c.email + '" class="email-btn">✉️ ' + c.email + '</a>' : ''}
    </div>

    <div class="drawer-section">
      <div class="drawer-section-title">Activity Score</div>
      <div class="drawer-score">
        <div class="drawer-score-num">\${score}</div>
        <div class="drawer-score-bar"><div class="drawer-score-fill" style="width:\${score}%"></div></div>
        <div style="font-size:12px;color:#8b949e">/100</div>
      </div>
    </div>

    \${c.bio ? \`<div class="drawer-section">
      <div class="drawer-section-title">Bio</div>
      <div class="drawer-bio">\${c.bio}</div>
    </div>\` : ''}

    \${c.summary ? \`<div class="drawer-section">
      <div class="drawer-section-title">AI Summary</div>
      <div class="drawer-summary">\${c.summary}</div>
    </div>\` : ''}

    <div class="drawer-section">
      <div class="drawer-section-title">Details</div>
      <div class="drawer-meta">
        \${c.company ? '<span>🏢 <strong>' + c.company + '</strong></span>' : ''}
        \${c.location ? '<span>📍 <strong>' + c.location + '</strong></span>' : ''}
        \${c.commits ? '<span>💻 <strong>' + c.commits + ' commits</strong> across scanned repos</span>' : ''}
      </div>
    </div>

    \${focusTags ? \`<div class="drawer-section">
      <div class="drawer-section-title">Focus Areas</div>
      <div>\${focusTags}</div>
    </div>\` : ''}

    \${reposHtml ? \`<div class="drawer-section">
      <div class="drawer-section-title">Contributed To</div>
      \${reposHtml}
    </div>\` : ''}

    \${pinned ? \`<div class="drawer-section">
      <div class="drawer-section-title">Pinned Repos</div>
      \${pinned}
    </div>\` : ''}

    \${orgs ? \`<div class="drawer-section">
      <div class="drawer-section-title">Organizations</div>
      <div>\${orgs}</div>
    </div>\` : ''}
  \`;

  document.getElementById('profileDrawer').classList.add('open');
  document.getElementById('drawerOverlay').classList.add('open');
}

function closeDrawer() {
  document.getElementById('profileDrawer').classList.remove('open');
  document.getElementById('drawerOverlay').classList.remove('open');
  document.querySelectorAll('.contributors-table tbody tr.selected').forEach(r => r.classList.remove('selected'));
}

function setKeyword(kw) {
  document.getElementById('keyword').value = kw;
  document.querySelectorAll('.tool-chip').forEach(c => c.classList.remove('active'));
  event.target.classList.add('active');
}

function log(msg, highlight=false) {
  const el = document.getElementById('log');
  const line = document.createElement('div');
  line.className = 'log-line' + (highlight ? ' highlight' : '');
  line.textContent = new Date().toLocaleTimeString() + '  ' + msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function setChip(id, state) {
  const el = document.getElementById('chip-' + id);
  if (!el) return;
  el.className = 'agent-chip ' + state;
}

function startScan() {
  const keyword = document.getElementById('keyword').value.trim();
  if (!keyword) return;
  const maxRepos = document.getElementById('maxRepos').value;
  const maxContributors = document.getElementById('maxContributors').value;

  document.getElementById('scanBtn').disabled = true;
  document.getElementById('reposSection').classList.add('hidden');
  document.getElementById('contributorsSection').classList.add('hidden');
  document.getElementById('reposGrid').innerHTML = '';
  document.getElementById('contributorsBody').innerHTML = '';
  document.getElementById('log').innerHTML = '';

  ['browser','search','contributors','profiles','analysis'].forEach(c => setChip(c, ''));

  log('Starting GitHub Radar scan for: ' + keyword, true);

  const es = new EventSource('/api/github/stream?keyword=' + encodeURIComponent(keyword) +
    '&max_repos=' + maxRepos + '&max_contributors=' + maxContributors);

  es.onmessage = function(e) {
    try {
      const msg = JSON.parse(e.data);
      const type = msg.type || '';
      const text = msg.message || '';
      const data = msg.data || {};

      log(text, ['repos_found','contributors_found','complete'].includes(type));

      if (type === 'agent' && text.includes('Browserbase')) setChip('browser', 'active');
      if (type === 'agent' && text.includes('connected'))   setChip('browser', 'done');
      if (type === 'scanning_repo')                          setChip('search', 'active');
      if (type === 'repos_found')                            setChip('search', 'done');
      if (type === 'contributors_found')                     setChip('contributors', 'active');
      if (type === 'profiling')                              setChip('profiles', 'active');
      if (type === 'profile_done')                           setChip('profiles', 'active');
      if (type === 'analyzing')                              setChip('analysis', 'active');
      if (type === 'scored')                                 setChip('analysis', 'active');

      if (type === 'repo_detail' && data.repo) {
        document.getElementById('reposSection').classList.remove('hidden');
        const grid = document.getElementById('reposGrid');
        const card = document.createElement('div');
        card.className = 'repo-card';
        card.innerHTML = '<div class="repo-name"><a href="https://github.com/' + data.repo +
          '" target="_blank" style="color:inherit">' + data.repo + '</a></div>' +
          '<div class="repo-desc">' + (data.description || '—') + '</div>' +
          '<div class="repo-meta"><span class="star">⭐ ' + (data.stars||0).toLocaleString() + '</span></div>';
        grid.appendChild(card);
      }

      if (type === 'complete' && data.top_contributors) {
        setChip('analysis', 'done');
        contributorsData = data.top_contributors;
        document.getElementById('contributorsSection').classList.remove('hidden');
        const tbody = document.getElementById('contributorsBody');
        tbody.innerHTML = '';
        data.top_contributors.forEach((c, idx) => {
          const tier = c.tier || 'active';
          const score = Math.min(100, c.activity_score || 0);
          const tr = document.createElement('tr');
          tr.title = 'Click to view profile';
          tr.onclick = function() {
            document.querySelectorAll('.contributors-table tbody tr.selected').forEach(r => r.classList.remove('selected'));
            tr.classList.add('selected');
            openDrawer(c);
          };
          tr.innerHTML =
            '<td><span class="username">@' + c.username + '</span>' +
              (c.company ? '<br><small style="color:#8b949e">' + c.company + '</small>' : '') + '</td>' +
            '<td><span class="tier tier-' + tier + '">' + tier + '</span></td>' +
            '<td><div style="font-weight:600">' + score + '</div>' +
              '<div class="score-bar"><div class="score-fill" style="width:' + score + '%"></div></div></td>' +
            '<td style="font-size:12px">' + (c.email ? '<span style="color:#58a6ff">✉️ ' + c.email + '</span>' : '<span style="color:#484f58">—</span>') + '</td>' +
            '<td style="color:#8b949e;font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (c.summary || c.bio || '—') + '</td>' +
            '<td style="font-size:12px;color:#8b949e">' + (c.repos_contributed || []).join('<br>') + '</td>';
          tbody.appendChild(tr);
        });
        document.getElementById('scanBtn').disabled = false;
        es.close();
      }

      if (type === 'error') {
        log('❌ ' + text, true);
        document.getElementById('scanBtn').disabled = false;
        es.close();
      }
    } catch(err) { console.error(err); }
  };

  es.onerror = function() {
    log('Connection closed');
    document.getElementById('scanBtn').disabled = false;
    es.close();
  };
}
</script>
</body>
</html>
"""


@app.route("/github")
def github_radar():
    return render_template_string(GITHUB_RADAR_HTML)


@app.route("/api/github/stream")
def github_stream():
    keyword = request.args.get("keyword", "vulnerability scanner")
    max_repos = int(request.args.get("max_repos", 5))
    max_contributors = int(request.args.get("max_contributors", 8))

    q = queue.Queue()

    def yield_event(type_, message, data=None):
        payload = {"type": type_, "message": message, "data": data or {}}
        q.put(json.dumps(payload))

    def run_crawler():
        from github_crawler import GitHubRadarAgent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent = GitHubRadarAgent(
                keyword=keyword,
                max_repos=max_repos,
                max_contributors=max_contributors,
            )
            loop.run_until_complete(agent.run(yield_event=yield_event))
        except Exception as e:
            yield_event("error", str(e))
        finally:
            q.put(None)  # sentinel
            loop.close()

    thread = threading.Thread(target=run_crawler, daemon=True)
    thread.start()

    def generate():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"\n🤖 AI Visibility Audit Agent")
    print(f"   http://localhost:{port}")
    print(f"   Browserbase: {'✅' if os.environ.get('BROWSERBASE_API_KEY') else '❌'}")
    print(f"   OpenAI: {'✅' if os.environ.get('OPENAI_API_KEY') else '❌'}")
    app.run(host="0.0.0.0", port=port, debug=True)
