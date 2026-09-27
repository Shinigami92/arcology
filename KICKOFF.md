# Kickoff: Arcology (VR)

You are setting up a new long-running VR project in this folder. This file is the brief; turn it into a working project foundation, then replace this file with the permanent project docs described below.

## Vision

A first-class VR experience set in a cyberpunk megacity. It starts as a single apartment (living room with a large window onto the city) and grows zone by zone over time — hallway, elevator, streets, markets — until the user can walk outside.

Inspirations: The Fifth Element (Korben Dallas's apartment block, flying traffic), Star Citizen Area18, Cyberpunk 2077, Ghost in the Shell, Star Wars Coruscant, Elysium (the ring). Dense vertical city, neon, holographic ads, flying vehicles, rain, fog.

## Hard constraints

- **Engine:** Godot 4 (latest stable 4.x), Forward+ renderer, OpenXR.
- **Target:** Valve Steam Frame, streamed from a Windows PC with an RTX 4080 Super via SteamVR. PC build only (no standalone/ARM build).
- **Performance:** minimum 90 FPS in stereo, always. Every feature must respect the budget; measure, don't guess.
- **Workflow:** Claude Code does nearly all the work. The user supplies ideas, guides direction and tests in the headset. Prefer text-based, diffable assets and automation over manual editor steps. When a manual step is unavoidable, give the user exact, short instructions.

## Tooling

- **Blender MCP** for modeling, texturing, baking, and pre-rendering city panoramas (Cycles). Blender source files live in `blender/`, exported as `.glb` into `assets/`.
- **A Godot MCP with screenshot capture** (e.g. GDAI MCP or IvanMurzak's Godot-MCP) so you can visually verify your own work. Evaluate the options and recommend one before installing.
- **Git with Git LFS** for binaries (`.blend`, `.glb`, textures, audio).
- **Custom subagents** in `.claude/agents/` with explicit `model` and effort in their frontmatter (verify the exact frontmatter field names in the Claude Code docs first). At minimum:
  - `blender-artist` — 3D asset creation via Blender MCP; highest quality model and high effort.
  - `godot-dev` — scenes, scripts, shaders, integration.
  - `perf-reviewer` — reviews changes against the performance budget.
  Set them up so the user can easily A/B the model (`opus` vs `fable`) and effort on the same asset.

First, check what's installed (Godot version, Blender version, Git LFS, which MCPs are configured) and report what's missing. Ask before installing anything.

## Architecture

```
CLAUDE.md               # conventions, perf budgets, "how to add a zone/prop/interactable" recipes
docs/
  style-guide.md        # palette, neon colors, materials, lighting mood, inspirations
  ideas.md              # the user's idea backlog; work items come from here
  decisions.md          # short log of architectural decisions and why
blender/                # .blend sources (LFS)
assets/                 # shared .glb, textures, materials, shaders, audio, signage
core/
  player/               # XR rig, hands, smooth + teleport locomotion, snap turn, comfort vignette
  interaction/          # Godot XR Tools setup: pickables, throwing, hinges, sliders, buttons, snap zones, impact sounds, tags (e.g. "trash")
  world_state/          # global autoload: time of day, weather, auto cycle, manual override
  weather/              # rain particles, rain-on-glass shader, wet surfaces, fog, lightning, sky crossfade, audio layers
  zones/                # zone loader: threaded preload, door/elevator transitions, unload
  persistence/          # object state across zones, save/load
zones/
  apartment/            # first zone
tools/                  # Blender→glb export script, perf flythrough test, shader precompile helpers
```

### Principles

- **Zones are self-contained scenes** with a defined entry point, their own GI/probes, and only shared assets from `assets/`. The world uses one consistent scale and coordinate system so future zones line up with what's visible from the window.
- **Everything interactable is physical.** Doors open by grabbing the handle, drawers slide, buttons get pressed. No "press A to open".
- **Physics:** Jolt, physics tick at 90 Hz to match the display.
- **Lighting:** the apartment must support a live day/night cycle, so no static-only lightmaps for sun-dependent lighting. Start with VoxelGI (baked geometry, real-time light updates) and validate its cost early.
- **Window view in layers:** near facades as real low-poly geometry, mid-distance as impostors/cards, far city as Blender-rendered panoramas (day, dusk, night, rain/fog variants) crossfaded by time and weather. Layers get upgraded to real geometry when the corresponding zone is built.
- **No loading screens, ever.** Doors trigger background loading on approach; if not ready, a diegetic delay (e.g. "ID scan") covers it. Elevator rides last as long as loading needs. Precompile shaders and add nodes incrementally to avoid hitches.
- **World state:** default is an automatic day/night cycle with weather changes at configurable speed; the user can override via an in-world control panel (e.g. a holographic wall terminal with physical buttons/sliders).
- **Performance check:** a scripted camera flythrough per zone that logs frame times and fails on budget regressions. Define per-zone budgets (draw calls, triangles, lights, GI cost) in `CLAUDE.md`.

## Milestone 1 (this session and the next few)

1. Git + LFS, Godot project with OpenXR, Forward+, Jolt, 90 Hz physics.
2. MCP setup (Blender, Godot), custom subagents.
3. `CLAUDE.md`, `docs/style-guide.md`, `docs/ideas.md` (seed it with everything in this brief), `docs/decisions.md`.
4. Core: XR rig with hands, locomotion + comfort options, XR Tools interaction.
5. Apartment blockout at correct VR scale, basic lighting, simple window view.
6. Interactables: one grabbable door, a ball (bounce + impact sounds), a beverage can, a trash can that accepts "trash".
7. Perf flythrough script; confirm 90 FPS headroom.

Milestone 2: day/night cycle, weather system, world-state control panel, panorama variants.
Milestone 3: hallway + elevator with seamless zone loading, persistence.

Work in small, verifiable steps and commit after each. Tell the user when something is ready to test in the headset and what to look for.

When Milestone 1 is scaffolded, delete this `KICKOFF.md`; its content should live on in `CLAUDE.md` and `docs/`.
