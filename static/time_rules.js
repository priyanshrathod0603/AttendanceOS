(() => {
  "use strict";
  const scope = location.pathname.endsWith("/teacher") ? "teacher" : "student";
  const labels = scope === "teacher" ? {
    office_start: "Office Start Time", late_grace_time: "Late Grace Time",
    half_day_time: "Half Day Time", absent_after_time: "Absent After Time",
    office_end: "Office End Time", out_start: "OUT Detection Start Time",
    min_working_hours: "Minimum Working Hours (minutes)",
    max_break_minutes: "Maximum Break Time (minutes)",
    max_late_per_month: "Maximum Late Per Month", overtime_start: "Overtime Start Time",
    early_exit_time: "Early Exit Time",
  } : {
    office_start: "School Start Time", late_grace_time: "Late Time",
    half_day_time: "Half Day Time", absent_after_time: "Absent Time",
    office_end: "School End Time", out_start: "OUT Detection Start Time",
  };
  const toggles = scope === "teacher" ? {
    enable_in: "Enable IN Detection", enable_out: "Enable OUT Detection",
    enable_working_hours: "Enable Working Hours", enable_overtime: "Enable Overtime",
    enable_early_exit: "Enable Early Exit", enable_multi_entry: "Enable Multiple Entry Detection",
    enable_unknown_alert: "Enable Unknown Face Alert", enable_notifications: "Enable Notifications",
  } : {
    enable_out: "Enable OUT Detection", enable_working_hours: "Enable Working Hours",
    enable_parent_notifications: "Enable Parent Notifications", enable_late_alert: "Enable Late Alert",
    enable_half_day: "Enable Half Day",
  };
  let rules = null;
  const e = window.escapeHtml || ((v) => String(v));
  const request = window.j;

  function refreshIcons() { if (window.lucide) lucide.createIcons(); }
  async function save(changes, message = "Rules saved") {
    try {
      rules = await request(`/api/time-rules/${scope}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...changes, reason: "Updated from time rules" }),
      });
      render();
      window.showResult({ title: "Saved", ok: true, message });
    } catch (err) { window.showResult({ title: "Save failed", ok: false, message: err.message }); }
  }
  function editField(key, label) {
    const isNumber = ["min_working_hours", "max_break_minutes", "max_late_per_month"].includes(key);
    window.openFormModal({ title: `Edit ${label}`, fields: [{ name: key, label, type: isNumber ? "number" : "time", required: true }], initial: rules,
      onSave: (values) => save({ [key]: isNumber ? Number(values[key]) : values[key] }) });
  }
  function render() {
    document.querySelector("#rules-updated").textContent = rules.updated_at ? `Last updated ${new Date(rules.updated_at).toLocaleString()}` : "";
    document.querySelector("#time-rows").innerHTML = Object.entries(labels).map(([key, label]) => `
      <div class="rule-row"><div><strong>${e(label)}</strong><div class="muted small">${e(rules[key] ?? "—")}</div></div>
      <button class="btn-secondary edit-rule" data-key="${key}" data-label="${e(label)}"><i data-lucide="pencil"></i>Edit</button></div>`).join("");
    document.querySelectorAll(".edit-rule").forEach((b) => b.onclick = () => editField(b.dataset.key, b.dataset.label));
    const off = String(rules.weekly_off || "").split(",");
    document.querySelector("#weekly-off").innerHTML = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, i) =>
      `<label><input type="checkbox" value="${i}" ${off.includes(String(i)) ? "checked" : ""}> ${day}</label>`).join("") +
      '<button class="btn-primary" id="save-weekly-off">Save</button><button class="btn-secondary" id="reset-rules">Reset all</button>';
    document.querySelector("#save-weekly-off").onclick = () => save({ weekly_off: [...document.querySelectorAll("#weekly-off input:checked")].map(x => x.value).join(",") });
    document.querySelector("#reset-rules").onclick = async () => {
      if (!confirm("Reset this scope to its default rules?")) return;
      try { rules = await request(`/api/time-rules/${scope}/reset`, { method: "POST" }); render(); } catch (err) { window.showResult({ title: "Reset failed", ok: false, message: err.message }); }
    };
    document.querySelector("#toggle-rows").innerHTML = Object.entries(toggles).map(([key, label]) => `
      <div class="rule-row"><strong>${e(label)}</strong><label class="switch"><input type="checkbox" data-toggle="${key}" ${rules[key] ? "checked" : ""}><span></span></label></div>`).join("");
    document.querySelectorAll("[data-toggle]").forEach((input) => input.onchange = () => save({ [input.dataset.toggle]: input.checked }));
    refreshIcons(); loadHolidays(); loadAudit();
  }
  async function loadHolidays() {
    const rows = await request(`/api/holidays?scope=${scope}`);
    document.querySelector("#holiday-table tbody").innerHTML = rows.length ? rows.map(h => `<tr><td>${e(h.holiday_date)}</td><td>${e(h.name)}</td><td>${e(h.kind)}</td><td>${e(h.scope)}</td><td><button class="btn-danger delete-holiday" data-id="${h.id}">Delete</button></td></tr>`).join("") : '<tr><td colspan="5" class="empty">No holidays configured.</td></tr>';
    document.querySelectorAll(".delete-holiday").forEach(b => b.onclick = async () => { if (confirm("Delete this holiday?")) { await request(`/api/holidays/${b.dataset.id}`, { method: "DELETE" }); loadHolidays(); loadAudit(); } });
  }
  async function loadAudit() {
    const rows = (await request("/api/audit-log?entity_type=rule")).slice(0, 50);
    document.querySelector("#audit-table tbody").innerHTML = rows.length ? rows.map(r => `<tr><td>${new Date(r.edited_at).toLocaleString()}</td><td>${e(r.entity_type)}</td><td>${r.entity_id}</td><td>${e(r.field)}</td><td>${e(r.old_value || "—")}</td><td>${e(r.new_value || "—")}</td><td>${e(r.edited_by)}</td><td>${e(r.reason || "—")}</td></tr>`).join("") : '<tr><td colspan="8" class="empty">No audit entries yet.</td></tr>';
  }
  document.querySelector("#btn-add-holiday").onclick = () => window.openFormModal({ title: "Add Holiday", fields: [
    { name: "holiday_date", label: "Date", type: "date", required: true }, { name: "name", label: "Holiday name", required: true },
    { name: "kind", label: "Type", type: "select", options: [{v:"national",t:"National"},{v:"school",t:"School"},{v:"emergency",t:"Emergency"}] },
  ], onSave: async values => { await request("/api/holidays", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({...values, scope}) }); loadHolidays(); loadAudit(); } });
  request(`/api/time-rules/${scope}`).then((data) => { rules = data; render(); }).catch((err) => window.showResult({ title: "Could not load rules", ok: false, message: err.message }));
})();
