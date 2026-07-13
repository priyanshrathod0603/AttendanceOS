/* =====================================================================
   FaceID School ERP -- common helpers
   - Sidebar collapse, modal helpers, status badge, fetch wrapper
   - Upload-photo modal logic (file / drag / webcam)
   - Per-page renderers are loaded by app.js / *.js after this file
   ===================================================================== */
(() => {
  "use strict";

  // ---------------------------------------------------------------- helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  window.$ = $;
  window.$$ = $$;

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  window.escapeHtml = escapeHtml;

  async function j(url, opts = {}) {
    const res = await fetch(url, opts);
    const text = await res.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
    if (!res.ok) {
      const err = new Error((body && body.error) || `HTTP ${res.status}`);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }
  window.j = j;

  // ---------------------------------------------------------- sidebar
  function initSidebar() {
    const body = document.body;
    const KEY = "faceid-sidebar-collapsed";
    if (localStorage.getItem(KEY) === "1") body.classList.add("sidebar-collapsed");
    const btn = $("#sidebar-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        if (window.matchMedia("(max-width: 768px)").matches) {
          body.classList.toggle("sidebar-open");
        } else {
          body.classList.toggle("sidebar-collapsed");
          localStorage.setItem(KEY, body.classList.contains("sidebar-collapsed") ? "1" : "0");
        }
      });
    }
    $$(".nav-accordion-trigger").forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const group = trigger.closest(".nav-accordion");
        if (group) group.classList.toggle("open");
      });
    });
  }

  // ---------------------------------------------------------- modal helpers
  function openModal(sel) {
    const m = $(sel);
    if (m) { m.classList.add("open"); m.setAttribute("aria-hidden", "false"); }
  }
  function closeModal(sel) {
    const m = $(sel);
    if (m) { m.classList.remove("open"); m.setAttribute("aria-hidden", "true"); }
  }
  window.openModal = openModal;
  window.closeModal = closeModal;

  document.addEventListener("click", (e) => {
    const t = e.target;
    if (t && t.dataset && t.dataset.close) {
      const m = t.closest(".modal");
      if (m) { m.classList.remove("open"); m.setAttribute("aria-hidden", "true"); }
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      $$(".modal.open").forEach((m) => { m.classList.remove("open"); m.setAttribute("aria-hidden", "true"); });
    }
  });

  // ---------------------------------------------------------- result dialog
  function showResult({ title, ok, message }) {
    $("#result-title").textContent = title;
    const body = $("#result-body");
    body.innerHTML = `
      <div class="big ${ok ? "ok" : "err"}">
        <span>${ok ? "&#10003;" : "&#10007;"}</span>
        <span>${escapeHtml(title)}</span>
      </div>
      <div>${escapeHtml(message)}</div>`;
    openModal("#result-dialog");
  }
  window.showResult = showResult;

  // ---------------------------------------------------------- form modal
  // Builds a form inside #form-modal-body and wires Save to onSave(values).
  function openFormModal({ title, fields, onSave, initial = {} }) {
    $("#form-modal-title").textContent = title;
    const body = $("#form-modal-body");
    body.innerHTML = "";
    fields.forEach((f) => {
      const row = document.createElement("div");
      row.className = "form-row";
      const id = `f-${f.name}`;
      const value = initial[f.name] ?? f.value ?? "";
      let inputHtml = "";
      if (f.type === "select") {
        const opts = (f.options || []).map(
          (o) => `<option value="${escapeHtml(o.v)}" ${String(value) === String(o.v) ? "selected" : ""}>${escapeHtml(o.t)}</option>`
        ).join("");
        inputHtml = `<select id="${id}" name="${f.name}" ${f.required ? "required" : ""}>${opts}</select>`;
      } else if (f.type === "textarea") {
        inputHtml = `<textarea id="${id}" name="${f.name}" ${f.required ? "required" : ""}>${escapeHtml(value)}</textarea>`;
      } else {
        inputHtml = `<input id="${id}" name="${f.name}" type="${f.type || "text"}"
                            value="${escapeHtml(value)}" ${f.required ? "required" : ""}
                            ${f.readonly ? "readonly" : ""}
                            ${f.disabled ? "disabled" : ""}
                            ${f.accept ? `accept="${f.accept}"` : ""} />`;
      }
      row.innerHTML = `<label for="${id}">${escapeHtml(f.label)}${f.required ? " *" : ""}</label>${inputHtml}`;
      body.appendChild(row);
    });
    const save = $("#form-modal-save");
    const handler = async () => {
      const missing = fields
        .filter((f) => f.required)
        .filter((f) => {
          const el = body.querySelector(`[name="${f.name}"]`);
          return !el || !String(el.value ?? "").trim();
        });
      if (missing.length) {
        showResult({
          title: "Missing required fields",
          ok: false,
          message: `Please fill: ${missing.map((f) => f.label).join(", ")}`,
        });
        return;
      }
      const values = {};
      fields.forEach((f) => {
        const el = body.querySelector(`[name="${f.name}"]`);
        if (el) values[f.name] = el.value;
      });
      try {
        await onSave(values);
        closeModal("#form-modal");
      } catch (err) {
        showResult({ title: "Save failed", ok: false, message: err.message });
      }
    };
    save.onclick = handler;
    openModal("#form-modal");
  }
  window.openFormModal = openFormModal;

  // ---------------------------------------------------------- status badge
  function studentStatusBadge(s, todayPresentSet) {
    if (s.has_encoding && todayPresentSet && todayPresentSet.has(s.id)) {
      return `<span class="badge ok">Attendance Marked</span>`;
    }
    if (s.has_encoding) {
      return `<span class="badge info">Face Registered</span>`;
    }
    if (!s.is_active) {
      return `<span class="badge muted">Inactive</span>`;
    }
    return `<span class="badge warn">Pending Registration</span>`;
  }
  window.studentStatusBadge = studentStatusBadge;

  // ---------------------------------------------------------- upload modal
  const Upload = {
    studentId: null,
    studentName: "",
    file: null,
    previewUrl: null,
    stream: null,
  };
  window.Upload = Upload;

  function switchTab(name) {
    $$(".tab", $("#upload-modal")).forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $$(".tab-panel", $("#upload-modal")).forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
    if (name !== "webcam") stopWebcam();
  }
  window.switchUploadTab = switchTab;

  function openUploadModal(studentId, studentName) {
    Upload.studentId = studentId;
    Upload.studentName = studentName || "";
    Upload.file = null;
    $("#upload-modal-title").textContent = `Register Face -- ${Upload.studentName}`;
    setPreview(null);
    setProgress(0, "Idle");
    $("#upload-submit").disabled = true;
    switchTab("file");
    stopWebcam();
    openModal("#upload-modal");
  }
  window.openUploadModal = openUploadModal;

  function closeUploadModal() {
    closeModal("#upload-modal");
    stopWebcam();
    if (Upload.previewUrl) URL.revokeObjectURL(Upload.previewUrl);
    Upload.previewUrl = null;
    Upload.file = null;
  }
  window.closeUploadModal = closeUploadModal;

  function setPreview(url) {
    if (Upload.previewUrl) URL.revokeObjectURL(Upload.previewUrl);
    Upload.previewUrl = url;
    const img = $("#preview-img");
    const empty = $("#preview-empty");
    if (url) {
      img.src = url; img.style.display = "block"; empty.style.display = "none";
      $("#upload-submit").disabled = false;
    } else {
      img.removeAttribute("src"); img.style.display = "none"; empty.style.display = "flex";
      $("#upload-submit").disabled = true;
    }
  }

  function setProgress(pct, label, mode = "") {
    const fill = $("#progress-fill");
    const text = $("#progress-text");
    fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
    fill.classList.remove("error", "done");
    if (mode === "error") fill.classList.add("error");
    if (mode === "done") fill.classList.add("done");
    text.textContent = label;
  }
  window.setUploadProgress = setProgress;

  function acceptFile(file) {
    if (!file) return;
    const okType = /^image\/(jpeg|jpg|png)$/.test(file.type) || /\.(jpe?g|png)$/i.test(file.name || "");
    if (!okType) {
      showResult({ title: "Unsupported file", ok: false, message: "Only .jpg, .jpeg or .png images are accepted." });
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      showResult({ title: "File too large", ok: false, message: `Image must be smaller than 8 MB (got ${(file.size / 1024 / 1024).toFixed(1)} MB).` });
      return;
    }
    Upload.file = file;
    setPreview(URL.createObjectURL(file));
    setProgress(0, "Ready to upload", "");
  }
  window.acceptFile = acceptFile;

  // webcam
  async function startWebcam() {
    try {
      Upload.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      });
      const v = $("#webcam");
      v.srcObject = Upload.stream;
      await v.play();
      $("#webcam-start").disabled = true;
      $("#webcam-capture").disabled = false;
      $("#webcam-retake").hidden = true;
      $("#webcam-hint").textContent = "Camera is on. Position the face inside the frame, then click Capture.";
    } catch (err) {
      $("#webcam-hint").textContent = `Could not open camera: ${err.message || err}`;
    }
  }
  function stopWebcam() {
    if (Upload.stream) { Upload.stream.getTracks().forEach((t) => t.stop()); Upload.stream = null; }
    const v = $("#webcam"); if (v) v.srcObject = null;
    const start = $("#webcam-start"), cap = $("#webcam-capture"), retake = $("#webcam-retake");
    if (start) start.disabled = false;
    if (cap) cap.disabled = true;
    if (retake) retake.hidden = true;
  }
  function captureFromWebcam() {
    const v = $("#webcam"), c = $("#snap");
    if (!v.videoWidth) return;
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    c.toBlob((blob) => {
      if (blob) {
        const f = new File([blob], "webcam-capture.jpg", { type: "image/jpeg" });
        acceptFile(f);
      }
    }, "image/jpeg", 0.92);
    $("#webcam-capture").disabled = true;
    $("#webcam-retake").hidden = false;
    stopWebcam();
  }
  function retake() {
    setPreview(null);
    $("#webcam-capture").disabled = false;
    $("#webcam-retake").hidden = true;
    startWebcam();
  }

  function bindUploadModal() {
    $$("#upload-modal .tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
    $("#file-label").addEventListener("click", (e) => {
      if (e.target.tagName !== "INPUT") $("#file-input").click();
    });
    $("#file-input").addEventListener("change", () => {
      const f = $("#file-input").files && $("#file-input").files[0];
      if (f) acceptFile(f);
    });

    const dz = $("#dropzone");
    ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => {
      e.preventDefault(); e.stopPropagation(); dz.classList.add("drag");
    }));
    ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => {
      e.preventDefault(); e.stopPropagation(); dz.classList.remove("drag");
    }));
    dz.addEventListener("drop", (e) => {
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) acceptFile(f);
    });

    document.addEventListener("paste", (e) => {
      const upload = $("#upload-modal");
      if (!upload.classList.contains("open")) return;
      if (!$('.tab-panel[data-panel="drop"]').classList.contains("active")) return;
      const items = e.clipboardData && e.clipboardData.items;
      if (!items) return;
      for (const it of items) {
        if (it.kind === "file" && it.type.startsWith("image/")) {
          const f = it.getAsFile(); if (f) { acceptFile(f); break; }
        }
      }
    });

    $("#webcam-start").addEventListener("click", startWebcam);
    $("#webcam-capture").addEventListener("click", captureFromWebcam);
    $("#webcam-retake").addEventListener("click", retake);

    $("#upload-submit").addEventListener("click", () => {
      if (!Upload.file || !Upload.studentId) return;
      $("#upload-submit").disabled = true;
      setProgress(0, "Uploading...", "");

      const fd = new FormData();
      fd.append("photo", Upload.file, Upload.file.name || "capture.jpg");

      const xhr = new XMLHttpRequest();
      xhr.open("POST", `/api/students/${Upload.studentId}/photo`, true);
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const pct = (e.loaded / e.total) * 100;
        setProgress(pct, `Uploading... ${pct.toFixed(0)}%`);
      };
      xhr.onload = () => {
        let body = null;
        try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
        if (xhr.status >= 200 && xhr.status < 300) {
          setProgress(100, "Face Registered Successfully", "done");
          showResult({ title: "Face Registered Successfully", ok: true,
            message: `${Upload.studentName}'s face has been encoded and is now ready for live recognition.` });
          closeUploadModal();
          window.dispatchEvent(new CustomEvent("face-registered", { detail: { studentId: Upload.studentId } }));
        } else {
          const msg = (body && body.error) || `Upload failed (HTTP ${xhr.status}).`;
          setProgress(100, msg, "error");
          const isNoFace = /no face/i.test(msg);
          showResult({
            title: isNoFace ? "No Face Detected" : "Upload Failed",
            ok: false,
            message: isNoFace
              ? "We couldn't find a face in this image. Try a clearer front-facing photo with good lighting."
              : msg,
          });
        }
      };
      xhr.onerror = () => {
        setProgress(100, "Network error", "error");
        showResult({ title: "Network Error", ok: false, message: "The request didn't reach the server. Check your connection and try again." });
      };
      xhr.send(fd);
    });
  }

  // ------------------------------------------------------------ bootstrap
  document.addEventListener("DOMContentLoaded", () => {
    initSidebar();
    bindUploadModal();
  });
})();
