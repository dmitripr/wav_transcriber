document.getElementById("uploadForm").addEventListener("submit", async function (e) {
  e.preventDefault();
  const fileInput = document.getElementById("fileInput");
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const res = await fetch("/upload", {
    method: "POST",
    body: formData
  });

  const data = await res.json();
  const jobId = data.job_id;
  document.getElementById("status").innerText = "Transcription started...";

  pollJobs();
});

async function pollJobs() {
  const res = await fetch("/jobs");
  const jobs = await res.json();

  const jobList = document.getElementById("jobList");
  jobList.innerHTML = "";

  jobs.forEach(job => {
    const li = document.createElement("li");
    let content = `${job.filename} — ${job.status}`;
    if (job.status === "done") {
      content += ` — <a href="/download/${job.job_id}">Download</a>`;
    }
    li.innerHTML = content;
    jobList.appendChild(li);
  });
}

setInterval(pollJobs, 3000);