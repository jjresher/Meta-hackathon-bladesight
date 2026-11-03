# Meta API: first real calls (issue #2)

Date: 2026-10-29. Procedure: skill `meta-api-check` through `bladesight.meta` (`MetaClient`: cache,
retries, spend cap), Meta only (no Baseten call), `BLADESIGHT_MODE=live`, hard cap 0.10 USD
(cumulative, summed from `.spend/spend_log.jsonl`). The key was read from the environment/`.env`
in-process and never printed. Checks before the calls: `META_API_KEY` set, `BLADESIGHT_MODE` set
(live), `META_API_BASE_URL` set (resolves to host `api.meta.ai`, https); a `--cache-only` dry run
was a miss, as expected. All images are public Wikimedia Commons photos, not dataset images.

Costs are the documented prices (dev.meta.ai/docs) times the real usage; they are NOT checked
against an invoice. The raw response bodies were not stored: the usage numbers, request ids and
parsed masks are in `.spend/spend_log.jsonl` and the cache (both gitignored); fields such as the
echoed `store` / `reasoning` values were read from the live replies during the session (their
structure was captured by throwaway step scripts that are not committed).

## Calls and cost

| Step | Calls (live / cached / retried) | Est. cost USD | Result |
|---|---|---|---|
| 1a. Muse Spark `muse-spark-1.3`, rotor-blade photo, one-line prompt, default effort, `max_output_tokens=800` | 1 / 0 / 0 | 0.004450 | OK. 1143 in / 711 out (686 reasoning). Request id `3112c130-cd9e-4fde-9b07-640a3b479c8f` |
| 1b. SAM `sam-3.1`, "wind turbine blade", same rotor-blade photo | 1 / 0 / 0 | 0.002500 | OK, **0 matches**. `ecebebe9-2b9a-4da1-83fd-cbc505fce262` |
| 2a. SAM "car", street photo (1280x855) | 1 / 0 / 0 | 0.002500 | OK, **6 masks**, confidence 0.675-0.953. `7c45e332-6512-433b-ab7c-3c7c2b2efd72` |
| 2b-1. SAM "wind turbine", wind-farm photo (1280x960) | 1 / 0 / 0 | 0.002500 | OK, **6 masks**, confidence 0.863-0.949. `86010b75-292b-4f92-bdca-40d03e604990` |
| 2b-2. SAM "rotor blade", same photo | 1 / 0 / 0 | 0.002500 | OK, **16 masks**, confidence 0.515-0.789. `cb9f94b3-d2a4-46a3-82b4-da6d5e3958d7` |
| 2c. Muse Spark, same prompt/image as 1a, `reasoning.effort="low"`, `store=false` | 1 / 0 / 0 | 0.002406 | OK, both values accepted. 1143 in / 230 out (203 reasoning). `2e1608f3-f7ed-4b91-99c0-4e1ab5b5973d` |
| Total | 6 / 0 / 0 | 0.016857 | Cap 0.10 USD not approached; no 400, no retry |

Images: 1a/1b/2c `.../thumb/4/44/Ice-at-rotor-blade-of-wind-turbine.jpg/1280px-...`; 2a
`.../thumb/8/8a/Parked_cars_on_Howard_Street_-_geograph.org.uk_-_8382065.jpg/1280px-...`; 2b
`.../thumb/a/a2/Desert-Sky-Wind-Farm.jpg/1280px-Desert-Sky-Wind-Farm.jpg` (all under
`https://upload.wikimedia.org/wikipedia/commons/`).

## Confirmed on the wire

- `POST https://api.meta.ai/v1/responses`, bearer auth, `stream: false`, body
  `{"model", "input": [{"type": "message", "role": "user", "content": [...]}], "max_output_tokens"}`
  accepted. `input_text` + `input_image` with `image_url` = a public URL is fetched by Meta.
- Muse Spark reply: `status: "completed"`, `output` = `[reasoning item, message item]`, text in
  `output[1].content[0].text`. Usage shape (real numbers, call 1a):

  ```json
  {"input_tokens": 1143, "input_tokens_details": {"cached_tokens": 0},
   "output_tokens": 711, "output_tokens_details": {"reasoning_tokens": 686}, "total_tokens": 1854}
  ```

  Reasoning tokens are inside `output_tokens` (686 of 711).
- `reasoning: {"effort": "low"}` and `store: false` are both accepted and echoed back
  (`"store": false`, `"reasoning": {"effort": "low"}`). On the same prompt and image, output went
  from 711 to 230 tokens (reasoning 686 to 203) and the cost from 0.004450 to 0.002406 (-46%),
  (usage of call 2c: `input_tokens` 1143, `cached_tokens` 0, `output_tokens` 230,
  `reasoning_tokens` 203). The one-sentence description it gave ("Snow and ice coat the edge of a
  large red ramp on a snowy hillside") is fluent but does not mention a rotor blade; that is a
  quality signal for #3, not a #2 finding. The default effort (call 1a) echoed a 4-character value
  and the default `store` echoed `true`; both read from the live reply, raw body not stored. Effort
  values below "low" were not tried.
- SAM request accepted: one `input_text` (the concept) + one `input_image` (`image_url`), no
  `/v1/files` upload, `metadata {"mask_encoding": "one_bit", "include_confidence": "true"}`,
  non-streaming. Reply: `status: "completed"`, one `message` item whose `output_text` is the
  special-token text. No match gives `output_text == ""` (call 1b). Usage: all token counts 0 and
  `"images_processed": 1` (the observed per-image count; per-image billing itself comes from Meta's
  pricing page). The SAM reply also echoes `"store": true` (read from the live reply of call 1b; the
  raw body was not stored, and `store` was not sent on SAM requests).
- Real SAM masks (28 masks over 2a, 2b-1, 2b-2), as parsed by `meta-sam-parser`:
  - Each record is `id<|box;x1;y1;x2;y2;w;h;c|><|mask;x=0;y=0;c;data=H,W,!payload|>`: one-bit `!`
    payloads, a full-precision float confidence `c` on both tokens (e.g. `0.8439024686813354`).
  - `w`/`h` equal the source image size (1280x855 and 1280x960; they match the downloaded files).
  - `x2`/`y2` are inclusive: wire `x1=582;x2=651` is 70 px wide and the mask says `data=24,70`.
  - **The mask raster is exactly the size of its box** (all 28: `(mask width, height) == (box
    width, height)`), is placed at the box's top-left corner, and nothing falls outside the box.
    The mask-token `x=0;y=0` were 0 in all 28 records and are not used; placement is by the box.
  - Checked visually: overlays of the masks on both photos (kept locally, not committed) show the
    masks following the cars and the turbines (tower and blades) inside their boxes.

## Early observations for the #3 go/no-go (n = 2 images, no ground truth: NOT tuning)

- "car" and "wind turbine" found every obvious object at confidence 0.68-0.95; the 6 turbines in
  2b-1 include the two small distant ones on the left and the one cut by the right edge.
- "rotor blade" on the same photo gave 16 masks at lower confidence (0.515-0.789), many thin or
  partial pieces (boxes as small as 6x55 or 17x7 px; mask fill 0.19-0.83 of the box). The default
  threshold 0.5 keeps all 16; whether they are real blades was not verified.
- The first photo (ice on a rotor blade, close-up) returned 0 matches for "wind turbine blade".

## Not confirmed

- `input_tokens` including the cached tokens (`cached_tokens` was 0 in every call, also on the
  repeated prompt and image).
- `temperature` (never sent), tool-call item shapes, `store` on SAM requests (not sent), effort
  values other than "low" and the default, Baseten's image input format.
