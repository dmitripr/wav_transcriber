async function pollJobs() {
  const res = await fetch("/jobs");
  const jobs = await res.json();
  const jobList = document.getElementById("jobList");
  
  jobList.innerHTML = "";

  for (const job of jobs) {
    const li = document.createElement("li");
    let content = `${job.filename} — ${job.status}`;

    // Fetch progress
    const progressRes = await fetch(`/progress/${job.job_id}`);
    const { progress } = await progressRes.json();

    if (job.status === "done") {
      content += ` — <a href="/download/${job.job_id}">Download</a>`;
    } else {
      content += ` — ${progress}%`;
    }
    
    li.innerHTML = content;
    jobList.appendChild(li);
  };
}

setInterval(pollJobs, 3000);
window.addEventListener("load", pollJobs);