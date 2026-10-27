import ReactMarkdown, { type Components } from 'react-markdown'

// Note text is untrusted (threat model T6). react-markdown builds React
// elements, never HTML strings; raw HTML in a note is dropped (skipHtml);
// links keep only safe protocols (its default urlTransform); images aren't
// shown yet, their alt text is.
const components: Components = {
  h1: ({ children }) => <h2 className="mt-8 mb-3 text-2xl font-semibold tracking-tight">{children}</h2>,
  h2: ({ children }) => <h3 className="mt-7 mb-2 text-xl font-semibold tracking-tight">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-6 mb-2 text-lg font-semibold">{children}</h4>,
  h4: ({ children }) => <h5 className="mt-5 mb-2 font-semibold">{children}</h5>,
  h5: ({ children }) => <h6 className="mt-4 mb-1 font-semibold">{children}</h6>,
  h6: ({ children }) => <h6 className="mt-4 mb-1 font-semibold text-stone-500">{children}</h6>,
  p: ({ children }) => <p className="my-3">{children}</p>,
  ul: ({ children }) => <ul className="my-3 ml-6 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 ml-6 list-decimal space-y-1">{children}</ol>,
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-l-4 border-stone-300 pl-4 text-stone-600 dark:border-stone-700 dark:text-stone-400">
      {children}
    </blockquote>
  ),
  code: ({ children }) => (
    <code className="rounded bg-stone-200 px-1 py-0.5 font-mono text-[0.9em] dark:bg-stone-800">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto rounded-lg bg-stone-100 p-4 font-mono text-sm dark:bg-stone-900 [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-700 underline dark:text-emerald-400">
      {children}
    </a>
  ),
  img: ({ alt }) => <span className="text-stone-500">[{alt || 'image'}]</span>,
  hr: () => <hr className="my-6 border-stone-200 dark:border-stone-800" />,
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-stone-300 px-2 py-1 text-left font-semibold dark:border-stone-700">{children}</th>
  ),
  td: ({ children }) => <td className="border-b border-stone-200 px-2 py-1 dark:border-stone-800">{children}</td>,
}

export default function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown skipHtml components={components}>
      {text}
    </ReactMarkdown>
  )
}
