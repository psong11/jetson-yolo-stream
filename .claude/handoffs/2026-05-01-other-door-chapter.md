# Handoff — jetson-yolo-stream — 2026-05-01

Site evening 2: shipped the third narrative chapter ("The Other Door") covering the autofocus victory. Wrote and rewrote the prose twice for voice (cut "ugly pictures" entirely, pulled back from arty/preachy phrasing per Paul's tasteful-not-cringey brief), built two new MDX-registered components — `<BeforeAfter>` drag-slider and `<FocusChart>` Recharts two-pass viz — and wired them into the chapter. Hit a tsc strictness diff between dev and prod, fixed it, deployed to Vercel production, and connected the project to GitHub for auto-deploy on future pushes. Three commits this session, all pushed.

## Working tree state

- Branch: `main` · 0 commits ahead / 0 behind `origin/main`
- Recent commits (newest first):
  - `30129f5` Loosen FocusChart Tooltip callback types for prod build
  - `c658feb` Render 'The Other Door' chapter — autofocus narrative + interactive components
  - `363c083` Add roadmap, site plan, and autofocus media
  - `2ccb41a` Render editorial first cut — Newsreader serif, MDX narrative, hero + metadata strip
  - `3c4dea7` Scaffold portfolio site — Next.js 16 + Tailwind v4 + MDX, deployed to Vercel
  - `ed169cf` Add one-shot autofocus — Tenengrad hill-climb on AK7375
- Uncommitted: only `.claude/` (machine-local settings + handoffs — intentionally excluded)
- **Pushed?** Yes, all three. Working tree clean against origin.

## Live artifacts

- https://paulsong-jetson-vision.vercel.app — production, dpl `dpl_6zBH7dQKrVQesVPhumaHo91WN1Pd`. Third chapter live.
- Vercel project `paulsong-jetson-vision` (scope `psong11s-projects`, Pro) is now **connected to GitHub** — `https://github.com/psong11/jetson-yolo-stream`. Pushes to `main` auto-deploy to production going forward.

## What's next

1. **Step 2 of 15** in `docs/project_plan.md`: object tracking via `model.track(persist=True)` in `detect_local.py`. Cracks open the "teach it to remember" arc that April 12's chapter promised. This is the obvious next horizon.
2. **Continuous autofocus** — one-shot AF works as of last session; the next problem is live drift detection + correction without being asked. Needs a motion-stable metric, hysteresis to prevent hunting, and a way to disambiguate "world changed" from "lens drifted." Loosely related to step 2, since tracking gives a target box whose sharpness can be the AF feedback signal.
3. **Watch the first auto-deploy.** First commit-to-main after this session will trigger an unattended Vercel build; check the deployment in the Vercel dashboard if anything looks off afterward. Consider configuring an "Ignored Build Step" if rebuilds on non-`site/` commits get noisy.

## Carry-forward context

- **Vercel auto-deploy is now ON.** Connected via `vercel git connect https://github.com/psong11/jetson-yolo-stream --yes` from `site/`. Every push to `main` will rebuild. Defaults: production branch = `main`. CLI deploys (`vercel deploy --prod`) still work alongside.
- **Vercel `rootDirectory` is set to `site`.** First auto-deploy (commit `4fdcbaa`) errored because the project's Root Directory was unset — `next build` ran from repo root and couldn't find `app/`. CLI deploys worked because they upload from cwd; Git integration doesn't have that context. Fixed by PATCHing the project via the Vercel API: `curl -X PATCH https://api.vercel.com/v9/projects/prj_27pztr79HYIEpBR4okj76Df9PE3S?teamId=team_AK01fQad3ATKWYOiMYBZFTQu -H "Authorization: Bearer $TOKEN" -d '{"rootDirectory":"site"}'`. The setting persists on the Vercel side; future pushes deploy correctly. Token is at `~/Library/Application Support/com.vercel.cli/auth.json`. Add this to the Vercel-account-gotchas memory if it bites again on a new project.
- **Vercel CLI dropped to 51.6.1.** When the previous session deployed, the global CLI was 53.0.1. Tonight's `vercel deploy` reported 51.6.1 — npm/system upgrade churn, harmless, just don't be confused by version drift.
- **Dev vs prod TypeScript strictness gap.** `next dev` (Turbopack) accepted narrow type annotations on Recharts Tooltip callbacks (`labelFormatter`, `formatter`) that `next build` rejected via tsc. The fix landed in `30129f5`. **Run `npx tsc --noEmit` in `site/` before any future deploy** — auto-deploy now means a bad type error pushes a broken build. Or add a pre-push hook later.
- **Recharts SSR warning is benign.** Console emits "width(-1) and height(-1) of chart should be greater than 0" on first render — known recharts issue with `getBoundingClientRect` returning -1 during SSR measurement. The actual SVG markup ships correctly and renders client-side. Don't chase it.
- **`<BeforeAfter>` and `<FocusChart>`** are registered globally via `site/mdx-components.tsx` — usable in any MDX file without import. Both are client components.
- **Image asset duality.** Photos for narrative chapters live both at `media/<topic>_<date>/` (canonical, used by `narrative.md` raw markdown) and `site/public/images/<topic>_<date>/` (served by Next, used by `site/content/narrative.mdx`). Same files, two locations. Established for chapter 1 (`first_observations/` + `site/public/images/`) and continued here.
- **Two new memory files this session**: `narrative_self_image.md` (no "ugly"/self-deprecating descriptors anywhere in narrative.md or site prose), and an extended bullet in `narrative_voice.md` (don't telegraph metaphors with "and elsewhere"-style pointers, no anthropomorphizing hardware). Both indexed in `MEMORY.md`. The autofocus_deferred.md memory was also updated to mark one-shot AF as done and clarify continuous AF is the remaining horizon.
- **Voice rewrite happened twice tonight.** Paul flagged "don't say I'm ugly" mid-draft and later asked for a tasteful-not-cringey rebuild. The shipped version dropped "ugly pictures of people"/"aesthetic failure"/"my face dissolved into a soft cloud" entirely, cut "and elsewhere"-style metaphor pointers, collapsed a standalone reflection beat into one inline sentence. Don't reintroduce these patterns in chapter 4.

## Open questions

- Whether to enable Vercel's "Ignored Build Step" so pushes outside `site/` don't trigger rebuilds. Defer until it gets annoying.
- Continuous AF metric choice (Tenengrad vs. Laplacian vs. something gradient-of-gradient) and how to drive it from the YOLO target box. Open until step 2 lands.
- Whether to start writing chapter 4 *during* the object-tracking work (live build journal) or after (reflective).

---

### Auto-loaded on next session start

- `~/.claude/CLAUDE.md` — global rules (memory self-audit etc.)
- `CLAUDE.md` (project) — file map, current state, SSH rules, hardware
- `~/.claude/projects/-Users-paulsong-Documents-learn-jetson-yolo-stream/memory/MEMORY.md` — index including the two new entries this session
- `site/AGENTS.md` + `site/CLAUDE.md` — Next.js 16 warning to read local docs

Read on demand (referenced from CLAUDE.md, not auto-loaded): `docs/project_plan.md`, `docs/site_plan.md`, `narrative.md`, `docs/autofocus.md`, `docs/ssh_jetson.md`.

### To resume

Open a fresh Claude Code terminal in this repo. After auto-loaded context, paste this as your first message:

> Picking up jetson-yolo-stream. Read `.claude/handoffs/2026-05-01-other-door-chapter.md` first to catch up on the previous session. Then propose your first concrete steps and wait for my go.
