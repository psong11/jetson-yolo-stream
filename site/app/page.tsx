import Image from "next/image";
import Narrative from "@/content/narrative.mdx";

const EVENINGS_COMPLETE = 1;
const EVENINGS_TOTAL = 15;
const REPO_URL = "https://github.com/psong11/jetson-yolo-stream";

export default function Home() {
  return (
    <main className="min-h-screen">
      <Hero />
      <MetadataStrip />
      <article className="mx-auto max-w-[68ch] px-6 pb-24">
        <Narrative />
      </article>
      <Footer />
    </main>
  );
}

function Hero() {
  return (
    <section className="mx-auto max-w-[68ch] px-6 pt-24 pb-12 sm:pt-32">
      <p className="mb-6 font-mono text-xs uppercase tracking-[0.2em] text-stone-500">
        A Build Journal · Begun April 12, 2026
      </p>
      <h1 className="font-serif text-[2.75rem] font-medium leading-[1.1] tracking-tight text-stone-900 sm:text-[3.5rem]">
        Teaching a Small Computer to See
      </h1>
      <p className="mt-6 font-serif text-xl leading-relaxed text-stone-600 sm:text-2xl">
        Building a portable AI camera on a Jetson Orin Nano.
      </p>
      <div className="mt-16">
        <Image
          src="/images/first_light.jpg"
          alt="First Light — warm amber light from a desk lamp spills against a ceiling"
          width={1920}
          height={1080}
          priority
          className="h-auto w-full rounded-sm"
        />
        <p className="mt-3 font-mono text-xs text-stone-500">
          First Light. April 12, 2026.
        </p>
      </div>
    </section>
  );
}

function MetadataStrip() {
  const rows: ReadonlyArray<readonly [string, React.ReactNode]> = [
    [
      "Hardware",
      "Jetson Orin Nano 8GB · ArduCam UC-873 Rev D (IMX519, 16MP)",
    ],
    [
      "Stack",
      "Python · OpenCV · GStreamer · YOLO11n · CUDA · TensorRT (planned)",
    ],
    [
      "Status",
      `In progress · ${EVENINGS_COMPLETE} of ${EVENINGS_TOTAL} evenings`,
    ],
    [
      "Repo",
      <a
        key="repo"
        href={REPO_URL}
        className="underline decoration-stone-400 underline-offset-4 hover:decoration-stone-700"
      >
        github.com/psong11/jetson-yolo-stream
      </a>,
    ],
  ];

  return (
    <section className="border-y border-stone-200 bg-stone-100/40">
      <dl className="mx-auto max-w-[68ch] divide-y divide-stone-200 px-6">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="grid grid-cols-[7rem_1fr] items-baseline gap-4 py-4 sm:grid-cols-[8rem_1fr]"
          >
            <dt className="font-mono text-xs uppercase tracking-[0.2em] text-stone-500">
              {label}
            </dt>
            <dd className="font-serif text-base leading-snug text-stone-800">
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-stone-200 py-12">
      <div className="mx-auto max-w-[68ch] px-6">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-stone-500">
          Paul Song · Continuing
        </p>
        <p className="mt-2 font-serif text-sm text-stone-600">
          Source on{" "}
          <a
            href={REPO_URL}
            className="underline decoration-stone-400 underline-offset-4 hover:decoration-stone-700"
          >
            GitHub
          </a>
          . Written from a desk in evenings.
        </p>
      </div>
    </footer>
  );
}
