# Meta API step 1: first real calls (issue #2)

Date: 2026-10-29. Procedure: skill `meta-api-check`, step 1, Meta only (no Baseten call), through
`bladesight.meta` (`MetaClient`: cache, retries, spend cap) with `BLADESIGHT_MODE=live` and a hard
cap of 0.10 USD. The key was read from the environment/`.env` in-process and never printed.
Image: a public Wikimedia Commons photo (CC BY-SA 3.0), not a dataset image:
`https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Ice-at-rotor-blade-of-wind-turbine.jpg/1280px-Ice-at-rotor-blade-of-wind-turbine.jpg`

Checks before the calls: `META_API_KEY` set, `BLADESIGHT_MODE` set (live), `META_API_BASE_URL` set
(resolves to host `api.meta.ai`, https), cache dry run (`--cache-only`) was a miss, as expected.

## Result

| Step | Calls (live / cached / retried) | Est. cost USD | Result |
|---|---|---|---|
| 1a. Muse Spark `muse-spark-1.3`, image + one-line prompt, `max_output_tokens=800` | 1 / 0 / 0 | 0.004450 | OK. `source=live`, 1 attempt, server returned model `muse-spark-1.3`, request id `3112c130-cd9e-4fde-9b07-640a3b479c8f` |
| 1b. SAM `sam-3.1`, concept "wind turbine blade", same image URL | 1 / 0 / 0 | 0.002500 | OK but **zero matches** (`output_text == ""`, status `completed`). Request id `ecebebe9-2b9a-4da1-83fd-cbc505fce262` |
| Total | 2 / 0 / 0 | 0.006950 | Cap 0.10 USD not approached |

Costs are the documented prices (dev.meta.ai/docs) times the real usage; they are NOT checked
against an invoice. Source: the spend log `.spend/spend_log.jsonl` (gitignored).
Check: 1143 x 1.25/1e6 + 711 x 4.25/1e6 = 0.0044505; SAM 1 image x 0.0025.

## Confirmed on the wire

- `POST https://api.meta.ai/v1/responses`, bearer auth, `stream: false`, body
  `{"model", "input": [{"type": "message", "role": "user", "content": [...]}], "max_output_tokens"}`
  accepted. `input_text` + `input_image` with `image_url` = a public URL accepted and fetched by Meta.
- Muse Spark reply: `status: "completed"`, `output` = `[reasoning item, message item]`, the text is in
  `output[1].content[0].text` (`type: output_text`). Usage (real numbers):

  ```json
  {"input_tokens": 1143, "input_tokens_details": {"cached_tokens": 0},
   "output_tokens": 711, "output_tokens_details": {"reasoning_tokens": 686}, "total_tokens": 1854}
  ```

  So reasoning tokens ARE inside `output_tokens` (686 of 711 for a one-sentence answer: the default
  reasoning effort is expensive; the reply echoed `"reasoning": {"effort": <4 chars>}`).
- The reply also echoes `"store": true`: Meta keeps responses by default.
- SAM request accepted: one `input_text` (the concept) + one `input_image` (`image_url`), no
  `/v1/files` upload, `metadata {"mask_encoding": "one_bit", "include_confidence": "true"}`,
  non-streaming. Reply: `status: "completed"`, one `message` item whose `output_text` is `""` when
  nothing matches, model `sam-3.1`. Usage has all token counts at 0 and
  `"images_processed": 1`, which is the billing unit.

## Not confirmed

- A real SAM mask: this image returned no match, so the box/mask wire tokens and how the mask
  raster maps onto the box have not been observed on real data. The documented format (and the
  `meta-sam-parser` examples) say the raster covers exactly the box; that is what the code assumes.
- `input_tokens` including the cached tokens (`cached_tokens` was 0).
- `temperature` (not sent), tool-call item shapes, Baseten's image input format.
