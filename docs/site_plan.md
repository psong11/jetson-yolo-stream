# Site Build Plan & Handoff

> **You are starting a focused build session.** Read this file and `CLAUDE.md` end-to-end before doing anything. Everything you need is here. If something looks unclear, ask Paul before assuming — don't guess decisions that have already been made.

## What this is

Paul is building a portable AI camera on a Jetson Orin Nano (the existing `jetson-yolo-stream` project). He's preparing for interviews with a physical-AI / store-analytics team at Walmart, and the polished portfolio artifact for those interviews is a **public-facing website** that documents the build journey as a long-form story.

The website is what gets linked from his resume. GitHub remains the underlying code, but the site is the readable, scrollable, designed surface that recruiters and hiring managers will actually look at.

## What we're building

**A single long-scroll editorial page**, not a multi-page site, not a dashboard, not a portfolio grid. One page, one story, scrolled top to bottom. Think NYT / Pudding / The Atlantic longform pieces:

- Hero (project name, one-line subtitle, hero image)
- Project metadata strip (hardware, stack, status, GitHub link)
- The narrative — long-form prose, lifted from `narrative.md`, rendered with editorial typography
- Photographs and charts embedded inline at the moments they matter
- Pull-quotes (optional, used sparingly)
- Footer with last-updated, GitHub link, contact

The narrative is the spine. Everything else (charts, before/after components, code snippets) is supporting media.

## Stack — decided, do not relitigate

- **Framework**: Next.js (App Router), TypeScript
- **Styling**: Tailwind CSS
- **Content**: MDX — lets Paul drop React components inline in prose
- **Charts**: Recharts (line chart for the focus-search curve)
- **Hosting**: Vercel, deploys from `site/` subfolder of this monorepo
- **Domain**: `*.vercel.app` subdomain for now (no custom domain)
- **Look**: long-form journalism. Editorial serif body, monospace accents for code/data, minimal chrome, generous whitespace, image-first layouts. Reference: NYT longform pieces, The Pudding articles, Stripe Atlas-style writeups.

Paul is comfortable with React and Next.js — you can write idiomatic Next.js without spending time explaining basics.

## Repo structure

This is a **monorepo**. The site lives at `site/` inside the existing `jetson-yolo-stream` repo. Vercel can deploy from a subfolder by setting "Root Directory" to `site/` in the Vercel project settings.

```
jetson-yolo-stream/                         (monorepo root)
├── narrative.md                            (SOURCE OF TRUTH for prose — keep growing)
├── docs/                                   (technical reference docs)
│   ├── architecture.md
│   ├── autofocus.md                        (AK7375 wire protocol — recent)
│   ├── jetson_setup.md
│   ├── ssh_jetson.md
│   └── site_plan.md                        (THIS FILE)
├── arducam_focus/                          (Jetson Python code)
├── detect_local.py, server.py, client.py   (existing Jetson scripts)
├── first_observations/                     (April 12 first-light images + notes)
│   ├── first_light.jpg
│   ├── first_detection.jpg
│   └── first_observations_of_the_world.md
├── logs/                                   (chronological learning journal)
│   ├── 01-setup.md
│   ├── 02-csi-camera.md
│   └── 03-autofocus-investigation.md
├── media/                                  (site-bound media assets)
│   └── autofocus_2026-04-30/
│       ├── before_dac0000.jpg              (before AF — soft)
│       ├── after_dac0800.jpg               (after AF — sharp)
│       └── search_log.csv                  (34 sharpness samples from the AF search)
└── site/                                   (NEW — what you're building)
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                        (the single-page narrative)
    │   └── globals.css
    ├── content/
    │   └── narrative.mdx                   (mirrors narrative.md, with embedded components)
    ├── components/
    │   ├── focus-chart.tsx                 (Recharts line graph from search_log.csv)
    │   ├── before-after.tsx                (image swap/slider for before/after pairs)
    │   ├── stat-table.tsx                  (the "What | Value" tables Paul writes)
    │   └── narrative-section.tsx           (semantic wrapper for each chapter)
    ├── public/
    │   ├── images/                         (copy assets from media/ here at build)
    │   └── data/search_log.csv             (or fetch from /media in build step)
    ├── package.json
    └── tailwind.config.ts
```

## Content — what goes on the page

### Section 1: Hero
- Title: **"Teaching a Small Computer to See"** (Paul's existing tag from narrative.md)
- Subtitle: "Building a portable AI camera on a Jetson Orin Nano." (or a tighter Paul-voice variant)
- Hero image: `first_observations/first_light.jpg` — the very first processed photo, lamp-warm, soft
- Top-right: small GitHub link

### Section 2: Project metadata strip
A compact card or strip showing:
- Hardware: Jetson Orin Nano 8GB, ArduCam UC-873 Rev D (IMX519, 16MP)
- Stack: Python, OpenCV, GStreamer, YOLO11n, CUDA, TensorRT (planned)
- Status: in progress (X of 15 evenings — pull from a single config var so it updates)
- Repo: link to GitHub

### Section 3: The build log (the narrative)
The long-form prose, lifted from `narrative.md`. As of writing there are two entries:

- **April 12, 2026 — First Light** (~3000 words). Includes embedded images: `first_observations/first_light.jpg` and `first_observations/first_detection.jpg`. Ends with a "What | Value" stat table.
- **April 16, 2026 — What You Can't Reach** (~2500 words). The autofocus-locked-door story, ending unresolved. Stat table at end.

A **third entry is coming soon** — Paul will write "April 30, 2026 — The Door Opens" (or similar title) covering tonight's autofocus victory. When that lands in `narrative.md`, the site should pick it up automatically (if narrative is imported as MDX) or with a re-render.

The third entry's media payload (already in `media/autofocus_2026-04-30/`):
- **Before/after image pair** — render with a `<BeforeAfter>` slider component. Caption: "Lens at DAC=0 (cold start) vs DAC=800 (after autofocus). The Tenengrad sharpness score went from 115 to 415."
- **Focus search curve** — render with a `<FocusChart>` component reading `search_log.csv` (34 rows). Two passes visible: coarse (DAC 0–4095 in 256-unit steps) and fine (around peak in 32-unit steps). Annotate the peak. Use serif typography for axis labels.

### Section 4 (eventually): What's next
- Brief mention of the 15-evening plan and current progress
- Pull from a status variable; no need for a separate page

### Section 5: Footer
Repo link, last commit hash + date, simple contact.

## Voice & style — important

- **Don't rewrite `narrative.md`.** Paul's voice is the differentiator. Ingest it, render it, don't edit it.
- **Editorial typography**: serif body (something like Source Serif Pro, Crimson Pro, or Newsreader), monospace for code/data (JetBrains Mono, IBM Plex Mono). Big line-height (1.6–1.8). Wide gutters. Drop caps optional but on-brand.
- **Generous vertical rhythm**: lots of breathing room between sections. Don't pack things.
- **Images full-width or near-full-width**, with thin captions in muted color underneath. No frames or shadows on images — let them be photographs.
- **No animations on scroll** unless they genuinely serve. No parallax. No fancy transitions. Static is fine.
- **No emoji.** The voice is reflective; emoji breaks tone.
- **Tasteful color palette**: off-white background (not pure white), dark warm-gray text (not pure black). Accent color minimal — could be a deep red or warm amber pulled from the first_light.jpg lamp glow. Don't overdo it.

## Hosting — important

- **Vercel only.** Deploy from `site/` subfolder.
- **Do not host anything on the Jetson public-facing.** The Jetson is for compute, not for serving the site.
- **Do not expose Jetson via Tailscale Funnel / Cloudflare Tunnel / ngrok unless Paul explicitly asks.** When live demos are needed, use recorded video clips instead.
- **No live data fetched from Jetson by the site.** Site is static (or uses Vercel serverless functions for things that genuinely need them, but tonight's content has nothing that needs that).

## What to do first (your first session)

In order:

1. **Read** `narrative.md` and `docs/autofocus.md` end-to-end. You need to understand the voice and the technical story.
2. **Briefly check** `first_observations/first_observations_of_the_world.md`, `logs/01-setup.md`, `logs/02-csi-camera.md`, `logs/03-autofocus-investigation.md` — for additional context only.
3. **Verify Node version on the Mac** — `node --version`. Should be 20+ for current Next.js. Tell Paul if upgrade needed.
4. **Scaffold** the Next.js app at `site/` using `npx create-next-app@latest site --typescript --tailwind --app --eslint --src-dir=false --import-alias="@/*"` (verify these flags against the current `create-next-app` — Next.js evolves fast). Confirm with Paul before running.
5. **Install supporting deps**: `recharts`, `@next/mdx`, `@mdx-js/loader`, `@mdx-js/react`, possibly `gray-matter` for frontmatter, `next-mdx-remote` if you go that route. Decide MDX strategy with Paul before committing.
6. **Verify dev server runs locally** — `cd site && npm run dev` should serve a page on localhost:3000.
7. **Set up Vercel project** — guide Paul through `vercel link` from inside `site/`, set Root Directory in Vercel dashboard, deploy. He has a Vercel account already. Confirm `*.vercel.app` URL works before adding any real content.
8. **Land a placeholder version of `app/page.tsx`** that just renders "Hello — site coming soon" with the right typography. This is the v0 deploy. Confirm it ships to Vercel before going further.
9. **THEN start adding real content** — narrative MDX import, first hero, first images. Iterate.

**Do not** try to build everything in one push. The first deploy should be a hello-world. Each subsequent commit adds a layer.

## Things to absolutely avoid

- Do not modify any existing Jetson code (`detect_local.py`, `server.py`, `client.py`, `arducam_focus/`).
- Do not modify `narrative.md` — Paul writes that himself. You can READ it and IMPORT it into the site, but don't edit prose.
- Do not modify the existing `docs/*.md` files unless Paul asks.
- Do not SSH to the Jetson. The Jetson plays no part in tonight's work.
- Do not commit anything without explicit "go" from Paul. Show diffs first.
- Do not push to the GitHub remote without explicit "push" from Paul.
- Do not add a custom domain — `*.vercel.app` is fine.
- Do not pull any third-party UI library unless Tailwind alone proves insufficient. shadcn/ui is OK if needed for a specific primitive, but don't preemptively install it.
- Do not use `pnpm` or `yarn` — use `npm` for consistency unless Paul says otherwise.
- Do not add analytics, tracking, cookies, banners. The site is content, not commerce.
- Do not add a CMS. MDX files in the repo are the CMS.
- Do not over-engineer. If Tailwind utility classes do the job, don't write a CSS module.

## Where the project is in its bigger plan

For the full 15-evening master roadmap, hardware decisions, chosen use cases, and known-problem foresight, **see `docs/project_plan.md`**. That doc is the source of truth for everything project-scope.

Quick orientation:
- Step 1 (continuous autofocus) is ✅ done tonight (commits `aa42f0b`, `ed169cf`).
- Steps 2–15 still ahead.
- Site work is **interleaved** with the Jetson work — not bolted on at the end.
- Tonight's session is "site evening 1": scaffold Next.js + Tailwind + Recharts, deploy hello-world to Vercel.
- Each subsequent Jetson-side evening also gets 30–60 min for the site (writing the narrative entry, adding media).

## How Paul works

- He likes step-by-step explanations of what you're doing and why. Concept-first, then commands.
- He prefers editing locally on Mac, running on Jetson — but for site work, both editing and running are local on Mac.
- When you're about to do something with consequences (install global packages, deploy, push to GitHub, change project structure), pause and confirm.
- He pushes back when something feels off — when he does, take it seriously, don't defend the original plan.
- Long commands often get awkwardly wrapped in his terminal; prefer short commands or break long ones across multiple invocations.
- He'll often ask you to explain something at a 15-year-old level. Storytelling explanations welcome.
