# Handoff — jetson-yolo-stream — 2026-04-30

Site evening 1: scaffolded the portfolio site at `site/` (Next.js 16 + Tailwind v4 + MDX), deployed to Vercel, then layered on the editorial first cut — Newsreader serif typography, hero + metadata strip + narrative article rendering both existing journal entries verbatim from `narrative.md`. Live at https://paulsong-jetson-vision.vercel.app. Two commits this session, neither pushed. Also stood up a `/handoff` user-level skill (this file is its first output) and saved a Vercel-gotchas memory file.

## Working tree state

- Branch: `main` · 4 commits ahead / 0 behind `origin/main`
- Recent commits (newest first):
  - `2ccb41a` Render editorial first cut — Newsreader serif, MDX narrative, hero + metadata strip
  - `3c4dea7` Scaffold portfolio site — Next.js 16 + Tailwind v4 + MDX, deployed to Vercel
  - `ed169cf` Add one-shot autofocus — Tenengrad hill-climb on AK7375
  - `aa42f0b` Add manual autofocus — AK7375 wire protocol via i2ctransfer
- Uncommitted (pre-session, Paul's authored content):
  - `CLAUDE.md` (M) — minor tweaks referencing the new planning docs
  - `docs/project_plan.md` (??) — 15-evening master roadmap
  - `docs/site_plan.md` (??) — site-specific handoff doc that drove this session
  - `media/` (??) — autofocus before/after photos + `search_log.csv`
- **Pushed?** No. Deliberate — site is still a placeholder + two existing chapters; no point advertising a thin portfolio. Push after the April 30 chapter and the BeforeAfter / FocusChart components land.

## Live artifacts

- https://paulsong-jetson-vision.vercel.app — production deployment, dpl-id `dpl_JCPURTfUtiGMvLqoBfShKjMtALDA` for the editorial cut.
- Vercel project: `paulsong-jetson-vision` under scope `psong11s-projects` (Pro plan).
- Local link: `site/.vercel/project.json` (gitignored). Project ID `prj_27pztr79HYIEpBR4okj76Df9PE3S`.

## What's next

1. **Write the April 30 narrative entry** in `narrative.md` — the autofocus victory chapter ("The Door Opens" or similar). Writing-mode task, Paul-driven. Do this while the texture of the work is still fresh.
2. **Mirror it into `site/content/narrative.mdx`** as a third `## ...` section, then build:
   - `<BeforeAfter>` slider component for `media/autofocus_2026-04-30/before_dac0000.jpg` ↔ `after_dac0800.jpg`. Copy the JPGs into `site/public/images/autofocus_2026-04-30/` first.
   - `<FocusChart>` Recharts line graph reading `search_log.csv` (34 rows, two passes — coarse + fine). Annotate the peak.
3. **Push to remote** once the third chapter is on the page. That's the bar for advertising the URL publicly.
4. **Step 2 of 15** in `docs/project_plan.md`: object tracking via `model.track(persist=True)` in `detect_local.py`. Cracks open the "teach it to remember" arc that April 12 promised.
5. **Tiny housekeeping**: commit the four uncommitted pre-session files in a separate "Add roadmap, site plan, and autofocus media" commit. Five-minute task, do it whenever.

## Carry-forward context

Things that won't be obvious from the code or git log and would otherwise get re-debugged:

- **Vercel project setup quirks already paid for once** — saved in memory at `vercel_account_gotchas.md` (auto-loaded). Specifically: `ssoProtection` was disabled via API on this project (Pro default is "all *.vercel.app URLs locked"), and `framework: "nextjs"` was PATCHed onto the project record (because `vercel project add` doesn't auto-set framework, which makes deploys 404 even when the build succeeds). Both fixes persist. Don't repeat the diagnosis.
- **Vercel CLI was updated to 53.0.1 globally** earlier this session. No action needed; just don't be surprised if next session sees a different version than your training data expects.
- **Typography stack**: Newsreader (variable serif body) + JetBrains Mono (mono accents), both via `next/font/google`. CSS variables wired into Tailwind v4 via `@theme inline` in `site/app/globals.css`. Reading column wraps at `max-w-[68ch]`. Stone palette only, no dark mode, no accent color yet.
- **MDX wiring**: `@next/mdx` + `remark-gfm`, configured in `site/next.config.ts`. Typography overrides for h1-h3, p, ul, ol, blockquote, code, pre, hr, table all live in `site/mdx-components.tsx`. The first_light.jpg appears twice deliberately — once as hero cover, once at the climactic narrative moment — both via explicit `<Image>` tags.
- **New memory files this session**: `vercel_account_gotchas.md` (in `MEMORY.md` index).
- **New user-level skill this session**: `/handoff` at `~/.claude/commands/handoff.md`. This file is its first output.
- **Strategic decision deferred**: connecting Vercel to GitHub for auto-deploy on push. Skipped intentionally — staying CLI-only until content stabilizes, so we don't fire deploys on routine commits.

## Open questions

- Final font choice. Newsreader is in place; Paul may want to A/B against Source Serif 4 or Crimson Pro after eyeballing the live site.
- Whether the hero image should go wider than the `max-w-[68ch]` reading column (NYT-style full-bleed) or stay column-width as it currently is.
- Accent color — none yet. Possible candidates: deep amber pulled from `first_light.jpg`, or a desaturated rust. Defer until the autofocus chapter where the accent has a narrative reason to exist.

---

### Auto-loaded on next session start

- `~/.claude/CLAUDE.md` — global rules (memory self-audit etc.)
- `CLAUDE.md` (project) — file map, current state, SSH rules, hardware
- `~/.claude/projects/-Users-paulsong-Documents-learn-jetson-yolo-stream/memory/MEMORY.md` — index of saved memory files including the new Vercel gotchas
- `site/AGENTS.md` + `site/CLAUDE.md` — Next.js 16 warning to read local docs

Read on demand (referenced from CLAUDE.md, not auto-loaded): `docs/project_plan.md`, `docs/site_plan.md`, `narrative.md`, `docs/autofocus.md`, `docs/ssh_jetson.md`.

### To resume

Open a fresh Claude Code terminal in this repo. After auto-loaded context, paste this as your first message:

> Picking up jetson-yolo-stream. Read `.claude/handoffs/2026-04-30-portfolio-site-launch.md` first to catch up on the previous session. Then propose your first concrete steps and wait for my go.
