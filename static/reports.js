/* Reports page: simple bar-chart + table builder for each report type. */
(() => {
  "use strict";
  const $ = window.$, $$ = window.$$;
  const j = window.j;
  const escapeHtml = window.escapeHtml;

  const TITLES = {
    daily:   "Daily Attendance",
    monthly: "Monthly Attendance",
    class:   "Class-wise Attendance",
    student: "Student-wise Attendance",
    teacher: "Teacher-wise Roster",
    unknown: "Unknown Faces",
  };

  let currentType = null;

  async function renderDaily() {
    const rows = await j(`/api/attendance?date=${new Date().toISOString().slice(0,10)}`);
    const byClass = new Map();
    rows.forEach((r) => {
      const k = r.class_name || "Unassigned";
      byClass.set(k, (byClass.get(k) || 0) + 1);
    });
    return {
      title: TITLES.daily,
      chart: byClass,
      table: rows.slice(0, 200).map((r) => [new Date(r.timestamp).toLocaleString(), r.roll_no, r.student_name, r.class_name, r.camera_name, (r.confidence || 0).toFixed(2)]),
      headers: ["Time", "Roll", "Name", "Class", "Camera", "Conf"],
    };
  }
  async function renderMonthly() {
    // No month-bucketing endpoint yet, so we just return a placeholder.
    return {
      title: TITLES.monthly,
      chart: new Map(),
      table: [["Monthly aggregation is not yet wired; the daily view above covers live data."]],
      headers: ["Note"],
    };
  }
  async function renderClass() {
    const stats = await j(`/api/stats`);
    return {
      title: TITLES.class,
      chart: new Map([["Present", stats.present_today], ["Absent", stats.absent_today]]),
      table: [
        ["Total Students", stats.total_students],
        ["Present Today", stats.present_today],
        ["Absent Today", stats.absent_today],
        ["Unknown Faces", stats.unknown_today],
        ["Active Cameras", stats.active_cameras],
      ],
      headers: ["Metric", "Value"],
    };
  }
  async function renderStudent() {
    const rows = await j(`/api/attendance`);
    const byStudent = new Map();
    rows.forEach((r) => {
      const k = r.student_name || "(unknown)";
      byStudent.set(k, (byStudent.get(k) || 0) + 1);
    });
    const entries = Array.from(byStudent.entries()).sort((a, b) => b[1] - a[1]);
    return {
      title: TITLES.student,
      chart: new Map(entries.slice(0, 12)),
      table: entries.map(([k, v]) => [k, v]),
      headers: ["Student", "Marks"],
    };
  }
  async function renderTeacher() {
    const rows = await j(`/api/teachers`);
    return {
      title: TITLES.teacher,
      chart: new Map(),
      table: rows.map((t) => [t.teacher_id, t.name, t.subject, t.assigned_classes, t.mobile, t.email]),
      headers: ["ID", "Name", "Subject", "Classes", "Mobile", "Email"],
    };
  }
  async function renderUnknown() {
    const rows = await j(`/api/unknown-faces`);
    return {
      title: TITLES.unknown,
      chart: new Map(),
      table: rows.map((r) => [new Date(r.timestamp).toLocaleString(), r.camera_name, r.confidence ? r.confidence.toFixed(2) : ""]),
      headers: ["Time", "Camera", "Confidence"],
    };
  }

  function renderOutput(out) {
    $("#report-title").textContent = out.title;
    const chart = $("#report-chart");
    if (out.chart && out.chart.size) {
      const max = Math.max(...out.chart.values(), 1);
      chart.innerHTML = Array.from(out.chart.entries()).map(([k, v]) => {
        const h = Math.max(6, (v / max) * 180);
        return `<div>
          <div class="bar" style="height:${h}px" title="${escapeHtml(k)}: ${v}">${v}</div>
          <div class="bar-label">${escapeHtml(k)}</div>
        </div>`;
      }).join("");
    } else {
      chart.innerHTML = "";
    }
    const thead = $("#report-table thead");
    const tbody = $("#report-table tbody");
    thead.innerHTML = `<tr>${out.headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr>`;
    tbody.innerHTML = out.table.map((row) => `<tr>${row.map((c) => `<td>${escapeHtml(c)}</td>`).join("")}</tr>`).join("");
    $("#report-output").hidden = false;
  }

  async function run(type) {
    currentType = type;
    const fn = { daily: renderDaily, monthly: renderMonthly, class: renderClass,
                 student: renderStudent, teacher: renderTeacher, unknown: renderUnknown }[type];
    if (!fn) return;
    try {
      renderOutput(await fn());
    } catch (e) {
      $("#report-output").hidden = false;
      $("#report-title").textContent = TITLES[type] || "Report";
      $("#report-table tbody").innerHTML = `<tr><td class="empty">${escapeHtml(e.message)}</td></tr>`;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    $$(".report-card").forEach((b) => b.addEventListener("click", () => run(b.dataset.type)));
  });
})();
