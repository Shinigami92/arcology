# Arcology

A VR experience set in a dense, vertical cyberpunk megacity. It starts in a single apartment with a large window onto the city and grows zone by zone (hallway, elevator, streets, markets) until you can walk outside. Inspired by **The Fifth Element**, **Star Citizen's Area18**, **Cyberpunk 2077**, **Ghost in the Shell**, **Coruscant** and **Elysium**: neon, holographic ads, flying traffic, rain and fog.

> **Status: very early development.** Milestone 1: a five-room blockout apartment you can walk around in VR, with doors, a ball, cans, a trash can, and a sofa and bed to sit on.

## Tech

- **Engine:** Godot 4.7, Forward+ renderer (Vulkan), Jolt Physics at 90 Hz, OpenXR, [Godot XR Tools](https://github.com/GodotVR/godot-xr-tools).
- **Target:** Valve Steam Frame, streamed via SteamVR from a Windows PC (RTX 4080 Super class). PC build only.
- **Performance:** 90 FPS in stereo, always.
- **Assets:** modeled and rendered in Blender, exported as `.glb`.

## Requirements

- [Godot 4.7](https://godotengine.org/download) (standard build, not .NET)
- [SteamVR](https://store.steampowered.com/app/250820/SteamVR/) set as the active OpenXR runtime, plus a headset
- Optional, for AI-assisted development with [Claude Code](https://claude.com/claude-code):
  - [uv](https://docs.astral.sh/uv/)
  - [Blender 5.1+](https://www.blender.org/download/) with the [Blender Lab MCP add-on](https://www.blender.org/lab/mcp-server/)

## Setup

Machine-specific paths live in environment variables, never in the repo:

| Variable | Used by | Example |
|---|---|---|
| `GODOT4_EDITOR` | VS Code [godot-tools](https://marketplace.visualstudio.com/items?itemName=geequlim.godot-tools) (`.vscode/settings.json`) | `E:\Godot\v4.7.2-stable\Godot_v4.7.2-stable_win64.exe` |
| `BLENDER_MCP_PATH` | Blender MCP server (`.mcp.json`) | path to the `mcp/` folder of a [blender_mcp](https://projects.blender.org/lab/blender_mcp) clone |

On Windows, set them once per user, then restart VS Code and your terminal:

```powershell
setx GODOT4_EDITOR "E:\Godot\v4.7.2-stable\Godot_v4.7.2-stable_win64.exe"
setx BLENDER_MCP_PATH "D:\path\to\blender_mcp\mcp"
```

## How to run

1. Start SteamVR and connect the headset.
2. Open `project.godot` in Godot 4.7.
3. Press **F5**.

Controls (Steam Frame; other controllers in [CLAUDE.md](./CLAUDE.md#controls)): left stick moves (push fully forward to sprint), right stick turns, grip grabs (point at farther objects and grip to pull them in), right **A** jumps, **B** toggles crouch, **X** sits down on the sofa or bed and gets up again, hold **Y** for a second to recenter and recalibrate your eye height (works seated).

### Performance test

```powershell
& $env:GODOT4_EDITOR --path . -- --perf=apartment               # in the headset
& $env:GODOT4_EDITOR --path . --xr-mode off -- --perf=apartment # desktop approximation
```

Prints `PERF: PASS` or `PERF: FAIL` and writes a JSON report to `tools/perf/results/`. Budgets are in `tools/perf/budgets.json`.

## AI tooling

`.mcp.json` registers two MCP servers for Claude Code:

- **blender**: the [Blender Lab MCP server](https://www.blender.org/lab/mcp-server/). Blender must be running with the add-on enabled and online access allowed.
- **godot-ai**: [godot-ai](https://github.com/hi-godot/godot-ai), with its editor plugin in `addons/godot_ai/`. The Godot editor must be open. Don't use the dock's **Configure** button: it writes an absolute `uvx` path into `.mcp.json`.

## Docs

- [CLAUDE.md](./CLAUDE.md): conventions, performance budgets, recipes
- [docs/ideas.md](./docs/ideas.md): backlog
- [docs/style-guide.md](./docs/style-guide.md): look and feel
- [docs/decisions.md](./docs/decisions.md): decision log

## License

[MIT](./LICENSE)
