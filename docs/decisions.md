# Decisions

Short log of architectural decisions and why. Newest at the bottom. Supersede an entry by adding a new one that references it; don't rewrite history.

Format: `## D-NNN: Title (YYYY-MM-DD)`, then 2–5 lines: decision, why, consequences.

## D-001: Godot 4.7, Forward+, D3D12 (2026-09-27)

Godot 4.7.2 stable, Forward+ renderer, D3D12 driver on Windows. The 4.7.2 binary ships `XR_KHR_D3D12_enable`, so OpenXR works on D3D12. If SteamVR shows problems on D3D12 (black eyes, crashes, missing depth submission), switch `rendering/rendering_device/driver.windows` to `vulkan` and log it here.

## D-002: Godot MCP: godot-ai (2026-09-27)

[godot-ai](https://github.com/hi-godot/godot-ai), pinned in `.mcp.json` (`godot-ai==4.2.3`), editor plugin in `addons/godot_ai/`. Chosen in Milestone 0 over GDAI MCP and IvanMurzak's Godot-MCP: open source, captures the editor viewport, a scene camera and the running game's framebuffer, reads game/editor logs, and evaluates GDScript in the running game (used by the perf test). The `_mcp_game_helper` autoload must stay enabled for game capture and eval.

## D-003: Blender MCP: Blender Lab MCP server (2026-09-27)

The official [Blender Lab MCP server](https://www.blender.org/lab/mcp-server/), path supplied via `BLENDER_MCP_PATH` so the repo stays machine-independent.

## D-004: Godot XR Tools 4.6.0-dev1 (2026-09-27)

XR Tools 4.5.1 (latest stable) fails to parse on Godot 4.7 (`viewport_2d_in_3d.gd`: "Not all code paths return a value"). 4.6.0-dev1 fixes the 4.7 return-value issues and ran clean in the official demo on the Steam Frame. Installed into `addons/godot-xr-tools/` unmodified (its `plugin.cfg` still says 4.5.1; `VERSIONS.md` has the 4.6.0 notes). Switch to 4.6.0 stable when it ships. Don't patch the addon; wrap or extend it in `core/` instead.

## D-005: Jolt, 90 Hz physics, no V-Sync (2026-09-27)

Jolt physics, `physics_ticks_per_second=90` to match the display, so held objects and hands move in lockstep with frames and physics interpolation isn't needed. V-Sync off: the OpenXR runtime paces frames, and V-Sync on the desktop mirror window would add latency. If the headset runs at 120 Hz later, raise the tick rate to match (or enable physics interpolation) and re-run the perf test.

## D-006: MSAA 4x, depth submission (2026-09-27)

Start with MSAA 4x (3D), no TAA/FSR (smearing and ghosting are worse in VR). `xr/openxr/submit_depth_buffer=true` so SteamVR can use depth for reprojection. Both are to be validated against the budget in the first perf run.

## D-007: Git LFS for all binaries, including addons (2026-09-27)

`.gitattributes` routes 3D, image, audio, video, font and binary Godot resources (`.res`, `.scn`) to LFS everywhere, addons included, so binaries never land in normal Git history. Text resources (`.tscn`, `.tres`, `.gdshader`, `.gltf`) stay in Git and are diffable. Prefer text formats for everything we author.

## D-008: World scale and coordinates (2026-09-27)

1 unit = 1 m, Y up, glTF/Godot conventions (-Z forward). The apartment floor is at y = 0 and is the world origin, to keep float precision best where the player spends the most time. The apartment sits 180 m above street level, so the street plane is y = -180. The apartment's main window faces -Z ("north" by convention). Every zone is authored in world coordinates at its real position; the zone loader never offsets zones. Distant layers seen from the window must use the same frame so they line up with zones built later.

## D-009: Locomotion defaults: smooth move and smooth turn, seated-first (2026-09-27)

The user plays mostly seated and isn't prone to motion sickness. Defaults: smooth (direct) movement and smooth turning, no teleport. Teleport, snap turn and the comfort vignette are available as options. Stick-click sprint felt tedious, so sprint is automatic past a stick-deflection threshold. Design for seated play: eye-height calibration to a standing adult, a recenter action, and no interactable that requires reaching the floor.

## D-010: VoxelGI first for lighting (2026-09-27)

The apartment needs a live day/night cycle, so sun-dependent lighting can't be baked into static lightmaps. Start with one VoxelGI per zone (baked geometry, real-time light updates), with ReflectionProbes for glossy surfaces. Measure its GPU cost in the first perf run; if it blows the budget, fall back to LightmapGI for sun-independent interior lights plus real-time sun and sky light.

## D-011: Vulkan instead of D3D12 (2026-09-27, supersedes D-001's driver choice)

With SteamVR running, D3D12 logged `_texture_create_shared_from_slice: owner_info.allocation` errors every frame (creating texture slices from the OpenXR swapchain) and the captured XR frame was black. Vulkan starts the same session cleanly. Vulkan is Godot's most-tested OpenXR path, so the driver is Vulkan (the project default, so `project.godot` has no explicit driver line). Retry D3D12 after a Godot update if there's a reason to.

## D-012: VoxelGI rejected for stereo; no GI in M1 (2026-09-27, supersedes D-010)

Measured in the apartment flythrough at the real per-eye target (2 × 2644²): baked VoxelGI (subdiv 64, half-resolution GI) raises GPU p95 from 5.8 ms to 11.6 ms, more than the whole frame. The node and its baked data stay in the apartment scene, hidden, so the cost can be re-measured later. M1 lights with direct lights, sky ambient and one ReflectionProbe. For M2's day/night cycle, measure these in order: LightmapGI for sun-independent interior bounce plus real-time sun and sky; SDFGI at the lowest settings; a scripted fill light driven by world state.

## D-013: Perf test runs in XR or as a desktop approximation (2026-09-27)

`tools/perf` runs the zone's PerfPath either in the headset (real stereo, paced by SteamVR) or with `--xr-mode off`, rendering a 5288×2644 SubViewport (both eyes side by side at SteamVR's 100% render target for the Steam Frame). Desktop mode checks only GPU/CPU cost and scene counts, not frame pacing. It isn't multiview, so it overestimates culling/CPU cost slightly and matches per-pixel cost well. Claude runs desktop mode on every perf-relevant change; the user runs XR mode before a milestone is called done.
