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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"\n🤖 AI Visibility Audit Agent")
    print(f"   http://localhost:{port}")
    print(f"   Browserbase: {'✅' if os.environ.get('BROWSERBASE_API_KEY') else '❌'}")
    print(f"   OpenAI: {'✅' if os.environ.get('OPENAI_API_KEY') else '❌'}")
    app.run(host="0.0.0.0", port=port, debug=True)
