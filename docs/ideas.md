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
- [later] Hand tracking (Steam Frame) in addition to controllers. The avatar's skeleton already carries the OpenXR hand joints (`<Side>Palm`, metacarpals, tips; D-037), so `XRHandModifier3D` can drive it; verify the joint orientations in the headset first.
- [M2] Player avatar stage 4: Silena's head, face and hair (`docs/characters/silena_vesper.md`). The current `HeadMesh` is a shadow-only placeholder (MPFB head, closed eyelids, a simple hair volume). Wanted: violet eyes and smoky makeup, the violet filigree markings on cheek, temple and neck, the messy updo with loose strands (hair cards), the dangling earring, the necklace. Pairs with the working mirror: then `HeadMesh` and `Collar` switch from shadows-only to render layers hidden only from the player's own camera (D-041).
- [later] Avatar polish (artist's second-pass list): the front of the armholes when reaching forward (sleeve folds into the coat; corrective weights or a helper bone), five small folded faces at the back of the shoulders (a light speck), sharper coat textures (the vine is soft at ~1.2 px/mm; split front/back atlases), notched lapel and collar shaping, a real heel block on the boots, an elbow helper bone for full bends, a second forearm twist bone for wrist rolls beyond 100°. Arm length is 1–2 cm long (negotiable).
- [later] Per-object grab poses for the avatar's hands: the hand wraps a door lever, a can, the shower head instead of the generic fist. XR Tools pose areas swap in their own animations (wrong bones), so this needs avatar poses per grip type first (D-041).
- [later] Seated or standing play mode (option in the settings panel). The avatar stands and walks either way; the user plays seated but is fine with a standing body (VRChat habit).
- [M2] Footstep sounds while walking (smooth locomotion and real steps), chosen by the floor under the player: vinyl, carpet, concrete, later street surfaces; quieter or none while seated. The avatar's `FootSteps` (D-042) knows when and where each foot lands: trigger the sound on each plant, louder when faster.

## Interaction

- [M1] Everything interactable is physical: doors open by grabbing the handle, drawers slide, buttons get pressed. No "press A to open".
- [M1] One grabbable door (hinge).
- [M1] A ball that bounces, with impact sounds.
- [M1] A beverage can.
- [M1] A trash can that accepts objects tagged "trash".
- [M1] XR Tools setup: pickables, throwing, hinges, sliders, buttons, snap zones, impact sounds, tags.
- [later] Drawers and cabinets (sliders); wardrobe doors. The fridge's crisper drawer is a separate object ready to slide; first lower its front panel, which reaches 6 mm into the cover trim when closed (see `blender/props/fridge/fridge_common.py`).
- [later] Use the Frame's left D-pad and bumpers (free for now): e.g. quick comfort toggles.
- [later] Bathroom: working tap/shower.
- [later] Impact sounds per surface: a falling or thrown object sounds different on vinyl, carpet (muffled), concrete and furniture. Needs a surface tag on static bodies (e.g. a group or metadata per floor material, set by the apartment generator) that `ImpactSound` looks up on contact, plus sound sets per object and surface.
- [later] Door hardware: levers press down while grabbed (latch: the door opens only with the lever down), bathroom thumb-turn and entrance deadbolt lock the door, smart-lock LED red/green; latch and deadbolt sounds. The glbs already have the levers and turns as separate parts on their axes (D-035).
- [later] Ceiling trim: maybe a shadow gap with an LED strip. Bathroom wall finish (tiles or a wet-room skirting).
- [later] Working bathroom mirror. The avatar exists now (D-041); for her to show in it, the head needs stage 4 and render layers instead of shadows-only. Godot 4.7 has no hardware ray tracing, so the options to measure against the 90 FPS budget are: planar reflection via a SubViewport (renders the room again for both eyes, the expensive but correct one), a box-projected ReflectionProbe updated in real time, or SSR (can't show what's off screen). Good stress test for the budget.
- [M2] Physical light switches and dimmers per room, and/or a smart-home hub panel (could be the same in-world terminal as the world-state control panel).
- [M2] Windows (D-033): tilt vent in the bedroom, motorized shades and smart-glass tint per room via a wall panel, HUD readout on the living room glass. Done on placeholders; the artist's frame/sash/panel glbs drop in by rerunning `tools/props/window.py`.
- [M2] Window HUD: drive it from WorldState (time, temperature, weather) once that exists; maybe more readouts (news ticker, messages).

## World state and weather

- [M2] Global world state: time of day, weather, automatic cycle at configurable speed, manual override.
- [M2] Day/night cycle with live lighting in the apartment.
- [M2] Weather: rain particles, wet surfaces, fog, lightning, sky crossfade, audio layers. Rain on the glass is done (D-034); the weather system drives it through `RainOnGlass.set_rain()` and replaces the living room's temporary RAIN button.
- [later] Rain on glass: wind-blown slanted runners, drops gathering on the sill and dripping, splashes on the stone sill outside the bedroom vent; better rain sounds than the synth placeholders.
- [M2] World-state control panel in the apartment, e.g. a holographic wall terminal with physical buttons and sliders.
- [M2] Panorama variants: day, dusk, night, rain/fog, crossfaded by time and weather.
- [M2] Replace the procedural window pattern with prefiltered (mipmapped) facades/impostors; the remaining flicker in the headset is probably aliasing plus stream compression (D-023).

## City view

- [M1] Simple window view.
- [M2] Window view in layers: near facades as real, realistic geometry (simplified only where distance hides it), mid-distance as impostors/cards, far city as Blender-rendered panoramas. Near ring done (D-045): ten Blender towers; the far city repeats them (D-046). Next: more tower variety (types, heights, wider footprints for the far ring), then the panorama.
- [M2] City life on the towers: blink the `<tower>_blink` meshes (warning and pad lights), animate the spires' `_ad<n>` panels (unshaded, scanlines, flicker), scale the city materials' emission with the day/night cycle.
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
- [M2] Refresh the perf baselines with the avatar: the desktop baseline (`tools/perf/baselines/apartment-desktop-approx.json`) and the zone table in CLAUDE.md predate it (last desktop runs: GPU p95 ~5.4 ms, 393 draw calls at peak); then an XR perf run in the headset (the user).
- [later] Faster interaction tests: with `--fixed-fps 90 --disable-vsync` the full suite takes ~17 s instead of ~87 s, but `HingeSwing`/`SliderSwing` measure release speed with the real clock (`Time.get_ticks_usec`); move them and the tests' throws onto engine time first. Waiting until things stop moving instead of fixed frame counts would save another ~13 s.

## Rejected or low priority

- Grappling hook (least satisfying in the XR Tools demo; not a fit).

## Done

- Player avatar stages 1–3 (2026-10-03/04): the user's Shadowrun character Silena Vesper as the player's body (D-037), built on an MPFB2 base: gloved hands with per-finger curl on the control each finger rests on (D-038, D-039), coat sleeves with arm IK (D-040), the full body on one skeleton with head/spine/arm/leg IK (D-041), procedural stepping and seated poses (D-042, D-043; "probably the best VR leg steps I ever experienced"), coat and belt items on spring bones (D-044). Interaction tests now run by group (`--only=avatar`).

- Skirting boards (2026-10-01): painted skirting along every wall, wrapping the archways and butting the door casings, swept in Blender along runs the apartment generator computes (D-036).

- Surfaces and doors (2026-10-01): tileable vinyl, carpet, polished concrete and plaster on the apartment shell (D-035); realistic interior doors (bathroom with a privacy thumb-turn) and a security entrance door with peephole, unit plate and smart-lock LED, each with its own frame.

- Rain on the glass (2026-09-30): Heartfelt-style beads, runners with trails and a wet mist on every window, drops refracting the city through the screen texture, wetness that lingers and dries after the rain, patter on the glass and louder rain through the open vent; temporary RAIN button and `--rain` (D-034).

- Windows (2026-09-30): procedural windows from shared JSON specs (D-033): floor-to-ceiling living room window with a glass HUD, bedroom tilt vent with city noise, kitchen window on a 0.9 m sill; motorized shades, smart-glass tint and LED channels per room, all on a physical wall panel; tint and shades darken the room.

- Sofa (2026-09-28): realistic three-seater (Opus 5.5 won the blind A/B for texture realism) with two pickable throw pillows; Fable 5.1's boucle sofa kept as `sofa_boucle` for other apartments. Shared Blender toolkit gained soft-goods geometry and fabric layers.

- Fridge (2026-09-28): realistic Blender fridge (Fable 5.1 won a blind A/B against Opus 5.5 by a hair), grab-to-open door with swing, magnetic seal, interior light, seal/close/hum sounds, cans on shelves and in door bins. Apartment doors swing on after release too.

- **Milestone 1 complete (2026-09-28).** In-headset perf: GPU p95 5.0 ms / 8 ms budget, CPU p95 1.7 ms, 0.45 % dropped frames (baseline `tools/perf/baselines/apartment-xr.json`).

- Feedback round 3 (2026-09-28): doors that open away can be pushed open (hand passes its own door); jump tucks and lands on tables; player body ignores cans and balls; interaction and skyline test suites. Skyline flicker deferred to the Blender/panorama rebuild (D-023).

- Feedback round 2 (2026-09-27): ranged grab actually pulls (own targeting, 6 m, line of sight); door collisions follow the door; all doors open; jump reaches the table; Steam Frame buttons: right A jump, B crouch, X sit, Y recenter; less skyline shimmer (measured).

- Feedback round 1 (2026-09-27): five-room apartment; visible ranged grab with highlight; door handles at 1.1 m; doors can't swing through the player; sit on sofa/bed; jump and crouch buttons; recenter confirmation; skyline window anti-aliasing; VS Code language server port.

- M1 scaffold (2026-09-27): XR rig with hands, smooth move/turn, stick-deflection sprint, teleport/snap/vignette options, hold-Y recenter; apartment blockout with window and hallway stub; grabbable door, bouncing ball, beverage cans, trash can; procedural skyline; perf flythrough.
