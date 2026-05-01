import type { MDXComponents } from "mdx/types";
import Image, { type ImageProps } from "next/image";
import { BeforeAfter } from "./components/before-after";
import { FocusChart } from "./components/focus-chart";

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    BeforeAfter,
    FocusChart,
    h1: (props) => (
      <h1 className="mt-16 mb-8 font-serif text-4xl font-medium leading-[1.15] tracking-tight text-stone-900 sm:text-[2.75rem]" {...props} />
    ),
    h2: (props) => (
      <h2 className="mt-14 mb-5 font-serif text-2xl font-medium leading-snug tracking-tight text-stone-900 sm:text-[1.75rem]" {...props} />
    ),
    h3: (props) => (
      <h3 className="mt-10 mb-3 font-serif text-xl font-medium tracking-tight text-stone-900" {...props} />
    ),
    p: (props) => (
      <p className="my-6 font-serif text-[1.125rem] leading-[1.75] text-stone-800" {...props} />
    ),
    a: (props) => (
      <a className="underline decoration-stone-400 underline-offset-4 transition-colors hover:decoration-stone-700" {...props} />
    ),
    ul: (props) => (
      <ul className="my-6 list-disc space-y-2 pl-6 font-serif text-[1.125rem] leading-[1.75] text-stone-800" {...props} />
    ),
    ol: (props) => (
      <ol className="my-6 list-decimal space-y-2 pl-6 font-serif text-[1.125rem] leading-[1.75] text-stone-800" {...props} />
    ),
    li: (props) => <li className="pl-1" {...props} />,
    blockquote: (props) => (
      <blockquote className="my-8 border-l-2 border-stone-400 pl-6 font-serif text-[1.2rem] italic leading-[1.7] text-stone-700" {...props} />
    ),
    code: (props) => (
      <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-[0.9em] text-stone-800" {...props} />
    ),
    pre: (props) => (
      <pre className="my-8 overflow-x-auto rounded-md border border-stone-200 bg-stone-50 p-5 font-mono text-[0.9rem] leading-relaxed text-stone-800" {...props} />
    ),
    hr: () => (
      <hr className="my-14 mx-auto w-12 border-0 border-t border-stone-300" />
    ),
    table: (props) => (
      <div className="my-8 overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[0.95rem]" {...props} />
      </div>
    ),
    thead: (props) => <thead className="border-b border-stone-300" {...props} />,
    th: (props) => (
      <th className="py-2 pr-6 text-left font-medium text-stone-600 uppercase text-xs tracking-wider" {...props} />
    ),
    td: (props) => (
      <td className="border-b border-stone-200 py-2 pr-6 text-stone-800" {...props} />
    ),
    img: (props) => (
      <Image
        {...(props as ImageProps)}
        width={1920}
        height={1080}
        sizes="(min-width: 768px) 768px, 100vw"
        className="my-10 h-auto w-full rounded-sm"
      />
    ),
    ...components,
  };
}
