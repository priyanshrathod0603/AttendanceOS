(() => {
  "use strict";
  const $ = (s) => document.querySelector(s), e = window.escapeHtml || String;
  const mins = (n) => `${Math.floor(Number(n || 0) / 60)}h ${Number(n || 0) % 60}m`;
  const time = (v) => v ? new Date(v).toLocaleTimeString() : "—";
  const yes = (v) => v ? '<span class="badge warn">Yes</span>' : "—";
  const headers = ["Type", "Roll / ID", "Name", "Class / Department", "Section / Designation", "IN", "OUT", "Working Hours", "Late", "Half Day", "Early Exit", "Overtime", "Break Time", "Status", "Camera", "Confidence", "Recognition Type"];
  function query() {
    const p = new URLSearchParams({ type: $("#filter-type").value, date: $("#filter-date").value });
    [["class_name", "#filter-class"], ["section", "#filter-section"], ["department", "#filter-department"], ["designation", "#filter-designation"], ["event_type", "#filter-event"], ["camera_id", "#filter-camera"], ["min_confidence", "#filter-min-confidence"], ["max_confidence", "#filter-max-confidence"], ["q", "#filter-search"]].forEach(([k, id]) => { if ($(id).value.trim()) p.set(k, $(id).value.trim()); });
    return p;
  }
  function row(r) {
    const ident = r.type === "student" ? r.roll_no : r.employee_id;
    const group = r.type === "student" ? r.class_name : r.department;
    const sub = r.type === "student" ? r.section : r.designation;
    return `<tr><td>${e(r.type)}</td><td>${e(ident || "—")}</td><td>${e(r.name || "—")}</td><td>${e(group || "—")}</td><td>${e(sub || "—")}</td><td>${time(r.in_time)}</td><td>${time(r.out_time)}</td><td>${mins(r.working_minutes)}</td><td>${yes(r.is_late)}</td><td>${yes(r.is_half_day)}</td><td>${yes(r.is_early_exit)}</td><td>${mins(r.overtime_minutes)}</td><td>${mins(r.break_minutes)}</td><td>${e(r.status || "—")}</td><td>${e(r.camera || "—")}</td><td>${r.confidence == null ? "—" : Number(r.confidence).toFixed(2)}</td><td>${e(r.recognition_type || "face")}</td></tr>`;
  }
  async function load() {
    const rows = await window.j(`/api/enterprise/sessions?${query()}`);
    const min = Number($("#filter-min-working").value || 0), maxRaw = $("#filter-max-working").value, max = maxRaw ? Number(maxRaw) : Infinity;
    const filtered = rows.filter((r) => Number(r.working_minutes || 0) >= min && Number(r.working_minutes || 0) <= max);
    $("#ext-count").textContent = `${filtered.length} record${filtered.length === 1 ? "" : "s"}`;
    $("#ext-head").innerHTML = headers.map((h) => `<th>${h}</th>`).join("");
    $("#ext-table tbody").innerHTML = filtered.length ? filtered.map(row).join("") : `<tr><td colspan="${headers.length}" class="empty">No attendance records found.</td></tr>`;
  }
  $("#filter-date").value = new Date().toISOString().slice(0, 10);
  document.querySelectorAll(".filters input, .filters select").forEach((el) => el.addEventListener(el.type === "search" ? "input" : "change", () => load().catch(console.error)));
  load().catch(console.error); setInterval(() => load().catch(console.error), 15000);
})();
