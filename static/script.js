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

  const interval = setInterval(async () => {
    const statusRes = await fetch(`/progress/${jobId}`);
    const statusData = await statusRes.json();
    const status = statusData.status;

    if (status === "done") {
      clearInterval(interval);
      document.getElementById("status").innerHTML = `
        ✅ Done! <a href="/download/${jobId}">Download transcript</a>
      `;
    } else if (status === "error") {
      clearInterval(interval);
      document.getElementById("status").innerText = "❌ An error occurred.";
    } else {
      document.getElementById("status").innerText = `⏳ Status: ${status}...`;
    }
  }, 2000);
});