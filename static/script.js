window.addEventListener("DOMContentLoaded", () => {
  const jobList = document.getElementById("jobList");

  async function pollJobs() {
    try {
      const res = await fetch("/jobs");
      const jobs = await res.json();
      console.log("Jobs:", jobs);

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
        } catch (err) {
          console.error("Progress fetch failed:", err);
        }

        let content = `${job.filename} — ${job.status}`;
        if (job.status === "done") {
          content += ` — <a href="/download/${job.job_id}">Download</a>`;
        } else {
          content += ` — ${progress}%`;
        }

        li.innerHTML = content;
      }
    } catch (err) {
      console.error("Failed to fetch /jobs:", err);
    }
  }

  // Start polling
  pollJobs();
  setInterval(pollJobs, 3000);
});
