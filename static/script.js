async function pollJobs() {
  const res = await fetch("/jobs");
  const jobs = await res.json();
  const jobList = document.getElementById("jobList");

  // Track which jobs are already shown
  const seen = new Set();

  for (const job of jobs) {
    seen.add(job.job_id);
    const itemId = `job-${job.job_id}`;
    let li = document.getElementById(itemId);

    // Create new list item if it doesn't exist
    if (!li) {
      li = document.createElement("li");
      li.id = itemId;
      jobList.appendChild(li);
    }

    // Safely fetch progress
    let progress = 0;
    try {
      const progressRes = await fetch(`/progress/${job.job_id}`);
      const progressData = await progressRes.json();
      progress = progressData.progress || 0;
    } catch (err) {
      console.error("Progress fetch failed:", err);
    }

    // Update inner HTML
    let content = `${job.filename} — ${job.status}`;
    if (job.status === "done") {
      content += ` — <a href="/download/${job.job_id}">Download</a>`;
    } else {
      content += ` — ${progress}%`;
    }
    li.innerHTML = content;
  }

  // Optionally remove jobs no longer in the list (not necessary now)
}
