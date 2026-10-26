// Small helpers shared by the mockups. Mockups only: the real app is React.
// Text is always inserted with textContent or escaped, never as raw HTML from data,
// the same rule the app follows (threat model T6).

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c])

// Minimal Markdown for mock notes: headings, list items, bold, italic, code, [[wikilinks]].
function renderBody(lines) {
  return lines
    .map((raw) => {
      let line = esc(raw)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(/`(.+?)`/g, '<code class="rounded bg-zinc-200 px-1 dark:bg-zinc-800">$1</code>')
        .replace(/\[\[(.+?)\]\]/g, '<a href="#" class="wikilink text-violet-600 underline decoration-dotted dark:text-violet-400" data-title="$1">$1</a>')
      if (raw.startsWith("## ")) return `<h3 class="mt-5 mb-2 text-base font-semibold">${line.slice(3)}</h3>`
      if (raw.startsWith("- ")) return `<li class="ml-5 list-disc">${line.slice(2)}</li>`
      return `<p class="my-2">${line}</p>`
    })
    .join("")
}

function noteIdByTitle(title) {
  return Object.keys(MOCK.notes).find((id) => MOCK.notes[id].title.toLowerCase() === title.toLowerCase())
}

const PRIORITY_CLASSES = {
  high: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  normal: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  low: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
}

const STAGE_CLASSES = {
  open: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
  "in-progress": "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
  "in-review": "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-300",
  done: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
}

const pill = (text, classes) =>
  `<span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${classes}">${esc(text)}</span>`

// One stage forward only, matching the app's rule: no skipping stages.
function nextStage(status) {
  const i = MOCK.stages.indexOf(status)
  return i >= 0 && i < MOCK.stages.length - 1 ? MOCK.stages[i + 1] : null
}

function advanceTask(id) {
  const t = MOCK.tasks.find((x) => x.id === id)
  const next = t && nextStage(t.status)
  if (!next) return
  if (next === "done" && !confirm("Sign off and move to Done?")) return
  t.history.push(`${t.status} → ${next}${next === "done" ? " (signed off)" : ""}`)
  t.status = next
}

// Light/dark toggle. Starts from the system setting.
function initTheme() {
  const root = document.documentElement
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) root.classList.add("dark")
  document.querySelectorAll("[data-theme-toggle]").forEach((b) =>
    b.addEventListener("click", () => root.classList.toggle("dark")),
  )
}

// A simple ⌘K / Ctrl+K command palette over notes and tasks.
function initPalette(onPick) {
  const dlg = document.getElementById("palette")
  const input = document.getElementById("palette-input")
  const list = document.getElementById("palette-list")
  const items = [
    ...Object.entries(MOCK.notes).map(([id, n]) => ({ kind: "Note", label: n.title, id })),
    ...MOCK.tasks.map((t) => ({ kind: "Task", label: t.title, id: t.id })),
  ]
  const draw = () => {
    const q = input.value.toLowerCase()
    list.innerHTML = items
      .filter((i) => i.label.toLowerCase().includes(q))
      .slice(0, 8)
      .map(
        (i, k) =>
          `<li><button data-k="${k}" class="flex w-full items-center gap-2 rounded px-3 py-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800"><span class="w-10 text-xs text-zinc-500">${esc(i.kind)}</span>${esc(i.label)}</button></li>`,
      )
      .join("")
    const shown = items.filter((i) => i.label.toLowerCase().includes(q)).slice(0, 8)
    list.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        dlg.close()
        onPick(shown[Number(b.dataset.k)])
      }),
    )
  }
  input.addEventListener("input", draw)
  const open = () => {
    input.value = ""
    draw()
    dlg.showModal()
    input.focus()
  }
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault()
      open()
    }
  })
  document.querySelectorAll("[data-palette-open]").forEach((b) => b.addEventListener("click", open))
}

// The palette dialog markup, shared by all three pages.
const PALETTE_HTML = `
<dialog id="palette" class="w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-0 text-zinc-900 shadow-2xl backdrop:bg-black/40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100">
  <input id="palette-input" placeholder="Search notes and tasks…" class="w-full border-b border-zinc-200 bg-transparent px-4 py-3 outline-none dark:border-zinc-700" />
  <ul id="palette-list" class="max-h-80 overflow-auto p-2"></ul>
  <p class="border-t border-zinc-200 px-4 py-2 text-xs text-zinc-500 dark:border-zinc-700">Mockup: made-up data. Esc to close.</p>
</dialog>`
