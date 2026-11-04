# Severity rubric (version `v1`)

**This is BladeSight's own illustrative rubric, not an industry standard** (it is not the
IEC/DNV/wind-industry damage categories). It exists so that a model, and a human labelling the
gold set (#10), can grade the same thing from the same observable criteria. It was written for
drone photos of the DTU Nordtank blade, where tiles carry no scale: everything is judged from
appearance and relative size, never from millimetres.

Severity is graded per detected defect, from a close crop and a wider context crop of one tile.

| Severity | Name | Observable criteria |
|---|---|---|
| 1 | Cosmetic | Dirt, stains, streaks, light discolouration. Surface and paint intact. No action. |
| 2 | Minor wear | Small surface wear or tiny paint chips; coating intact around it; no exposed laminate. Monitor at the next inspection. |
| 3 | Moderate | Visible paint or coating loss or erosion over a patch, or a short hairline mark; substrate may show but no fibres and no open crack. Schedule a repair. |
| 4 | Serious | A crack that is clearly open or long relative to the visible blade width, delamination, or exposed laminate and fibres. Repair soon. |
| 5 | Critical | Deep or large structural damage: a crack across a large share of the blade width, missing material, a hole, damage that could let the blade fail. Stop and repair. |

Rules of thumb (not extra levels):

- Dirt is severity 1 unless the dirt hides damage; say so in the rationale.
- Size is relative: judge a mark against the visible blade width, not against the tile.
- When a defect could be two levels, choose the lower one and lower the confidence; the
  verification step (#8) turns low confidence into `needs_review` or `reinspect`.
- If the crop is too small, blurred or ambiguous to grade, say so and give a low confidence
  rather than a confident guess.

Defect types: `leading_edge_erosion`, `crack`, `lightning_damage`, `surface_damage`, `dirt`,
`other`.
