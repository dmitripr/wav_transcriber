
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("ytForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("ytUrl").value;
    const action = document.getElementById("ytAction").value;
    const endpoint = action === "download" ? "/yt_download" : "/yt_transcribe";
    const formData = new FormData();
    formData.append("url", url);
    await fetch(endpoint, { method: "POST", body: formData });
    document.getElementById("ytUrl").value = "";
  });

  window.clearTranscriptions = async () => {
    await fetch("/clear_transcriptions", { method: "DELETE" });
    const tbody = document.querySelector("#jobTable tbody");
    tbody.innerHTML = "";
  };

  window.clearAudio = async () => {
    await fetch("/clear_audio_jobs", { method: "DELETE" });
    pollAudio();
  };

  window.deleteAudio = async (jobId) => {
    await fetch(`/audio_jobs/${jobId}`, { method: "DELETE" });
    const row = document.getElementById(`audio-${jobId}`);
    if (row) row.remove();
  };

  async function pollJobs() {
    const res = await fetch("/jobs");
    const jobs = await res.json();
    const tbody = document.querySelector("#jobTable tbody");
  
    for (const job of jobs) {
      const rowId = `job-${job.job_id}`;
      let row = document.getElementById(rowId);
  
      if (!row) {
        row = document.createElement("tr");
        row.id = rowId;
        tbody.appendChild(row);
      }
  
      const progressRes = await fetch(`/progress/${job.job_id}`);
      const progressData = await progressRes.json();
  
      row.innerHTML = `
        <td>${job.filename}</td>
        <td>${job.start || "—"}</td>
        <td>${progressData.status} ${progressData.progress || 0}%</td>
        <td>${job.end || "—"}</td>
        <td>${progressData.status === "done" ? `<a href="/download/${job.job_id}">Download</a>` : ""}</td>
      `;
    }
  }
  

  async function pollAudio() {
    const res = await fetch("/audio_jobs");
    const jobs = await res.json();
    const tbody = document.querySelector("#audioTable tbody");
    tbody.innerHTML = "";

    for (const job of jobs) {
      const row = document.createElement("tr");
      row.id = `audio-${job.job_id}`;
      row.innerHTML = `
        <td>${job.filename}</td>
        <td>${job.start || "—"}</td>
        <td>${job.status}</td>
        <td>${job.end || "—"}</td>
        <td>${job.status === "done" ? `<a href="/download_mp3/${job.job_id}">Download MP3</a> 
        <button onclick="deleteAudio('${job.job_id}')">Delete</button>` : "—"}</td>
      `;
      tbody.appendChild(row);
    }
  }

  pollJobs();
  pollAudio();
  setInterval(pollJobs, 3000);
  setInterval(pollAudio, 5000);
});
