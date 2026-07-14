(() => {
  "use strict";
  const $ = window.$;
  const e = window.escapeHtml || ((v) => String(v));
  const mins = (n) => { n = Number(n || 0); return `${Math.floor(n / 60)}h ${n % 60}m`; };

  // Map summary field -> DOM id
  const idMap = {
    present: "ent-present",
    late: "ent-late",
    half_day: "ent-half",
    absent: "ent-absent",
    early_exit: "ent-early",
    overtime: "ent-ot",
    currently_inside: "ent-inside",
    currently_outside: "ent-outside",
    unknown_faces: "ent-unknown",
    active_cameras: "ent-cams",
    average_in_time: "ent-avg-in",
    average_out_time: "ent-avg-out",
    today_attendance_pct: "ent-attendance-pct",
  };

  function fmt(v, fallback = "—") {
    if (v === null || v === undefined || v === "") return fallback;
    return v;
  }

  async function loadSummary() {
    const s = await window.j("/api/enterprise/summary");
    Object.entries(idMap).forEach(([key, id]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = fmt(s[key], "—");
    });
    const dateEl = document.querySelector("#ent-date");
    if (dateEl) {
      dateEl.textContent = s.date + (s.is_holiday ? " • Holiday" : "");
    }
    const pctEl = document.getElementById("ent-attendance-pct-bar");
    if (pctEl) {
      const pct = Number(s.today_attendance_pct || 0);
      pctEl.style.width = `${Math.max(0, Math.min(100, pct))}%`;
    }
  }

  async function loadSessions() {
    const [students, teachers] = await Promise.all([
      window.j("/api/enterprise/attendance?type=student"),
      window.j("/api/enterprise/attendance?type=teacher"),
    ]);
    const rows = [...students, ...teachers];
    const tbody = document.querySelector("#ent-sessions-table tbody");
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty">No sessions today.</td></tr>';
    } else {
      tbody.innerHTML = rows.map((x) => `
        <tr>
          <td>${e(x.name || "—")}</td>
          <td>${e(([x.class_name, x.section].filter(Boolean).join(" ") || x.department || "—"))}</td>
          <td>${x.in_time ? new Date(x.in_time).toLocaleTimeString() : "—"}</td>
          <td>${x.out_time ? new Date(x.out_time).toLocaleTimeString() : "—"}</td>
          <td>${mins(x.working_minutes)}</td>
          <td>${mins(x.overtime_minutes)}</td>
          <td>${x.is_late ? '<span class="badge warn">Late</span>' : (x.status === "half_day" ? '<span class="badge warn">Half Day</span>' : (x.is_early_exit ? '<span class="badge err">Early Exit</span>' : (x.overtime_minutes > 0 ? '<span class="badge info">Overtime</span>' : '<span class="badge ok">OK</span>')))}</td>
          <td>${e((x.camera || "—"))}</td>
        </tr>`).join("");
    }
    if (window.lucide) lucide.createIcons();
  }

  async function loadWidgets() {
    try {
      const w = await window.j("/api/enterprise/widgets");

      // Trend
      const trend = w.trend || [];
      const trendEl = document.getElementById("ent-trend");
      if (trendEl) {
        trendEl.innerHTML = trend.length
          ? trend.map((t) => `
            <div class="trend-row">
              <span class="trend-date">${e(t.date.slice(5))}</span>
              <div class="trend-bar"><span style="width:${Math.min(100, t.pct)}%"></span></div>
              <span class="trend-pct">${t.pct}%</span>
            </div>`).join("")
          : '<div class="empty">No trend data.</div>';
      }

      // Hourly
      const hourly = w.hourly || [];
      const hourlyEl = document.getElementById("ent-hourly");
      if (hourlyEl) {
        const max = Math.max(1, ...hourly.map((h) => h.count));
        hourlyEl.innerHTML = hourly.map((h) => `
          <div class="hour-bar" title="${h.hour}:00 → ${h.count}">
            <span class="hour-fill" style="height:${(h.count / max) * 100}%"></span>
            <small>${h.hour}</small>
          </div>`).join("");
      }

      // Top late
      const topLate = w.top_late || [];
      const topLateEl = document.getElementById("ent-top-late");
      if (topLateEl) {
        topLateEl.innerHTML = topLate.length
          ? topLate.map((r) => `<li><span>${e(r.name || "—")}</span><b>${r.late_count}</b></li>`).join("")
          : '<li class="empty">No late records.</li>';
      }

      // Top overtime
      const topOT = w.top_overtime || [];
      const topOTEl = document.getElementById("ent-top-ot");
      if (topOTEl) {
        topOTEl.innerHTML = topOT.length
          ? topOT.map((r) => `<li><span>${e(r.name || "—")}</span><b>${mins(r.overtime_minutes)}</b></li>`).join("")
          : '<li class="empty">No overtime records.</li>';
      }

      // Top early exit
      const topEarly = w.top_early_exit || [];
      const topEarlyEl = document.getElementById("ent-top-early");
      if (topEarlyEl) {
        topEarlyEl.innerHTML = topEarly.length
          ? topEarly.map((r) => `<li><span>${e(r.name || "—")}</span><b>${e(r.out_time || "")}</b></li>`).join("")
          : '<li class="empty">No early exits.</li>';
      }

      // Working hours distribution
      const wh = w.working_hours || [];
      const whEl = document.getElementById("ent-wh");
      if (whEl) {
        const max = Math.max(1, ...wh.map((h) => h.count));
        whEl.innerHTML = wh.map((b) => `
          <div class="wh-row">
            <span>${e(b.range)}</span>
            <div class="trend-bar"><span style="width:${(b.count / max) * 100}%"></span></div>
            <b>${b.count}</b>
          </div>`).join("");
      }

      // Camera health
      const cam = w.camera_health || [];
      const camEl = document.getElementById("ent-cam-health");
      if (camEl) {
        camEl.innerHTML = cam.length
          ? cam.map((c) => `
            <div class="cam-pill ${c.is_active ? "" : "off"}">
              <i data-lucide="video"></i>
              <span>${e(c.name)}</span>
              <small>${c.events_today} events</small>
            </div>`).join("")
          : '<div class="empty">No cameras configured.</div>';
      }

      // Recognition
      const rec = w.recognition || {};
      const recEl = document.getElementById("ent-recog");
      if (recEl) {
        recEl.innerHTML = `
          <div class="recog-row"><span>Total recognitions</span><b>${rec.total_recognitions ?? 0}</b></div>
          <div class="recog-row"><span>Successful</span><b>${rec.successful ?? 0}</b></div>
          <div class="recog-row"><span>Success rate</span><b>${rec.success_rate ?? 0}%</b></div>
          <div class="recog-row"><span>Unknown faces</span><b>${rec.unknown_faces ?? 0}</b></div>`;
      }

      // Heatmap
      const heat = w.heatmap || { classes: [], dates: [], matrix: {} };
      const heatEl = document.getElementById("ent-heatmap");
      if (heatEl) {
        if (!heat.classes.length) {
          heatEl.innerHTML = '<div class="empty">No class data available.</div>';
        } else {
          const head = ['<th>Class</th>', ...heat.dates.map((d) => `<th>${e(d.slice(5))}</th>`)].join("");
          const body = heat.classes.map((cls) => {
            const row = heat.matrix[cls] || {};
            const cells = heat.dates.map((d) => {
              const pct = row[d] ?? 0;
              const intensity = Math.min(1, pct / 100);
              const bg = `rgba(0,122,255,${0.15 + intensity * 0.65})`;
              const color = intensity > 0.55 ? "#fff" : "#1d1d1f";
              return `<td style="background:${bg};color:${color};text-align:center;font-weight:600">${pct}%</td>`;
            }).join("");
            return `<tr><td><strong>${e(cls)}</strong></td>${cells}</tr>`;
          }).join("");
          heatEl.innerHTML = `<div class="table-scroll"><table class="heatmap"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
        }
      }

      // Activity feed
      const feed = w.activity_feed || [];
      const feedEl = document.getElementById("ent-feed");
      if (feedEl) {
        feedEl.innerHTML = feed.length
          ? feed.map((f) => `
            <li class="feed-item ${f.event_type}">
              <span class="dot"></span>
              <div>
                <strong>${e(f.person || f.type)}</strong>
                <small>${f.event_type.toUpperCase()} • ${f.event_time ? new Date(f.event_time).toLocaleTimeString() : "—"}</small>
              </div>
              <em>${Number(f.confidence || 0).toFixed(2)}</em>
            </li>`).join("")
          : '<li class="empty">No recent activity.</li>';
        if (window.lucide) lucide.createIcons();
      }
    } catch (err) {
      // widgets are best-effort
      console.warn("widgets failed", err);
    }
  }

  async function loadAll() {
    try {
      await Promise.all([loadSummary(), loadSessions(), loadWidgets()]);
    } catch (err) {
      window.showResult && window.showResult({ title: "Dashboard unavailable", ok: false, message: err.message });
    }
  }

  loadAll();
  setInterval(loadAll, 30000);
})();
