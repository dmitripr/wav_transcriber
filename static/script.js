document.getElementById("uploadForm").addEventListener("submit", async function (e) {
  e.preventDefault();
  const fileInput = document.getElementById("fileInput");
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const res = await fetch("/upload", {
    method: "POST",
    body: formData
  });

  if (res.ok) {
    // Redirect back to home to show job list
    window.location.href = "/";
  } else {
    const error = await res.text();
    alert("Upload failed: " + error);
  }
});

// Run on page load to show jobs
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
window.addEventListener("load", pollJobs);
