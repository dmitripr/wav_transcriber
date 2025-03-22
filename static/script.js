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