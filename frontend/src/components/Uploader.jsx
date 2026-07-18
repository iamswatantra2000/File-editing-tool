import { useRef, useState } from "react";

const ACCEPTED = [".docx", ".xlsx"];

export default function Uploader({ onFileSelect, file }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) validate(dropped);
  }

  function handleChange(e) {
    const picked = e.target.files[0];
    if (picked) validate(picked);
  }

  function validate(f) {
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      alert(`Only ${ACCEPTED.join(", ")} files are supported.`);
      return;
    }
    onFileSelect(f);
  }

  function clear(e) {
    e.stopPropagation();
    onFileSelect(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div
      onClick={() => !file && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`relative rounded-lg border-2 border-dashed px-4 py-6 sm:px-6 sm:py-8 text-center transition cursor-pointer select-none
        ${dragOver
          ? "border-orange-500 bg-orange-500/5"
          : "border-stone-700 bg-stone-800/40 hover:border-stone-600 hover:bg-stone-800/60"
        }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".docx,.xlsx"
        onChange={handleChange}
        className="hidden"
      />

      <div className="text-2xl sm:text-3xl mb-2">📄</div>
      <p className="text-xs sm:text-sm text-stone-400">
        <span className="text-orange-400 font-medium">Click to browse</span>
        <span className="hidden sm:inline"> or drag a file here</span>
      </p>
      <p className="text-xs text-stone-600 mt-1">Supports .docx and .xlsx</p>

      {file && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="mt-3 sm:mt-4 flex items-center gap-2 min-w-0
                     bg-stone-800 border border-stone-700 rounded-md px-3 py-2
                     text-xs text-stone-300"
        >
          <span className="shrink-0">📎</span>
          <span className="truncate min-w-0 flex-1">{file.name}</span>
          <span className="text-stone-500 shrink-0 hidden sm:inline">
            ({(file.size / 1024).toFixed(1)} KB)
          </span>
          <button
            onClick={clear}
            title="Remove file"
            className="shrink-0 ml-auto text-stone-500 hover:text-stone-200 active:text-stone-100
                       transition text-sm leading-none p-0.5"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
