window.addEventListener("DOMContentLoaded", () => {
  const jobList = document.getElementById("jobList");
  const audioList = document.getElementById("audioList");

  document.getElementById("ytForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("ytUrl").value;
    const action = document.getElementById("ytAction").value;
    const endpoint = action === "download" ? "/yt_download" : "/yt_transcribe";

    const formData = new FormData();
    formData.append("url", url);

    await fetch(endpoint, {
      method: "POST",
      body: formData
    });

    document.getElementById("ytUrl").value = "";
  });

  async function pollJobs() {
    const res = await fetch("/jobs");
    const jobs = await res.json();

    for (const job of jobs) {
      const itemId = `job-${job.job_id}`;
      let li = document.getElementById(itemId);
      if (!li) {
        li = document.createElement("li");
        li.id = itemId;
        jobList.appendChild(li);
      }

      let progress = 0;
      try {
        const progressRes = await fetch(`/progress/${job.job_id}`);
        const progressData = await progressRes.json();
        progress = progressData.progress || 0;
      } catch {}

      let content = `${job.filename} — ${job.status}`;
      if (job.status === "done") {
        content += ` — <a href="/download/${job.job_id}">Download</a>`;
      } else {
        content += ` — ${progress}%`;
      }

      li.innerHTML = content;
    }
  }

  async function pollAudio() {
    const res = await fetch("/audio_jobs");
    const audioJobs = await res.json();

    audioList.innerHTML = "";
    for (const job of audioJobs) {
      const li = document.createElement("li");
      li.innerHTML = `${job.filename} — <a href="/download_mp3/${job.job_id}">Download MP3</a> 
        <button onclick="deleteAudio('${job.job_id}')">Delete</button>`;
      audioList.appendChild(li);
    }
  }

  window.deleteAudio = async function (jobId) {
    await fetch(`/audio_jobs/${jobId}`, { method: "DELETE" });
  };

  pollJobs();
  pollAudio();
  setInterval(pollJobs, 3000);
  setInterval(pollAudio, 5000);
});