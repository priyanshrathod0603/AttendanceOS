(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = window.escapeHtml || ((v) => String(v ?? ""));
  const fields = ["type", "date", "person-type", "class", "section", "department", "designation", "search"];
  const params = () => {
    const p = new URLSearchParams({ type: $("#report-type").value, date: $("#report-date").value });
    [["person_type", "#report-person-type"], ["class_name", "#report-class"], ["section", "#report-section"], ["department", "#report-department"], ["designation", "#report-designation"], ["q", "#report-search"]].forEach(([key, id]) => {
      if ($(id).value.trim()) p.set(key, $(id).value.trim());
    });
    return p;
  };
  const renderSummary = (s = {}) => ["total_records", "present", "late", "half_day", "absent", "early_exit", "overtime"].forEach((key) => {
    const el = $("#report-" + key); if (el) el.textContent = s[key] ?? 0;
  });
  async function generate() {
    const out = await window.j(`/api/reports/preview?${params()}`);
    $("#report-title").textContent = out.title || "Report Preview";
    $("#report-count").textContent = out.rows.length ? `${out.rows.length} record${out.rows.length === 1 ? "" : "s"}` : "No attendance records found.";
    renderSummary(out.summary);
    $("#report-table thead").innerHTML = `<tr>${out.headers.map((h) => `<th>${esc(h.replaceAll("_", " "))}</th>`).join("")}</tr>`;
    $("#report-table tbody").innerHTML = out.rows.length
      ? out.rows.map((r) => `<tr>${out.headers.map((h) => `<td>${esc(r[h] ?? "—")}</td>`).join("")}</tr>`).join("")
      : `<tr><td colspan="${Math.max(out.headers.length, 1)}" class="empty">No attendance records found.</td></tr>`;
  }
  $("#generate-report").addEventListener("click", () => generate().catch((err) => window.showResult({ title: "Report unavailable", ok: false, message: err.message })));
  $("#download-report").addEventListener("click", () => { const p = params(); p.set("format", $("#report-format").value); location.href = `/api/reports/export?${p}`; });
  $("#report-date").value = new Date().toISOString().slice(0, 10);
  fields.forEach((name) => { const el = name === "type" ? $("#report-type") : $("#report-" + name); if (el) el.addEventListener("change", generate); });
  generate().catch(() => renderSummary());
})();
