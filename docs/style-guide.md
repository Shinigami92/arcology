# Style guide

## Mood

**Realistic, not stylized.** Assets aim for believable, photoreal materials and proportions (PBR textures, wear, bevels that catch light), not low-poly or toon looks. Geometry is only simplified where the player can't tell: far away, or hidden by distance and fog.

Lived-in, dense, vertical. The apartment is a warm, slightly cramped refuge; the city outside is cold, huge and never dark. The contrast between warm interior light and cool, neon-soaked exterior is the signature look.

| Source | Take | Leave |
|---|---|---|
| The Fifth Element | Stacked apartment blocks, flying traffic lanes, compact prefab apartments with clever fold-away furniture, bright color accents | Cartoonish tone |
| Star Citizen Area18 | Readable scale, believable signage, rain on plazas, layered skyline | Clean sci-fi sterility |
| Cyberpunk 2077 | Neon signage density, holo ads, grime, wet streets | Visual noise that hurts VR readability |
| Ghost in the Shell | Melancholy, fog, overcast skies, Asian-influenced signage, holograms | |
| Coruscant | Endless vertical depth, traffic streams at many altitudes | Pristine surfaces |
| Elysium | The ring in the sky: the rich live above | |

## Palette

Base colors (albedo, in sRGB):

| Name | Hex | Use |
|---|---|---|
| Night navy | `#0B0F1A` | Sky at night, deep shadow tint |
| Smog blue | `#1C2A3A` | Fog, distant facades at night |
| Concrete | `#5A5F66` | Structural concrete, facades |
| Gunmetal | `#2E3238` | Painted metal, window frames |
| Brushed steel | `#8A9099` | Appliances, handles, rails |
| Warm off-white | `#D8D2C4` | Interior walls, plastics |
| Rust | `#7A3E1D` | Wear, old metal accents |

Neon accents (emission; use sparingly indoors, generously outside):

| Name | Hex | Use |
|---|---|---|
| Neon magenta | `#FF2A6D` | Primary signage, ads |
| Neon cyan | `#05D9E8` | Holograms, UI, terminals |
| Sodium amber | `#FFB000` | Street lights, warnings |
| Ultraviolet | `#7B2FFF` | Club signage, night accents |
| Acid green | `#39FF14` | Rare highlight only (pharmacy crosses, status LEDs) |

Interior light: warm 2700–3000 K (`#FFB36B` to `#FFC58F`). Exterior ambient at night: 8000–12000 K blue-cyan, tinted by neon spill.

## Materials

- **PBR metal/roughness**, authored in Blender, exported via glTF. One material per surface type, shared from `assets/materials/` where possible.
- **Wear everywhere:** edges get scuffs, horizontal surfaces get dust, exterior surfaces get grime streaks below ledges and windows.
- **Wet look (M2):** a shared wetness parameter lowers roughness and darkens albedo; puddles are a mask, not separate geometry.
- **Holograms:** unshaded, additive, cyan or magenta, with scanlines and a slight flicker. Never cast shadows.
- **Glass:** the main window is a single, mostly clear pane with subtle smudges and (M2) rain. Avoid stacked transparent layers; they cost fill rate twice in stereo.
- **Texel density:** ~512 px/m for props in reach, ~256 px/m for walls and floors, lower for anything outside the window.

## Lighting

- Night is the default mood; the day is overcast and hazy, never a clear blue sky.
- Few shadow-casting lights (see the budgets in `CLAUDE.md`); fill with emissive surfaces, VoxelGI and unshadowed lights.
- Neon spill from outside colors the apartment through the window: a large, soft, colored light near the window, not many small ones.
- Volumetric fog outside only when it's affordable; distance fog and baked panorama haze otherwise.
- Tonemapper: ACES or AgX; keep one choice project-wide once picked.

## Scale and readability in VR

- Real-world scale, always: door 2.1 m × 0.9 m, ceiling 2.6 m in the apartment, countertop 0.9 m, table 0.75 m, light switch 1.1 m.
- Text and signage large enough to read in the headset from where the player stands.
- Avoid high-frequency detail (thin stripes, fine grids) that shimmers in VR; prefer medium-scale shapes and roughness variation.
