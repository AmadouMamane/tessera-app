"use client";

import { Check, Copy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { cn } from "@/lib/cn";

type InlineNode =
  | string
  | { bold: string }
  | { italic: string }
  | { code: string }
  | { link: string; href: string };

type Block =
  | { type: "p"; text: string }
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "hr" }
  | { type: "code"; lang: string; text: string }
  | { type: "blockquote"; lines: string[] };

function parseInline(text: string): InlineNode[] {
  const nodes: InlineNode[] = [];
  const re = /\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|\[(.+?)\]\((https?:\/\/[^)]+)\)/g;
  let last = 0;
  for (let m = re.exec(text); m !== null; m = re.exec(text)) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const [, b, it, c, l, href] = m;
    if (b !== undefined) nodes.push({ bold: b });
    else if (it !== undefined) nodes.push({ italic: it });
    else if (c !== undefined) nodes.push({ code: c });
    else if (l !== undefined && href !== undefined) nodes.push({ link: l, href });
    last = re.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function renderInline(text: string, keyPrefix: string) {
  return parseInline(text).map((n, i) => {
    const k = `${keyPrefix}-${i}`;
    if (typeof n === "string") return n;
    if ("bold" in n)
      return (
        <strong key={k} className="font-semibold">
          {n.bold}
        </strong>
      );
    if ("italic" in n) return <em key={k}>{n.italic}</em>;
    if ("code" in n)
      return (
        <code
          key={k}
          className="rounded bg-[var(--muted)] px-1 py-0.5 font-mono text-[0.85em] text-[var(--foreground)]"
        >
          {n.code}
        </code>
      );
    // link
    return (
      <a
        key={k}
        href={n.href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-gold-600 underline underline-offset-2 transition-colors hover:text-gold-700 dark:text-gold-400 dark:hover:text-gold-300"
      >
        {n.link}
      </a>
    );
  });
}

const UL_RE = /^[-*•] /;
const OL_RE = /^\d+\. /;
const HR_RE = /^[-*_]{3,}$/;

function parseBlocks(text: string): Block[] {
  const lines = text.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i] ?? "";

    // Fenced code block
    const fenceMatch = /^```(\w*)/.exec(line);
    if (fenceMatch) {
      const lang = fenceMatch[1] ?? "";
      i++;
      const codeLines: string[] = [];
      while (i < lines.length && !/^```/.test(lines[i] ?? "")) {
        codeLines.push(lines[i] ?? "");
        i++;
      }
      i++; // skip closing ```
      blocks.push({ type: "code", lang, text: codeLines.join("\n") });
      continue;
    }

    // Each pattern requires its exact "#…# " prefix, so they are mutually
    // exclusive — no need to cross-guard with `!h3 && …` (which produced a
    // `false | RegExpExecArray` union that broke `?.[1]` narrowing).
    const h1 = /^# (.+)/.exec(line);
    const h2 = /^## (.+)/.exec(line);
    const h3 = /^### (.+)/.exec(line);

    if (h3?.[1]) {
      blocks.push({ type: "h3", text: h3[1] });
      i++;
      continue;
    }
    if (h2?.[1]) {
      blocks.push({ type: "h2", text: h2[1] });
      i++;
      continue;
    }
    if (h1?.[1]) {
      blocks.push({ type: "h1", text: h1[1] });
      i++;
      continue;
    }

    if (HR_RE.test(line.trim())) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // Blockquote
    if (/^> /.test(line)) {
      const bqLines: string[] = [];
      while (i < lines.length && /^> /.test(lines[i] ?? "")) {
        bqLines.push((lines[i] ?? "").slice(2));
        i++;
      }
      blocks.push({ type: "blockquote", lines: bqLines });
      continue;
    }

    if (UL_RE.test(line)) {
      const items: string[] = [];
      while (i < lines.length && UL_RE.test(lines[i] ?? "")) {
        items.push((lines[i] ?? "").replace(UL_RE, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    if (OL_RE.test(line)) {
      const items: string[] = [];
      while (i < lines.length && OL_RE.test(lines[i] ?? "")) {
        items.push((lines[i] ?? "").replace(OL_RE, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    if (line.trim() === "") {
      i++;
      continue;
    }

    const paraLines: string[] = [];
    while (i < lines.length) {
      const l = lines[i] ?? "";
      if (
        l.trim() === "" ||
        /^#{1,3} /.test(l) ||
        /^```/.test(l) ||
        /^> /.test(l) ||
        UL_RE.test(l) ||
        OL_RE.test(l) ||
        HR_RE.test(l.trim())
      )
        break;
      paraLines.push(l);
      i++;
    }
    if (paraLines.length) blocks.push({ type: "p", text: paraLines.join(" ") });
  }

  return blocks;
}

function CodeBlock({ lang, text }: { lang: string; text: string }) {
  const t = useTranslations("chat");
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="group/code rounded-xl border border-[var(--border)] bg-[var(--muted)]/60 dark:bg-navy-800/80">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-1.5">
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]/60">
          {lang || "text"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            "flex items-center gap-1 text-xs transition-all duration-150",
            "text-[var(--muted-foreground)]/40 hover:text-[var(--muted-foreground)]",
            "opacity-0 group-hover/code:opacity-100",
            copied && "!opacity-100 text-green-600 dark:text-green-400",
          )}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? t("copied") : t("copy")}
        </button>
      </div>
      <pre className="overflow-x-auto px-3 py-2.5">
        <code className="font-mono text-[0.8em] leading-relaxed text-[var(--foreground)]">
          {text}
        </code>
      </pre>
    </div>
  );
}

interface MarkdownProps {
  children: string;
  className?: string;
  trailingCursor?: boolean;
}

const Cursor = () => (
  <span
    aria-hidden
    className="ml-0.5 inline-block h-3.5 w-0.5 translate-y-0.5 animate-pulse bg-current opacity-60"
  />
);

export function Markdown({ children, className, trailingCursor = false }: MarkdownProps) {
  const blocks = parseBlocks(children);
  const lastIdx = blocks.length - 1;
  // Cursor is inline-eligible only for text blocks (p, headings).
  // For list/code/blockquote/hr we fall back to a standalone cursor after all blocks.
  const lastBlock = lastIdx >= 0 ? blocks[lastIdx] : undefined;
  const lastIsInline = lastBlock !== undefined && ["p", "h1", "h2", "h3"].includes(lastBlock.type);

  return (
    <div
      className={cn(
        "space-y-2 text-sm leading-relaxed [&_p]:text-justify [&_p]:hyphens-auto [&_li]:text-justify [&_li]:hyphens-auto",
        className,
      )}
    >
      {blocks.map((block, bi) => {
        const key = `b${bi}`;
        const isLast = bi === lastIdx;
        const cur = isLast && trailingCursor && lastIsInline ? <Cursor key={`${key}-cur`} /> : null;
        switch (block.type) {
          case "h1":
            return (
              <p key={key} className="text-base font-bold">
                {renderInline(block.text, key)}
                {cur}
              </p>
            );
          case "h2":
            return (
              <p key={key} className="font-bold">
                {renderInline(block.text, key)}
                {cur}
              </p>
            );
          case "h3":
            return (
              <p key={key} className="font-semibold">
                {renderInline(block.text, key)}
                {cur}
              </p>
            );
          case "p":
            return (
              <p key={key}>
                {renderInline(block.text, key)}
                {cur}
              </p>
            );
          case "ul":
            return (
              <ul
                key={key}
                className="ml-4 list-disc space-y-0.5 marker:text-[var(--muted-foreground)]"
              >
                {block.items.map((item, ii) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: markdown re-parses each render; list items never reorder
                  <li key={ii}>{renderInline(item, `${key}-${ii}`)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol
                key={key}
                className="ml-4 list-decimal space-y-0.5 marker:text-[var(--muted-foreground)]"
              >
                {block.items.map((item, ii) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: markdown re-parses each render; list items never reorder
                  <li key={ii}>{renderInline(item, `${key}-${ii}`)}</li>
                ))}
              </ol>
            );
          case "hr":
            return <hr key={key} className="border-[var(--border)]" />;
          case "blockquote":
            return (
              <blockquote
                key={key}
                className="border-l-2 border-gold-500/50 pl-3 italic text-[var(--muted-foreground)] dark:border-gold-400/40"
              >
                {block.lines.map((line, li) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: markdown re-parses each render; quote lines never reorder
                  <p key={li}>{renderInline(line, `${key}-${li}`)}</p>
                ))}
              </blockquote>
            );
          case "code":
            return <CodeBlock key={key} lang={block.lang} text={block.text} />;
        }
      })}
      {trailingCursor && !lastIsInline && blocks.length > 0 && <Cursor />}
    </div>
  );
}
