# Ideas

The user's idea backlog. Work items come from here. Add new ideas at the bottom of the matching section; move shipped items to **Done** with the commit or milestone.

Tags: `[M1]` `[M2]` `[M3]` milestone, `[later]` unscheduled, `[?]` needs a decision from the user.

## Vision

A first-class VR experience set in a cyberpunk megacity. It starts as a single apartment (a living room with a large window onto the city) and grows zone by zone (hallway, elevator, streets, markets) until the user can walk outside.

Inspirations: The Fifth Element (Korben Dallas's apartment block, flying traffic), Star Citizen Area18, Cyberpunk 2077, Ghost in the Shell, Star Wars Coruscant, Elysium (the ring). Dense vertical city, neon, holographic ads, flying vehicles, rain, fog.

## Player and comfort

- [M1] XR rig with hands (XR Tools), smooth locomotion and smooth turning as defaults.
- [M1] Comfort options: teleport, snap turn, vignette. Off by default.
- [M1] Seated-first: eye-height calibration so a seated player sees from a standing adult's height; recenter action.
- [M1] Better sprint than holding stick-click. Default: push the stick past a threshold. Alternatives to try: arm-swing, toggle.
- [later] Gravity-glove flick (point, grip, flick the wrist) instead of pull-on-grip.
- [later] Lie down on the bed.
- [later] In-world settings panel for comfort options (no flat menus).
- [later] Hand tracking (Steam Frame) in addition to controllers.
- [later] Player avatar / body (IK from head and hands); prerequisite for a meaningful mirror.

## Interaction

- [M1] Everything interactable is physical: doors open by grabbing the handle, drawers slide, buttons get pressed. No "press A to open".
- [M1] One grabbable door (hinge).
- [M1] A ball that bounces, with impact sounds.
- [M1] A beverage can.
- [M1] A trash can that accepts objects tagged "trash".
- [M1] XR Tools setup: pickables, throwing, hinges, sliders, buttons, snap zones, impact sounds, tags.
- [later] Drawers and cabinets (sliders); wardrobe doors.
- [later] Use the Frame's left D-pad and bumpers (free for now): e.g. quick comfort toggles.
- [later] Bathroom: working tap/shower.
- [later] Working bathroom mirror. Makes most sense once there's a player avatar. Godot 4.7 has no hardware ray tracing, so the options to measure against the 90 FPS budget are: planar reflection via a SubViewport (renders the room again for both eyes, the expensive but correct one), a box-projected ReflectionProbe updated in real time, or SSR (can't show what's off screen). Good stress test for the budget.
- [M2] Physical light switches and dimmers per room, and/or a smart-home hub panel (could be the same in-world terminal as the world-state control panel).

## World state and weather

- [M2] Global world state: time of day, weather, automatic cycle at configurable speed, manual override.
- [M2] Day/night cycle with live lighting in the apartment.
- [M2] Weather: rain particles, rain-on-glass shader, wet surfaces, fog, lightning, sky crossfade, audio layers.
- [M2] World-state control panel in the apartment, e.g. a holographic wall terminal with physical buttons and sliders.
- [M2] Panorama variants: day, dusk, night, rain/fog, crossfaded by time and weather.
- [M2] Replace the procedural window pattern with prefiltered (mipmapped) facades/impostors; the remaining flicker in the headset is probably aliasing plus stream compression (D-023).

## City view

- [M1] Simple window view.
- [M2] Window view in layers: near facades as real, realistic geometry (simplified only where distance hides it), mid-distance as impostors/cards, far city as Blender-rendered panoramas.
- [later] Upgrade a layer to real geometry when its zone is built.
- [later] Flying traffic lanes (The Fifth Element), holographic ads, neon signage.
- [later] Elysium-style ring visible in the sky.

## Zones

- [M1] Apartment: living room with a large window.
- [M3] Hallway and elevator with seamless zone loading.
- [M3] Persistence: object state across zones, save/load.
- [later] Streets, markets, eventually walking outside.
- No loading screens, ever. Doors start background loading on approach; if not ready, a diegetic delay (e.g. an "ID scan") covers it. Elevator rides last as long as loading needs.

## Performance and tooling

- [M1] Scripted camera flythrough per zone that logs frame times and fails on budget regressions.
- [later] Shader precompile helper, if a perf report ever shows pipeline compiles on dropped frames. The M1 hitches (8 frames up to 58 ms) turned out to come from the machine, not compiles (D-025); the XR Tools demo also hitched when first picking up the scoped rifle.
- [later] Budget SubViewport cameras (scopes, mirrors, security monitors) explicitly.

## Rejected or low priority

- Grappling hook (least satisfying in the XR Tools demo; not a fit).

## Done

- Fridge (2026-09-28): realistic Blender fridge (Fable 5.1 won a blind A/B against Opus 5.5 by a hair), grab-to-open door with swing, magnetic seal, interior light, seal/close/hum sounds, cans on shelves and in door bins. Apartment doors swing on after release too.

- **Milestone 1 complete (2026-09-28).** In-headset perf: GPU p95 5.0 ms / 8 ms budget, CPU p95 1.7 ms, 0.45 % dropped frames (baseline `tools/perf/baselines/apartment-xr.json`).

- Feedback round 3 (2026-09-28): doors that open away can be pushed open (hand passes its own door); jump tucks and lands on tables; player body ignores cans and balls; interaction and skyline test suites. Skyline flicker deferred to the Blender/panorama rebuild (D-023).

- Feedback round 2 (2026-09-27): ranged grab actually pulls (own targeting, 6 m, line of sight); door collisions follow the door; all doors open; jump reaches the table; Steam Frame buttons: right A jump, B crouch, X sit, Y recenter; less skyline shimmer (measured).

- Feedback round 1 (2026-09-27): five-room apartment; visible ranged grab with highlight; door handles at 1.1 m; doors can't swing through the player; sit on sofa/bed; jump and crouch buttons; recenter confirmation; skyline window anti-aliasing; VS Code language server port.

- M1 scaffold (2026-09-27): XR rig with hands, smooth move/turn, stick-deflection sprint, teleport/snap/vignette options, hold-Y recenter; apartment blockout with window and hallway stub; grabbable door, bouncing ball, beverage cans, trash can; procedural skyline; perf flythrough.
