import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function ReportCard({ title, markdown }: { title: string; markdown: string }) {
  const pass = /\*\*Overall:\*\*.*PASS/.test(markdown);
  return (
    <article className="card">
      <div className="row">
        <div className="title">{title}</div>
        <div className={pass?"badge pass":"badge fail"}>{pass?"PASS":"FAIL"}</div>
      </div>
      <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown></div>
    </article>
  );
}
