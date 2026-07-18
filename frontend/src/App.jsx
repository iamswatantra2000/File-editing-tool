import { useEffect, useRef, useState } from "react";
import { pollJob, submitJob } from "./api.js";
import JobStatus from "./components/JobStatus.jsx";
import Uploader from "./components/Uploader.jsx";

const POLL_INTERVAL_MS = 1500;

export default function App() {
  const [file, setFile] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [job, setJob] = useState(null);

  const pollRef = useRef(null);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed") {
      clearInterval(pollRef.current);
      return;
    }
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const updated = await pollJob(job.id);
        setJob(updated);
      } catch {
        // transient network error — keep polling
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(pollRef.current);
  }, [job?.id, job?.status]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file || !prompt.trim()) return;

    setSubmitting(true);
    setSubmitError(null);
    setJob(null);

    try {
      const created = await submitJob(file, prompt.trim());
      setJob(created);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    clearInterval(pollRef.current);
    setFile(null);
    setPrompt("");
    setJob(null);
    setSubmitError(null);
  }

  const canSubmit = file && prompt.trim() && !submitting && !job;

  return (
    <div className="min-h-screen bg-stone-950 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
      <div className="w-full max-w-lg mx-auto">

        {/* Header */}
        <div className="mb-8 sm:mb-10">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-100 font-montserrat">
            Document Editing Agent
          </h1>
          <p className="mt-1.5 text-xs sm:text-sm text-stone-500 leading-relaxed">
            Upload a .docx or .xlsx, describe your edit, and let Claude do the work.
          </p>
        </div>

        {/* Form card */}
        {!job && (
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 sm:p-6">
            <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
              <Uploader file={file} onFileSelect={setFile} />

              <div className="space-y-1.5">
                <label
                  htmlFor="prompt"
                  className="block text-xs font-semibold uppercase tracking-widest text-stone-400"
                >
                  What would you like to change?
                </label>
                <textarea
                  id="prompt"
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder='e.g. "insert a pie chart titled Q2 Revenue with Product 40, Services 35, Support 25 after the Financials heading"'
                  className="w-full bg-stone-800 border border-stone-700 rounded-lg px-3 py-2.5 sm:px-4 sm:py-3
                             text-sm text-stone-100 placeholder-stone-600 leading-relaxed
                             focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/40
                             resize-none transition"
                />
              </div>

              {submitError && (
                <div className="bg-red-950/60 border border-red-800/50 rounded-lg px-4 py-3 text-sm text-red-400 leading-relaxed">
                  {submitError}
                </div>
              )}

              <button
                type="submit"
                disabled={!canSubmit}
                className="w-full flex items-center justify-center gap-2
                           bg-orange-500 hover:bg-orange-600 active:bg-orange-700
                           disabled:opacity-40 disabled:cursor-not-allowed
                           text-stone-950 font-semibold text-sm tracking-wide rounded-lg
                           px-5 py-2.5 sm:py-3 transition font-inter"
              >
                {submitting ? (
                  <>
                    <span className="spinner" />
                    Submitting…
                  </>
                ) : (
                  "Edit document"
                )}
              </button>
            </form>
          </div>
        )}

        <JobStatus job={job} onReset={handleReset} />
      </div>
    </div>
  );
}
