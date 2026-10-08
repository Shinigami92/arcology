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
- [M2] Player avatar stage 4: Silena's head, face and hair (`docs/characters/silena_vesper.md`). Eyes done (D-050): violet eyes, lids, lashes, brows, smoky eye makeup, eye contact in mirrors, optional eye tracking. Still wanted: dark lips, the violet filigree markings on cheek, temple and neck, the messy updo with loose strands (hair cards), the dangling earring, the necklace. The mirror works (D-049) and already shows the head (render layer 11, hidden from the player's own camera).
- [later] Eye tracking for the avatar's eyes (D-050): the OpenXR eye gaze interaction is wired up (`eye_gaze_pose` on `/user/eyes_ext`, read by `AvatarEyes`) but didn't move the eyes on the Steam Frame (2026-10-05). To check: whether SteamVR offers `XR_EXT_eye_gaze_interaction` at all (`OpenXRInterface.is_eye_gaze_interaction_supported()`, the startup log), whether the tracker gets a pose and under which name, and Steam's eye-tracking permission.
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
- [later] Live reflections: a cheaper pass (skip small props via a render layer), a curved magnifier (today a planar zoom), rain and steam on the mirror and the shower screen (D-049). By day every reflection viewport renders the sun's shadow map again (D-052): the light's `shadow_caster_mask` could keep small props out of it.
- [?] Ray grabs for handles too: open doors, drawers and the fridge from afar with the controller ray (today the ray grabs pickables and presses buttons, D-054).
- [M2] Physical light switches and dimmers per room, and/or a smart-home hub panel (could be the same in-world terminal as the world-state control panel).
- [M2] Windows (D-033): tilt vent in the bedroom, motorized shades and smart-glass tint per room via a wall panel, HUD readout on the living room glass. Done on placeholders; the artist's frame/sash/panel glbs drop in by rerunning `tools/props/window.py`.
- [M2] Window HUD: more readouts (news ticker, messages). It shows the world's time, temperature and weather (D-051).

## World state and weather

- [M2] Weather: rain particles, wet surfaces, fog, lightning, sky crossfade, audio layers; weather that changes by itself. Rain on the glass is done (D-034) and goes through `WorldState.set_rain()` (D-051); the world terminal sets it by hand (D-053).
- [M2] Day/night polish (D-051, D-052 are done): a dawn that differs from dusk, stars and a moon in the night sky, rain that dims the city's haze, weather that changes by itself (today it's set by hand), shadowed window spill on overcast days, smart-glass tint dimming the sun; tune the day in the headset.
- [later] Rain on glass: wind-blown slanted runners, drops gathering on the sill and dripping, splashes on the stone sill outside the bedroom vent; better rain sounds than the synth placeholders.
- [M2] World terminal polish (D-053 is done): a smart-home page (room lights, shades, tint), weather presets (fog, storm) once the weather system has them, a news ticker.
- [later] Sunlight leaks at a few wall edges (thin generated walls, shadow bias); likely gone once a building shell surrounds the apartment (roadmap phase 1).
- [M2] Panorama variants: day, dusk, night, rain/fog, crossfaded by time and weather.
- [M2] Replace the procedural window pattern with prefiltered (mipmapped) facades/impostors; the remaining flicker in the headset is probably aliasing plus stream compression (D-023).

## City view

- [M1] Simple window view.
- [M2] Window view in layers: near facades as real, realistic geometry (simplified only where distance hides it), mid-distance as impostors/cards, far city as Blender-rendered panoramas. Near ring done (D-045): ten Blender towers; the far city repeats them (D-046). Next: more tower variety (types, heights, wider footprints for the far ring), then the panorama.
- [M2] City life on the towers: blink the `<tower>_blink` meshes (warning and pad lights), animate the spires' `_ad<n>` panels (unshaded, scanlines, flicker), scale the city materials' emission with the day/night cycle.
- [later] Upgrade a layer to real geometry when its zone is built (roadmap, phase 2).
- [later] Holographic ads, more neon signage.
- [M2] Flying traffic polish (D-047 is done): whoosh/hum of near vehicles through the open vent, the patrol car's light bar blinking (lamp boxes above local y 0.63: x < 0 red, x > 0 blue), occasional lane changes, more vehicle types. Docking at pads and buildings: see the roadmap, phase 3.
- [later] Elysium-style ring visible in the sky.

## Zones

- [M1] Apartment: living room with a large window.
- No loading screens, ever. Doors start background loading on approach; if not ready, a diegetic delay (e.g. an "ID scan") covers it. Elevator rides last as long as loading needs.

## Roadmap: from the apartment to a walkable city

The user's long-term direction (2026-10-04). Too big for one session: each phase is built part by part, each part playable and measured before the next. Order matters: rendering visibility and streaming come first, because every later phase adds far more than the GPU can draw at once.

### Phase 0: draw only what can be seen (next)

- [M3] Visibility tiers for everything outside: near ring, far city and traffic per window cluster, and per-node `visibility_range` fades instead of hard cuts. The city layers already switch off when no window is in view (D-048).
- [M3] Zone streaming (`core/zones/`): done for doors (D-059): `ZoneStreamer` loads the zones next to the player's from `zones/zone_graph.json` in the background, frees those two connections away, holds a connection's door shut until both sides are in (amber "ID scan"), and draws a zone the player isn't in only through an open door or the peephole. Still to do: tiers per zone (full interior, exterior shell only, impostor) with a budget per tier; connections other than doors (elevator, station); loading on approach for zones too big to keep loaded next door.
- [M3] Spread a big zone's load over frames: streaming the apartment back in costs two ~100 ms frames (its `_ready` work, five probe captures, the first draw; D-059). Before the elevator makes that happen in play: stagger probe captures, defer heavy `_ready` work, or add the zone in parts.
- [later] Port `tools/blockout/apartment.py` onto the shared writer `tools/blockout/blockout.py` (it still has its own copy).
- [M3] Perf flythrough per zone and per transition (the hitch of loading a zone counts), in XR before a phase is done.

### Phase 1: our own building

- [M3] The arcology we live in as a real building: its exterior shell (seen later from outside and from the transit), its floor plan, and the stack of floors as modular, generated parts (one floor in full, the others as shells).
- [M3] Outer hallway behind the entrance door: blockout done (D-059): side corridor from a facade window past our door (4417) and two neighbors, main corridor with four more units, service and stairs doors, an elevator lobby with two (static) elevators, Label3D signs. Next: real geometry and materials (an `environment-artist` agent: wall panels, ceiling, lighting fixtures, skirting, the window's frame glbs), sounds (corridor hum, footsteps on its floor), signs from the world directory.
- [M3] Elevator: call button, doors, a cabin that rides 180 m down; the ride is the streaming delay. Floor buttons for later floors.
- [M3] Lobby at street level (y = -180): concierge desk, mailboxes, security gates, the exit doors.
- [M3] Persistence: object state across zones, save/load.

### Phase 2: outside

- [M4] The street level around our building, walkable: plazas, walkways, shop fronts, wet streets, street-level traffic and pedestrians later. The near ring's towers get their street-level podiums as real geometry when the street is built (until then they end in the fog).
- [M4] Building interiors. All buildings should feel inhabited and be walkable over time: first every window shows a fake interior (interior-mapping shader on the facade atlases: rooms with depth and parallax, almost free); then buildings become enterable one at a time (lobby, shops, a bar, a ramen place, apartments), built from modular kits and generators, streamed in on approach.
- [later] Markets, a club, rooftops.

### Phase 3: transit (Star Citizen style)

- [M5] Stations: sky-bus stops and taxi pads at buildings, with signs, timetables and a call button; wait at the station, a vehicle docks, get in, sit (seated-first fits this perfectly), ride along the traffic lanes to another station, get out. The ride streams the destination like the elevator does.
- [M5] Vehicles docking at landing pads and buildings (the KAZE roof pad first), also as ambient traffic: vehicles leave lanes, land, wait, take off.
- [later] Flying a vehicle yourself.

### Across all phases: a world that makes sense, and wayfinding

The user (2026-10-04): walking the world, everything should make sense; signs, holograms and maps guide the way to shops, transit and buildings, outside and inside.

- [M3] One world directory as the single source of truth (a text file, e.g. `world/directory.json`): districts, streets with names, buildings with names and addresses, their floors and what's on each (apartments with unit numbers, shops, the lobby), stations and their lines. Signs, maps, elevator panels, door plates, mailboxes, timetables and the window HUD are all generated from it, so they never contradict each other, and adding a shop puts it on every map and sign at once.
- [M3] Inside buildings: a floor directory and "you are here" map in the lobby and at each elevator, floor numbers at the elevator doors, unit numbers on doors (ours already has a unit plate), arrows to the elevators, stairs and exits, emergency exit signs. The elevator panel lists what's on each floor.
- [M4] Outside: street name signs at corners, building names and addresses at the entrances, directional signposts and holographic wayfinding pillars ("Transit ▸ 120 m", "Market ▸"), shop signs that match their shops, station signs visible from afar, a district map at plazas.
- [M5] Transit: line maps and timetables at stations, the destination on the vehicle's sign, arrival announcements, a route map inside the cabin.
- [later] An optional personal guide: a route to a chosen place shown as a holographic line or arrows (a wrist device or the window HUD), off by default so the signs stay the main way to find things.
- Readability rules (style guide): text large enough to read where the player stands, a consistent sign family per kind (street, building, transit, shop), bilingual (Latin + invented kanji), lit at night, never so dense it becomes visual noise.

### Agents for the roadmap

New subagents when a phase starts (the user agreed to add or update agents whenever it helps them focus):
- `environment-artist` (Blender): modular building kits, interiors, facade atlases with fake-interior maps, elevator cabins, lobbies; props stay with `blender-artist`.
- `world-builder` (Godot): zone generators, occluders, streaming, zone graph and connections, transitions; `godot-dev` keeps player, interaction and systems.
- Maybe `systems-dev` (Godot) once traffic, transit and world state grow: schedules, stations, vehicle docking.

## Performance and tooling

- [M1] Scripted camera flythrough per zone that logs frame times and fails on budget regressions.
- [later] Shader precompile helper, if a perf report ever shows pipeline compiles on dropped frames. The M1 hitches (8 frames up to 58 ms) turned out to come from the machine, not compiles (D-025); the XR Tools demo also hitched when first picking up the scoped rifle.
- [later] Budget SubViewport cameras (scopes, mirrors, security monitors) explicitly.
- [M2] Refresh the perf baselines with the avatar, occlusion culling, live reflections, the sun's shadows and the world terminal: an XR perf run in the headset (the user), then the zone table in CLAUDE.md; and a desktop run at night and by day (`--time=17 --weather=clear`) with SteamVR closed (it adds ~0.9 ms GPU to desktop runs, D-052), copied over `tools/perf/baselines/`.
- [M2] Ambient occlusion budget (D-055): SSAO is on and the user wants it, but costs +1.8 ms GPU p95 on the desktop flythrough (8.2–8.4 ms, over 8.0), mostly from its normal buffer under MSAA 2x. Measure in XR; if over budget, bake AO into the static shell (generator surfaces or LightmapGI) and keep SSAO small for the furniture, or trade MSAA for another AA.
- [later] Stagger the probe re-captures (one probe at a time instead of four for 8 frames) if a hitch shows at dawn or dusk (D-051).
- [later] Faster interaction tests: with `--fixed-fps 90 --disable-vsync` the full suite takes ~17 s instead of ~87 s, but `HingeSwing`/`SliderSwing` measure release speed with the real clock (`Time.get_ticks_usec`); move them and the tests' throws onto engine time first. Waiting until things stop moving instead of fixed frame counts would save another ~13 s.

## Rejected or low priority

- Grappling hook (least satisfying in the XR Tools demo; not a fit).

## Done

- Zone streaming and the corridor (2026-10-08, D-059): floor 44's corridor streams in behind the entrance door (the vestibule is gone); the door waits for it with an amber LED; a zone the player isn't in is only drawn through an open door or the peephole (from the corridor: 846 → 186 draw calls); tests `zones`, `--perf-reload`, `--load-depth`.
- Ambient occlusion (2026-10-06, D-055): SSAO in the world environment, blind headset A/B won clearly; radius 0.6 m after halos at 1.0 m by day. `ABEnvironment` A/Bs Environment settings with the same panel.
- Ray presses and a deeper skyline (2026-10-05): every button can be pressed from afar by pointing the controller ray and pulling R1/R2 (snap and hover highlight); the world terminal floats in the living room window's left bay; a far skyline band out to 3.5 km (D-054).

- World terminal and a city without a floor (2026-10-05): a holographic wall terminal sets time, clock speed, weather, rain and date by touch (D-053); the street plane is gone, the towers reach down into the haze with lit windows fading in the depth, deep traffic lanes below the window.

- Sun, seasons and weather (2026-10-05): the real sun for the date at 48° N, windows facing 240° (winter sunsets in front of them), sun patches with window-frame shadows moving across the floor, hazy-sun and overcast days, a less white day (D-052).

- World state and day/night (2026-10-05): the world follows the PC's clock (or `--time`); an overcast, hazy day, dusk and dawn tint the sky and fog; the sun lights the city, the windows let daylight in, the city's lit windows and traffic lights dim by day, and the room lights dim like a smart home; the HUD shows the world's time, temperature and weather (D-051).

- Live reflections (2026-10-04): the bathroom mirror, the magnifier (3× zoom), the shower screen and the window glass reflect the room and the avatar, per eye, while in view; the windows share one renderer (D-049).

- Occlusion culling (2026-10-04, roadmap phase 0): the apartment generator writes a box occluder per wall, floor and ceiling; the city and traffic hide while no window is on screen (`OutsideView`, D-048). Bathroom 271 → 216 draw calls, hallway 465 → 332; no visible difference in the headset.

- City view (2026-10-04): ten Blender towers in the near ring, brutalist megablocks and corporate spires (D-045); the far city repeats them instead of the box placeholders (D-046); height fog toward the street; flying traffic with five vehicle types in lanes at many altitudes, moved on the GPU (D-047). Skyline shimmer from ~5.0 % down to 2.1 %.

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
