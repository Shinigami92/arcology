# Silena Vesper

The player's own body: the user's Shadowrun 6 character, seen in first person (hands, sleeves, looking down) and later in mirrors. Reference: `silena_vesper_reference.png` (a painted concept; we translate it into the realistic PBR style of `docs/style-guide.md`, not the painted look).

## Character

- **Concept:** nocturnal elf adept, specialist for discreet extractions and infiltration. Elegant, calm, polite, slightly arrogant; prefers clean solutions.
- **Role:** stealth, pistols, perception, social; brings targets in alive.
- **Gear ideas (later props):** Ares Predator heavy pistol (gel rounds), zip ties, handcuffs, lockpicks, maglock passkey, multitool, flashlight, disposable gloves, armor tape, fiber-optic camera.
- **Nocturnal:** light-sensitive and irritable by day; works in the evening.

## Body

- **Stature:** ~1.91 m, slender elf build, long limbs and fingers. The eyes sit at the rig's standard eye height (`godot_xr_tools/player/standard_height` = 1.8 m), which fixes the scale.
- **Base mesh:** MPFB2 (CC0 core assets), female, tall, slim, low muscle; elf ears and face sculpted on top.
- **Skin:** pale, cool undertone. Violet filigree markings (tattoo-like) on one cheek, temple and down the neck.
- **Head (later):** long pointed ears, violet eyes, smoky eye makeup, dark lips. Black hair with a violet sheen, messy updo with loose strands framing the face. Dangling dark-metal earring with a violet stone, thin necklace.

## Outfit

Mostly black, with violet as the only accent color. Violet glows only on tech (the passkey).

| Part | Description | Seen in first person |
|---|---|---|
| Gloves | Black leather gloves, embossed filigree pattern on the back of the hand, wrist strap; fitted, thin enough for lockpicking | always (stage 1) |
| Coat sleeves | Long black leather coat, sleeves with violet filigree embroidery, wide cuffs over the glove cuffs | always (stage 1) |
| Coat | Ankle-length, high upturned collar, open front, violet filigree embroidery on the panels; tails swing (spring bones) | looking down |
| Top | Black brocade/lace corset-style top over a deep violet underlayer, V-neck | looking down |
| Belt | Wide black leather utility belt: pouches, a row of small cylinders (vials/ammo), handcuffs on a clip, violet-glowing maglock passkey | looking down |
| Trousers | Black, fitted; thigh strap (holster) | looking down |
| Boots | Black leather, low heel (not in the reference; keep simple) | looking down |

## Palette

| Name | Hex | Use |
|---|---|---|
| Leather black | `#141216` | Coat, gloves, belt (roughness 0.45–0.6, worn edges lighter) |
| Fabric black | `#0F0E12` | Top, trousers (matte) |
| Filigree violet | `#5B3F86` | Embroidery, glove pattern, underlayer (albedo, not emissive) |
| Tech violet | `#7B2FFF` | Passkey glow (style guide's Ultraviolet, emissive) |
| Skin | `#E6D6CF` | Pale, cool |

## Stages

1. Gloved hands (replace the XR Tools hands). Done (D-038, D-039).
2. Coat sleeves, arm IK. Done: the whole arm to the shoulder (D-040).
3. Body when looking down: top, belt, trousers, boots, coat, full-body IK and leg animation. Done: one body skeleton (D-041), stepping and sitting (D-042, D-043), coat and belt items on spring bones (D-044).
4. Head, face and hair (for the mirror). Open: the head is a placeholder (closed eyes, simple hair), already visible in the bathroom mirror (D-049); see `docs/ideas.md`.

The skeleton and rendering rules are in D-037.
