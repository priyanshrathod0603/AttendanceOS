/* =====================================================================
   FaceID School ERP -- per-page controllers
   Page detection: looks at <body data-page="..."> injected by the
   server-side template via @app.context_processor would be even nicer,
   but we infer the page from the active nav link for simplicity.
   ===================================================================== */
(() => {
  "use strict";

  const $ = window.$, $$ = window.$$;
  const j = window.j;
  const escapeHtml = window.escapeHtml;
  const openUploadModal = window.openUploadModal;
  const showResult = window.showResult;
  const openFormModal = window.openFormModal;
  const studentStatusBadge = window.studentStatusBadge;

  function cameraMetaHtml(c) {
    return `
      <span class="pill"><i data-lucide="map-pin"></i> ${escapeHtml(c.location || "Campus")}</span>
      <span class="pill"><i data-lucide="gauge"></i> FPS <b data-cam-fps="${c.id}">--</b></span>
      <span class="pill"><i data-lucide="eye"></i> Detected <b data-cam-detected="${c.id}">0</b></span>
      <span class="pill"><i data-lucide="user-check"></i> Recognized <b data-cam-recognized="${c.id}">0</b></span>
      <span class="pill"><i data-lucide="help-circle"></i> Unknown <b data-cam-unknown="${c.id}">0</b></span>
      <span class="pill"><i data-lucide="link"></i> ${escapeHtml(c.source)}</span>`;
  }

  async function refreshCameraStatus(root = document) {
    try {
      const statuses = await j("/api/cameras/status");
      Object.values(statuses).forEach((s) => {
        const set = (key, value) => {
          $$(`[data-cam-${key}="${s.camera_id}"]`, root).forEach((el) => { el.textContent = value; });
        };
        set("fps", s.fps);
        set("detected", s.detected_faces);
        set("recognized", s.recognized_faces);
        set("unknown", s.unknown_faces);
      });
    } catch { /* status is best-effort */ }
  }

  // ------------------------------------------------------ active page
  function activePage() {
    const a = $(".nav-item.active");
    if (!a) return "dashboard";
    if (a.textContent.includes("Dashboard")) return "dashboard";
    if (a.textContent.includes("Attendance")) return "attendance";
    if (a.textContent.includes("Students")) return "students";
    if (a.textContent.includes("Teachers")) return "teachers";
    if (a.textContent.includes("Cameras")) return "cameras";
    if (a.textContent.includes("Reports")) return "reports";
    if (a.textContent.includes("Settings")) return "settings";
    return "dashboard";
  }

  // ============================================================ DASHBOARD
  function initDashboard() {
    const camGrid = $("#cam-grid");
    const attendanceTbody = $("#attendance-table tbody");
    const unknownList = $("#unknown-list");
    const scopePill = $("#scope-pill");

    async function refreshStats() {
      try {
        const s = await j("/api/stats");
        $("#stat-total").textContent = s.total_students;
        $("#stat-present").textContent = s.present_today;
        $("#stat-absent").textContent = s.absent_today;
        $("#stat-unknown").textContent = s.unknown_today;
        $("#stat-cams").textContent = s.active_cameras;
        const label = s.class_name ? `${s.class_name}${s.section ? " " + s.section : ""}` : "All Classes";
        if (scopePill) scopePill.textContent = label;
      } catch (e) { /* noop */ }
    }

    async function refreshCams() {
      if (!camGrid) return;
      const cams = await j("/api/cameras");
      if (!cams.length) { camGrid.innerHTML = `<div class="empty">No cameras configured yet.</div>`; return; }
      camGrid.innerHTML = "";
      cams.forEach((c) => {
        const card = document.createElement("div");
        card.className = "cam-card";
        card.innerHTML = `
          <div class="cam-head">
            <div>
              <div class="cam-name">${escapeHtml(c.name)}</div>
              <div class="cam-loc">${escapeHtml(c.location || "")}</div>
            </div>
            <span class="badge ${c.is_active ? "ok" : "muted"}">${c.is_active ? "Active" : "Stopped"}</span>
          </div>
          <img class="cam-stream" src="/stream/${c.id}" alt="${escapeHtml(c.name)}" />
          <div class="cam-meta">
            ${cameraMetaHtml(c)}
          </div>
          <div class="cam-foot">
            <button class="btn-secondary" data-cam-action="start" data-id="${c.id}" ${c.is_active ? "disabled" : ""}>
              <i data-lucide="play"></i> Start
            </button>
            <button class="btn-secondary" data-cam-action="stop" data-id="${c.id}" ${c.is_active ? "" : "disabled"}>
              <i data-lucide="square"></i> Stop
            </button>
            <button class="btn-icon" data-cam-action="fullscreen" data-id="${c.id}" title="Fullscreen">
              <i data-lucide="maximize"></i>
            </button>
          </div>`;
        camGrid.appendChild(card);
      });
      if (window.lucide) lucide.createIcons();
      refreshCameraStatus(camGrid);
    }

    async function refreshAttendance() {
      const rows = await j("/api/attendance/today");
      attendanceTbody.innerHTML = "";
      if (!rows.length) {
        attendanceTbody.innerHTML = `<tr><td colspan="6" class="empty">No attendance recorded today.</td></tr>`;
        return;
      }
      rows.forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${new Date(r.timestamp).toLocaleTimeString()}</td>
          <td>${escapeHtml(r.student_name || "")}</td>
          <td>${escapeHtml(r.roll_no || "")}</td>
          <td>${escapeHtml(r.class_name || "")}</td>
          <td>${escapeHtml(r.camera_name || "")}</td>
          <td>${(r.confidence || 0).toFixed(2)}</td>`;
        attendanceTbody.appendChild(tr);
      });
    }

    async function refreshUnknown() {
      const rows = await j("/api/unknown-faces");
      const list = rows.slice(0, 10);
      if (!list.length) {
        unknownList.innerHTML = `<li class="empty">No unknown faces recorded.</li>`;
        return;
      }
      unknownList.innerHTML = list.map((r) => `
        <li>
          <span><i data-lucide="help-circle"></i> ${escapeHtml(r.camera_name || "Unknown")}</span>
          <span class="muted small">${new Date(r.timestamp).toLocaleString()}</span>
        </li>`).join("");
      if (window.lucide) lucide.createIcons();
    }

    camGrid && camGrid.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-cam-action]");
      if (!btn) return;
      const action = btn.dataset.camAction;
      const id = btn.dataset.id;
      if (action === "fullscreen") {
        const img = camGrid.querySelector(`.cam-stream`);
        if (img && img.requestFullscreen) img.requestFullscreen();
        return;
      }
      await fetch(`/api/cameras/${id}/${action}`, { method: "POST" });
      refreshCams();
      refreshStats();
    });

    refreshStats();
    refreshCams();
    refreshAttendance();
    refreshUnknown();
    setInterval(refreshStats, 8000);
    setInterval(refreshAttendance, 4000);
    setInterval(refreshUnknown, 10000);
    setInterval(() => refreshCameraStatus(camGrid), 3000);
  }

  // ============================================================ STUDENTS
  function initStudents() {
    const tbody = $("#students-table tbody");
    const countEl = $("#students-count");
    const titleEl = $("#students-title");
    const pager = $("#students-pager");
    const state = { class_name: "", section: "", search: "", page: 1, pageSize: 50 };

    // hydrate from URL (sidebar link)
    const path = window.location.pathname;
    const m = path.match(/^\/students\/class\/(.+)$/);
    if (m) {
      state.class_name = decodeURIComponent(m[1]);
      $("#filter-class").value = state.class_name;
    }

    async function refreshStats() {
      const params = new URLSearchParams();
      if (state.class_name) params.set("class_name", state.class_name);
      if (state.section) params.set("section", state.section);
      const s = await j(`/api/stats?${params.toString()}`);
      $("#stat-total").textContent = s.total_students;
      $("#stat-present").textContent = s.present_today;
      $("#stat-absent").textContent = s.absent_today;
      $("#stat-unknown").textContent = s.unknown_today;
      $("#stat-cams").textContent = s.active_cameras;
      $("#stat-scope").textContent = state.class_name
        ? `${state.class_name}${state.section ? " - " + state.section : ""}`
        : "All Classes";
    }

    async function load() {
      const params = new URLSearchParams();
      if (state.class_name) params.set("class_name", state.class_name);
      if (state.section) params.set("section", state.section);
      if (state.search) params.set("q", state.search);
      const rows = await j(`/api/students?${params.toString()}`);
      const total = rows.length;
      const start = (state.page - 1) * state.pageSize;
      const slice = rows.slice(start, start + state.pageSize);
      if (countEl) countEl.textContent = `${total} students`;
      if (titleEl) {
        titleEl.textContent = state.class_name
          ? `${state.class_name}${state.section ? " - " + state.section : ""} Students`
          : "All Students";
      }
      if (!slice.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty">No students found.</td></tr>`;
      } else {
        tbody.innerHTML = slice.map((s) => `
          <tr data-id="${s.id}">
            <td>${escapeHtml(s.roll_no)}</td>
            <td>${escapeHtml(s.name)}</td>
            <td>${s.id}</td>
            <td>${studentStatusBadge(s)}</td>
            <td>
              <button class="btn-primary" data-action="upload" data-id="${s.id}" data-name="${escapeHtml(s.name)}" title="Capture Face / Upload Photo">
                <i data-lucide="camera"></i> Face
              </button>
              <button class="btn-secondary" data-action="edit" data-id="${s.id}"><i data-lucide="edit"></i> Edit</button>
              <button class="btn-danger" data-action="delete" data-id="${s.id}"><i data-lucide="trash-2"></i> Delete</button>
            </td>
          </tr>`).join("");
      if (window.lucide) lucide.createIcons();
      }
      refreshStats();
      // pager
      const pages = Math.max(1, Math.ceil(total / state.pageSize));
      pager.innerHTML = "";
      for (let p = 1; p <= pages; p++) {
        const b = document.createElement("button");
        b.textContent = p;
        if (p === state.page) b.classList.add("active");
        b.addEventListener("click", () => { state.page = p; load(); });
        pager.appendChild(b);
      }
    }

    $("#filter-class").addEventListener("change", (e) => {
      state.class_name = e.target.value;
      state.page = 1;
      // Update URL so refreshing / sharing keeps the filter
      const url = state.class_name
        ? `/students/class/${encodeURIComponent(state.class_name)}`
        : `/students`;
      history.replaceState(null, "", url);
      load();
    });
    $("#filter-section").addEventListener("change", (e) => {
      state.section = e.target.value; state.page = 1; load();
    });
    let timer;
    $("#filter-search").addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.search = e.target.value; state.page = 1; load(); }, 200);
    });

    $("#btn-add-student").addEventListener("click", () => {
      const classes = window.__SCHOOL__ && window.__SCHOOL__.classes || [];
      const sections = (window.__SCHOOL__ && window.__SCHOOL__.sections) || ["A", "B", "C", "D"];
      openFormModal({
        title: "Add Student",
        fields: [
          { name: "student_id", label: "Student ID", value: "Auto-generated", readonly: true },
          { name: "roll_no", label: "Roll Number", required: true },
          { name: "name", label: "Student Name", required: true },
          { name: "class_name", label: "Class", type: "select", required: true, value: state.class_name || "",
            options: [{ v: "", t: "Select class..." }, ...classes.map((c) => ({ v: c, t: c }))] },
          { name: "section", label: "Section", type: "select", value: state.section || "",
            options: [{ v: "", t: "Select section..." }, ...sections.map((s) => ({ v: s, t: s }))] },
          { name: "mobile", label: "Mobile Number" },
          { name: "email", label: "Email", type: "email" },
        ],
        onSave: async (v) => {
          delete v.student_id;
          if (!v.class_name) {
            throw new Error("Please select a class.");
          }
          const created = await j("/api/students", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(v),
          });
          showResult({ title: "Student added", ok: true, message: `${created.name} added. Now register their face.` });
          load();
          openUploadModal(created.id, created.name);
        },
      });
    });

    tbody.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const id = btn.dataset.id;
      const action = btn.dataset.action;
      if (action === "upload") {
        openUploadModal(parseInt(id, 10), btn.dataset.name);
      } else if (action === "delete") {
        if (!confirm("Delete this student and their face encoding?")) return;
        try { await fetch(`/api/students/${id}`, { method: "DELETE" }); load(); }
        catch (err) { showResult({ title: "Delete failed", ok: false, message: err.message }); }
      } else if (action === "edit") {
        try {
          const rows = await j(`/api/students?q=${id}`);
          const s = rows.find((r) => r.id == id) || (await j(`/api/students`)).find((r) => r.id == id);
          if (!s) return;
          const classes = (window.__SCHOOL__ && window.__SCHOOL__.classes) || [];
          const sections = (window.__SCHOOL__ && window.__SCHOOL__.sections) || ["A","B","C","D"];
          openFormModal({
            title: `Edit ${s.name}`,
            initial: s,
            fields: [
              { name: "id", label: "Student ID", readonly: true },
              { name: "roll_no", label: "Roll Number", required: true },
              { name: "name", label: "Student Name", required: true },
              { name: "class_name", label: "Class", type: "select", required: true, options: classes.map((c) => ({ v: c, t: c })) },
              { name: "section", label: "Section", type: "select", options: sections.map((sec) => ({ v: sec, t: sec })) },
              { name: "mobile", label: "Mobile Number" },
              { name: "email", label: "Email", type: "email" },
              { name: "is_active", label: "Active", type: "select", options: [{v:"true",t:"Active"},{v:"false",t:"Inactive"}] },
            ],
            onSave: async (v) => {
              v.is_active = String(v.is_active).toLowerCase() === "true";
              delete v.id;
              await j(`/api/students/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v) });
              showResult({ title: "Student updated", ok: true, message: `${v.name} updated.` });
              load();
            },
          });
        } catch (err) { showResult({ title: "Edit failed", ok: false, message: err.message }); }
      }
    });

    // Re-render when a face is registered so the badge flips.
    window.addEventListener("face-registered", () => load());

    load();
  }

  // ============================================================ ATTENDANCE
  function initAttendance() {
    const tbody = $("#attendance-table tbody");
    const countEl = $("#attendance-count");
    const state = { class_name: "", section: "", date: new Date().toISOString().slice(0, 10), camera_id: "", search: "" };

    function isTodayRecord(timestamp) {
      if (!timestamp) return false;
      const d = new Date(timestamp);
      const now = new Date();
      return d.getFullYear() === now.getFullYear()
        && d.getMonth() === now.getMonth()
        && d.getDate() === now.getDate();
    }

    async function loadCams() {
      const sel = $("#filter-camera");
      const cams = await j("/api/cameras");
      cams.forEach((c) => {
        const o = document.createElement("option");
        o.value = c.id; o.textContent = c.name; sel.appendChild(o);
      });
    }
    $("#filter-date").value = state.date;

    async function load() {
      const params = new URLSearchParams();
      if (state.class_name) params.set("class_name", state.class_name);
      if (state.section) params.set("section", state.section);
      if (state.date) params.set("date", state.date);
      if (state.camera_id) params.set("camera_id", state.camera_id);
      if (state.search) params.set("q", state.search);
      const rows = await j(`/api/attendance?${params.toString()}`);
      if (countEl) countEl.textContent = `${rows.length} records`;
      if (!rows.length) { tbody.innerHTML = `<tr><td colspan="8" class="empty">No attendance for selected filters.</td></tr>`; return; }
      const q = state.search.toLowerCase();
      const filtered = q
        ? rows.filter((r) => (r.student_name || "").toLowerCase().includes(q) ||
                              (r.roll_no || "").toLowerCase().includes(q) ||
                              String(r.student_id || "").includes(q))
        : rows;
      tbody.innerHTML = filtered.map((r) => `
        <tr data-id="${r.id}">
          <td>${new Date(r.timestamp).toLocaleTimeString()}</td>
          <td>${escapeHtml(r.roll_no || "")}</td>
          <td>${escapeHtml(r.student_name || "")}</td>
          <td>${escapeHtml(r.class_name || "")}</td>
          <td>${escapeHtml(r.section || "")}</td>
          <td>${escapeHtml(r.camera_name || "")}</td>
          <td>${(r.confidence || 0).toFixed(2)}</td>
          <td>
            <button class="btn-secondary" data-action="edit" data-id="${r.id}" title="Edit attendance">
              <i data-lucide="edit"></i>
            </button>
            <button class="btn-danger" data-action="delete" data-id="${r.id}" title="Delete attendance">
              <i data-lucide="trash-2"></i>
            </button>
          </td>
        </tr>`).join("");
      if (window.lucide) lucide.createIcons();
    }

    function exportHref(fmt) {
      const params = new URLSearchParams();
      if (state.class_name) params.set("class_name", state.class_name);
      if (state.section) params.set("section", state.section);
      if (state.date) params.set("date", state.date);
      params.set("format", fmt);
      return `/api/attendance/export?${params.toString()}`;
    }

    $("#filter-class").addEventListener("change", (e) => { state.class_name = e.target.value; load(); });
    $("#filter-section").addEventListener("change", (e) => { state.section = e.target.value; load(); });
    $("#filter-date").addEventListener("change", (e) => { state.date = e.target.value; load(); });
    $("#filter-camera").addEventListener("change", (e) => { state.camera_id = e.target.value; load(); });
    $("#filter-search").addEventListener("input", (e) => { state.search = e.target.value; load(); });
    $("#btn-export-csv").addEventListener("click", () => { window.location.href = exportHref("csv"); });
    $("#btn-export-pdf").addEventListener("click", () => { window.location.href = exportHref("pdf"); });
    $("#btn-print").addEventListener("click", () => window.print());

    tbody.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const id = btn.dataset.id;
      const action = btn.dataset.action;
      const params = new URLSearchParams();
      if (state.class_name) params.set("class_name", state.class_name);
      if (state.section) params.set("section", state.section);
      if (state.date) params.set("date", state.date);
      if (state.camera_id) params.set("camera_id", state.camera_id);
      const rows = await j(`/api/attendance?${params.toString()}`);
      const record = rows.find((r) => String(r.id) === String(id));
      if (!record) return;

      if (action === "delete") {
        const today = isTodayRecord(record.timestamp);
        const msg = today
          ? `Delete attendance for ${record.student_name || record.roll_no}?`
          : `This record is from a previous date. Delete anyway?`;
        if (!confirm(msg)) return;
        try {
          const url = today
            ? `/api/attendance/${id}`
            : `/api/attendance/${id}?force=true`;
          await j(url, { method: "DELETE" });
          showResult({
            title: "Attendance removed",
            ok: true,
            message: `${record.student_name || record.roll_no} attendance deleted.`,
          });
          load();
        } catch (err) {
          showResult({ title: "Delete failed", ok: false, message: err.message });
        }
      } else if (action === "edit") {
        const today = isTodayRecord(record.timestamp);
        openFormModal({
          title: `Edit Attendance — ${record.student_name || record.roll_no}`,
          initial: {
            status: record.status || "present",
            confidence: (record.confidence || 0).toFixed(2),
            timestamp: record.timestamp ? record.timestamp.slice(0, 16) : "",
          },
          fields: [
            { name: "status", label: "Status", type: "select", required: true,
              options: [
                { v: "present", t: "Present" },
                { v: "absent", t: "Absent" },
                { v: "late", t: "Late" },
              ] },
            { name: "confidence", label: "Confidence", type: "number" },
            { name: "timestamp", label: "Timestamp (local)", type: "datetime-local" },
          ],
          onSave: async (v) => {
            const payload = {
              status: v.status,
              confidence: parseFloat(v.confidence || "0"),
            };
            if (v.timestamp) {
              payload.timestamp = new Date(v.timestamp).toISOString();
            }
            if (!today) payload.force = true;
            await j(`/api/attendance/${id}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            });
            showResult({
              title: "Attendance updated",
              ok: true,
              message: `${record.student_name || record.roll_no} attendance corrected.`,
            });
            load();
          },
        });
      }
    });

    loadCams();
    load();
  }

  // ============================================================ TEACHERS
  function initTeachers() {
    const tbody = $("#teachers-table tbody");
    const countEl = $("#teachers-count");
    let search = "";

    async function load() {
      const rows = await j("/api/teachers");
      const q = search.toLowerCase();
      const filtered = q
        ? rows.filter((r) =>
            (r.name || "").toLowerCase().includes(q) ||
            (r.teacher_id || "").toLowerCase().includes(q) ||
            (r.subject || "").toLowerCase().includes(q))
        : rows;
      if (countEl) countEl.textContent = `${filtered.length} teachers`;
      if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty">No teachers yet.</td></tr>`; return;
      }
      tbody.innerHTML = filtered.map((t) => `
        <tr>
          <td>${escapeHtml(t.teacher_id)}</td>
          <td>${escapeHtml(t.name)}</td>
          <td>${escapeHtml(t.subject || "")}</td>
          <td>${escapeHtml(t.assigned_classes || "")}</td>
          <td>${escapeHtml(t.mobile || "")}</td>
          <td>${escapeHtml(t.email || "")}</td>
          <td><span class="badge ${t.is_active ? "ok" : "muted"}">${t.is_active ? "Active" : "Inactive"}</span></td>
          <td>
            <button class="btn-secondary" data-action="edit" data-id="${t.id}"><i data-lucide="edit"></i></button>
            <button class="btn-danger" data-action="delete" data-id="${t.id}"><i data-lucide="trash-2"></i></button>
          </td>
        </tr>`).join("");
      if (window.lucide) lucide.createIcons();
    }

    let timer;
    $("#filter-search").addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => { search = e.target.value; load(); }, 200);
    });

    $("#btn-add-teacher").addEventListener("click", () => {
      openFormModal({
        title: "Add Teacher",
        fields: [
          { name: "teacher_id", label: "Teacher ID", required: true },
          { name: "name", label: "Name", required: true },
          { name: "subject", label: "Subject" },
          { name: "assigned_classes", label: "Assigned Classes (e.g. 5A, 6B)" },
          { name: "mobile", label: "Mobile" },
          { name: "email", label: "Email", type: "email" },
        ],
        onSave: async (v) => {
          await j("/api/teachers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v) });
          showResult({ title: "Teacher added", ok: true, message: `${v.name} added.` });
          load();
        },
      });
    });

    tbody.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const id = btn.dataset.id;
      if (btn.dataset.action === "delete") {
        if (!confirm("Delete this teacher?")) return;
        await fetch(`/api/teachers/${id}`, { method: "DELETE" });
        load();
      } else if (btn.dataset.action === "edit") {
        const t = (await j("/api/teachers")).find((r) => r.id == id);
        if (!t) return;
        openFormModal({
          title: `Edit ${t.name}`,
          initial: t,
          fields: [
            { name: "teacher_id", label: "Teacher ID", required: true },
            { name: "name", label: "Name", required: true },
            { name: "subject", label: "Subject" },
            { name: "assigned_classes", label: "Assigned Classes" },
            { name: "mobile", label: "Mobile" },
            { name: "email", label: "Email", type: "email" },
            { name: "is_active", label: "Status", type: "select", options: [{v:"true",t:"Active"},{v:"false",t:"Inactive"}] },
          ],
          onSave: async (v) => {
            v.is_active = String(v.is_active).toLowerCase() === "true";
            await j(`/api/teachers/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v) });
            showResult({ title: "Teacher updated", ok: true, message: `${v.name} saved.` });
            load();
          },
        });
      }
    });

    load();
  }

  // ============================================================ CAMERAS
  function initCameras() {
    const grid = $("#cam-grid");

    async function load() {
      const cams = await j("/api/cameras");
      if (!cams.length) { grid.innerHTML = `<div class="empty">No cameras yet. Add one to start.</div>`; return; }
      grid.innerHTML = cams.map((c) => `
        <div class="cam-card" data-id="${c.id}">
          <div class="cam-head">
            <div>
              <div class="cam-name">${escapeHtml(c.name)}</div>
              <div class="cam-loc">${escapeHtml(c.location || "")}</div>
            </div>
            <span class="badge ${c.is_active ? "ok" : "muted"}">${c.is_active ? "Active" : "Stopped"}</span>
          </div>
          <img class="cam-stream" src="/stream/${c.id}" alt="${escapeHtml(c.name)}" />
          <div class="cam-meta">
            ${cameraMetaHtml(c)}
          </div>
          <div class="cam-foot">
            <button class="btn-secondary" data-action="test" data-id="${c.id}"><i data-lucide="wifi"></i> Test</button>
            <button class="btn-secondary" data-action="edit" data-id="${c.id}"><i data-lucide="edit"></i> Edit</button>
            <button class="btn-danger" data-action="delete" data-id="${c.id}"><i data-lucide="trash-2"></i></button>
          </div>
        </div>`).join("");
      if (window.lucide) lucide.createIcons();
      refreshCameraStatus(grid);
    }

    $("#btn-add-camera").addEventListener("click", () => {
      openFormModal({
        title: "Add Camera",
        fields: [
          { name: "name", label: "Camera Name", required: true },
          { name: "source", label: "RTSP URL or 0 (webcam)", required: true },
          { name: "location", label: "Location" },
        ],
        onSave: async (v) => {
          await j("/api/cameras", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v) });
          showResult({ title: "Camera added", ok: true, message: `${v.name} added.` });
          load();
        },
      });
    });

    grid.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const id = btn.dataset.id;
      if (btn.dataset.action === "test") {
        const r = await j(`/api/cameras/${id}/test`, { method: "POST" });
        showResult({ title: r.ok ? "Reachable" : "Unreachable", ok: r.ok, message: r.message || r.source || "" });
      } else if (btn.dataset.action === "delete") {
        const cams = await j("/api/cameras");
        const cam = cams.find((r) => r.id == id);
        const msg = cam && cam.is_active
          ? "This camera is currently active. It will be stopped and deleted. Proceed?"
          : "Delete this camera?";
        if (!confirm(msg)) return;
        try {
          await j(`/api/cameras/${id}`, { method: "DELETE" });
          showResult({ title: "Camera deleted", ok: true, message: "Camera removed." });
          load();
        } catch (err) {
          showResult({ title: "Delete failed", ok: false, message: err.message });
        }
      } else if (btn.dataset.action === "edit") {
        const cams = await j("/api/cameras");
        const c = cams.find((r) => r.id == id);
        if (!c) return;
        openFormModal({
          title: `Edit ${c.name}`,
          initial: c,
          fields: [
            { name: "name", label: "Camera Name", required: true },
            { name: "source", label: "RTSP URL or 0", required: true },
            { name: "location", label: "Location" },
            { name: "is_active", label: "Status", type: "select", options: [{v:"true",t:"Active"},{v:"false",t:"Stopped"}] },
          ],
          onSave: async (v) => {
            v.is_active = String(v.is_active).toLowerCase() === "true";
            await j(`/api/cameras/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v) });
            showResult({ title: "Camera updated", ok: true, message: `${v.name} saved.` });
            load();
          },
        });
      }
    });

    load();
  }

  // ============================================================ SETTINGS
  function initSettings() {
    const t = $("#set-threshold");
    const tv = $("#set-threshold-value");
    if (t && tv) {
      t.addEventListener("input", () => { tv.textContent = t.value; });
    }
    // Populate school meta + system versions
    j("/api/meta").then((m) => {
      const nameEl = $("#set-school-name");
      if (nameEl) nameEl.value = m.school_name;
    }).catch(() => {});
    try {
      $("#sys-cv").textContent = "opencv";
      $("#sys-flask").textContent = "Flask";
      $("#sys-if").textContent = "insightface";
    } catch { /* noop */ }
  }

  // ============================================================ BOOTSTRAP
  document.addEventListener("DOMContentLoaded", async () => {
    // pre-load class/section lists for forms
    try {
      const meta = await j("/api/meta");
      window.__SCHOOL__ = { classes: meta.classes, sections: meta.sections };
    } catch { window.__SCHOOL__ = { classes: [], sections: [] }; }

    switch (activePage()) {
      case "dashboard":  initDashboard(); break;
      case "students":   initStudents(); break;
      case "attendance": initAttendance(); break;
      case "teachers":   initTeachers(); break;
      case "cameras":    initCameras(); break;
      case "settings":   initSettings(); break;
      default: /* noop */ break;
    }
  });
})();
