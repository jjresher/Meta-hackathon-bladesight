import type { ReactNode } from "react";

/**
 * A small, safe Markdown renderer for the agent's report: headings, bullet lists, paragraphs,
 * `**bold**`, `_italic_` and `` `code` ``. It builds React elements only (no HTML injection), so
 * model-written text can never add markup. Anything else is shown as plain text.
 */
function inline(text: string, keyBase: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|(?<!\w)_.+?_(?!\w))/g;
  let last = 0;
  let index = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    const token = match[0];
    const key = `${keyBase}-${index++}`;
    if (token.startsWith("**")) parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("`")) parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    else parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    last = start + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function Markdown({ source }: { source: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let paragraph: string[] = [];

  const flushList = () => {
    if (list.length === 0) return;
    const key = `ul-${blocks.length}`;
    blocks.push(
      <ul key={key}>
        {list.map((item, i) => (
          <li key={i}>{inline(item, `${key}-${i}`)}</li>
        ))}
      </ul>,
    );
    list = [];
  };
  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    const key = `p-${blocks.length}`;
    blocks.push(<p key={key}>{inline(paragraph.join(" "), key)}</p>);
    paragraph = [];
  };

  for (const raw of source.split("\n")) {
    const line = raw.trimEnd();
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    if (heading) {
      flushList();
      flushParagraph();
      const level = Math.min(heading[1].length + 1, 5); // the page owns the h1
      const key = `h-${blocks.length}`;
      const Tag = `h${level}` as "h2" | "h3" | "h4" | "h5";
      blocks.push(<Tag key={key}>{inline(heading[2], key)}</Tag>);
    } else if (bullet) {
      flushParagraph();
      list.push(bullet[1]);
    } else if (line.trim() === "") {
      flushList();
      flushParagraph();
    } else {
      flushList();
      paragraph.push(line.trim());
    }
  }
  flushList();
  flushParagraph();
  return <div className="markdown">{blocks}</div>;
}
