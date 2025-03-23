async function pollJobs() {
  const res = await fetch("/jobs");
  const jobs = await res.json();

  const jobList = document.getElementById("jobList");

  jobs.forEach(async (job) => {
    const itemId = `job-${job.job_id}`;
    let li = document.getElementById(itemId);

    // If job item doesn't exist, create it
    if (!li) {
      li = document.createElement("li");
      li.id = itemId;
      jobList.appendChild(li);
    }

    // Get progress
    const progressRes = await fetch(`/progress/${job.job_id}`);
    const { progress } = await progressRes.json();

    // Update job status and progress
    let content = `${job.filename} — ${job.status}`;
    if (job.status === "done") {
      content += ` — <a href="/download/${job.job_id}">Download</a>`;
    } else {
      content += ` — ${progress}%`;
    }

    li.innerHTML = content;
  });
}