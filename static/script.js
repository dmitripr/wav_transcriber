const POLL_INTERVAL_MS = 3000;

const logDialog = document.getElementById("logDialog");
const logTitle = document.getElementById("logTitle");
const logSubtitle = document.getElementById("logSubtitle");
const logContent = document.getElementById("logContent");
const downloadLogButton = document.getElementById("downloadLog");

let currentLog = null;
let refreshing = false;

const ACTIVE_STATUSES = new Set([
  "running",
  "converting",
  "downloading",
  "fetching title",
]);

function makeRow(rowId) {
  const row = document.createElement("tr");
  row.id = rowId;

  const filenameCell = document.createElement("td");
  filenameCell.className = "filename";
  row.appendChild(filenameCell);

  for (let i = 0; i < 4; i += 1) {
    row.appendChild(document.createElement("td"));
  }
  return row;
}

function setText(cell, value) {
  const text =
    value === null || value === undefined || value === "" ? "—" : String(value);
  if (cell.textContent !== text) cell.textContent = text;
}

function statusClass(status) {
  if (status === "done") return "badge-success";
  if (status === "error") return "badge-danger";
  if (ACTIVE_STATUSES.has(status)) return "badge-active";
  return "badge-neutral";
}

function setStatus(cell, job, showProgress) {
  let badge = cell.querySelector(".badge");
  if (!badge) {
    cell.textContent = "";
    badge = document.createElement("span");
    cell.appendChild(badge);
  }

  let text = job.status || "unknown";
  if (showProgress && job.status !== "done" && job.status !== "error") {
    text += ` ${Number(job.progress) || 0}%`;
  }
  if (badge.textContent !== text) badge.textContent = text;

  const className = `badge ${statusClass(job.status)}`;
  if (badge.className !== className) badge.className = className;

  if (job.error) {
    cell.title = job.error;
  } else {
    cell.removeAttribute("title");
  }
}

function makeButton(label, variant, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `button small ${variant}`;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function triggerDownload(url) {
  const link = document.createElement("a");
  link.href = url;
  link.download = "";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function renderActions(cell, job, kind) {
  const state = `${job.status}|${job.filename}`;
  if (cell.dataset.state === state) return;
  cell.dataset.state = state;
  cell.textContent = "";

  const actions = document.createElement("div");
  actions.className = "actions";

  if (job.status === "done") {
    const label = kind === "audio" ? "Download MP3" : "Download";
    const href =
      kind === "audio"
        ? `/download_mp3/${encodeURIComponent(job.job_id)}`
        : `/download/${encodeURIComponent(job.job_id)}`;
    actions.appendChild(
      makeButton(label, "primary", () => triggerDownload(href))
    );
  }

  actions.appendChild(makeButton("Log", "ghost", () => showLog(job)));

  if (job.status === "error") {
    actions.appendChild(
      makeButton("Clear", "danger", () => deleteJob(kind, job.job_id))
    );
  } else if (job.status === "done") {
    actions.appendChild(
      makeButton("Delete", "ghost danger-text", () =>
        deleteJob(kind, job.job_id)
      )
    );
  }

  cell.appendChild(actions);
}

function removeStaleRows(tbody, seenRowIds) {
  Array.from(tbody.children).forEach((row) => {
    if (!seenRowIds.has(row.id) && !row.classList.contains("empty-row")) {
      row.remove();
    }
  });
}

function updateEmptyState(tbody, columns, message, isEmpty) {
  let row = tbody.querySelector(".empty-row");

  if (!isEmpty) {
    if (row) row.remove();
    return;
  }

  if (!row) {
    row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.className = "empty-state";
    cell.colSpan = columns;
    row.appendChild(cell);
    tbody.appendChild(row);
  }

  const cell = row.querySelector("td");
  if (cell.textContent !== message) cell.textContent = message;
}

function renderTranscriptions(jobs) {
  const tbody = document.querySelector("#jobTable tbody");
  const seen = new Set();

  jobs.forEach((job) => {
    const rowId = `job-${job.job_id}`;
    seen.add(rowId);

    let row = document.getElementById(rowId);
    if (!row) {
      row = makeRow(rowId);
      tbody.appendChild(row);
    }
    row.classList.toggle("is-error", job.status === "error");

    const cells = row.children;
    setText(cells[0], job.filename);
    setText(cells[1], job.start);
    setStatus(cells[2], job, true);
    setText(cells[3], job.end);
    renderActions(cells[4], job, "transcriptions");
  });

  removeStaleRows(tbody, seen);
  updateEmptyState(
    tbody,
    5,
    "No transcription jobs yet. Upload a file or submit a YouTube link.",
    jobs.length === 0
  );
}

function renderAudioJobs(jobs) {
  const tbody = document.querySelector("#audioTable tbody");
  const seen = new Set();

  jobs.forEach((job) => {
    const rowId = `audio-${job.job_id}`;
    seen.add(rowId);

    let row = document.getElementById(rowId);
    if (!row) {
      row = makeRow(rowId);
      tbody.appendChild(row);
    }
    row.classList.toggle("is-error", job.status === "error");

    const cells = row.children;
    setText(cells[0], job.filename);
    setText(cells[1], job.start);
    setStatus(cells[2], job, false);
    setText(cells[3], job.end);
    renderActions(cells[4], job, "audio");
  });

  removeStaleRows(tbody, seen);
  updateEmptyState(
    tbody,
    5,
    "No audio downloads yet. Paste a YouTube link above.",
    jobs.length === 0
  );
}

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const [jobs, audioJobs] = await Promise.allSettled([
      getJson("/jobs"),
      getJson("/audio_jobs"),
    ]);

    if (jobs.status === "fulfilled") {
      renderTranscriptions(jobs.value);
    } else {
      console.error(jobs.reason);
    }

    if (audioJobs.status === "fulfilled") {
      renderAudioJobs(audioJobs.value);
    } else {
      console.error(audioJobs.reason);
    }
  } finally {
    refreshing = false;
  }
}

async function showLog(job) {
  currentLog = { jobId: job.job_id, label: job.filename || job.job_id };
  logTitle.textContent = "Process log";
  logSubtitle.textContent = currentLog.label;
  logContent.textContent = "Loading…";
  downloadLogButton.disabled = true;

  if (!logDialog.open) logDialog.showModal();

  try {
    const response = await fetch(`/logs/${encodeURIComponent(job.job_id)}`, {
      headers: { Accept: "text/plain" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    logContent.textContent = await response.text();
    downloadLogButton.disabled = false;
  } catch (error) {
    logContent.textContent = `Could not load log: ${error.message}`;
  }

  logContent.scrollTop = logContent.scrollHeight;
}

function downloadCurrentLog() {
  if (!currentLog) return;
  const blob = new Blob([logContent.textContent], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `job-${currentLog.jobId.slice(0, 8)}.log`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function deleteJob(kind, jobId) {
  try {
    const url =
      kind === "audio"
        ? `/audio_jobs/${encodeURIComponent(jobId)}`
        : `/jobs/${encodeURIComponent(jobId)}`;
    const response = await fetch(url, { method: "DELETE" });
    if (!response.ok && response.status !== 404) {
      throw new Error(`Delete failed: ${response.status}`);
    }
    await refresh();
  } catch (error) {
    console.error(error);
  }
}

async function clearJobs(endpoint) {
  try {
    const response = await fetch(endpoint, { method: "DELETE" });
    if (!response.ok) throw new Error(`Clear failed: ${response.status}`);
    await refresh();
  } catch (error) {
    console.error(error);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const ytForm = document.getElementById("ytForm");
  const urlInput = document.getElementById("ytUrl");
  const actionSelect = document.getElementById("ytAction");

  ytForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const busyButton = ytForm.querySelector('button[type="submit"]');
    const endpoint =
      actionSelect.value === "download" ? "/yt_download" : "/yt_transcribe";
    const body = new FormData();
    body.append("url", urlInput.value.trim());

    busyButton.disabled = true;
    try {
      const response = await fetch(endpoint, { method: "POST", body });
      if (!response.ok) throw new Error(`Submit failed: ${response.status}`);
      urlInput.value = "";
      await refresh();
    } catch (error) {
      console.error(error);
    } finally {
      busyButton.disabled = false;
    }
  });

  document
    .getElementById("clearTranscriptions")
    .addEventListener("click", () => clearJobs("/clear_transcriptions"));
  document
    .getElementById("clearAudio")
    .addEventListener("click", () => clearJobs("/clear_audio_jobs"));

  document.getElementById("closeLog").addEventListener("click", () => {
    logDialog.close();
  });
  document
    .getElementById("closeLogFooter")
    .addEventListener("click", () => logDialog.close());
  downloadLogButton.addEventListener("click", downloadCurrentLog);
  logDialog.addEventListener("click", (event) => {
    if (event.target === logDialog) logDialog.close();
  });

  refresh();
  setInterval(() => {
    if (!document.hidden) refresh();
  }, POLL_INTERVAL_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh();
  });
});
