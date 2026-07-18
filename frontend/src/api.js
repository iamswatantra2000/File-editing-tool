const BASE = "/api/jobs";

export async function submitJob(file, prompt) {
  const form = new FormData();
  form.append("file", file);
  form.append("prompt", prompt);

  const res = await fetch(BASE, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Failed to submit job");
  }
  return res.json();
}

export async function pollJob(jobId) {
  const res = await fetch(`${BASE}/${jobId}`);
  if (!res.ok) throw new Error("Failed to poll job");
  return res.json();
}

export function resultUrl(jobId) {
  return `${BASE}/${jobId}/result`;
}
