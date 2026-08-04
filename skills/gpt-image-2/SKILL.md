---
name: gpt-image-2
description: Generate or edit raster images with OpenAI gpt-image-2 through the local gpt-image-2 MCP server. Use when the user explicitly asks to create, generate, draw, render, revise, inpaint, restyle, or otherwise edit a photo, illustration, texture, icon bitmap, mockup, or any other pixel image. Covers PNG/JPEG/WebP output, local reference images, and alpha masks. Do not use for SVG, vector art, charts, diagrams, CSS/HTML UI, or anything better produced as code.
---

# GPT Image 2

## Overview

Generate and edit raster images through OpenAI's direct Image API, exposed as
two local MCP tools: `generate_image` and `edit_image`. Every call is paid,
moderated, and slow — several minutes is normal, and the server allows one
operation 540 seconds end to end. Every successful call writes real files to
disk and returns their absolute paths.

## Before you call: is this actually a raster job?

Reach for this skill only when pixels are the deliverable.

| Ask | Use instead |
| --- | --- |
| Logo, icon set, diagram, chart, flowchart | SVG or a diagramming workflow |
| UI layout, landing page, component mockup that will become code | HTML/CSS/React directly |
| Data visualisation | a plotting library |
| Editing an existing SVG or vector source | edit the source |
| Photo, illustration, texture, matte painting, concept art, photoreal mockup | this skill |
| Inpainting, restyling, or compositing existing bitmaps | this skill |

A generated raster of a UI is a picture of a UI. If the user wants something
they can ship, build it in code.

## Disclose the cost before you spend it

State plainly, once, before the first call in a session: this calls OpenAI, it
costs money per image, it is subject to OpenAI's content moderation, and it
commonly takes several minutes per request. Then proceed — do not ask permission
for every subsequent image in an approved batch.

While a call is in flight, do not conclude it has hung and do not fire a second
one. Each image is separately billed, and the server already bounds the call at
540 seconds and will return a structured error if it runs out.

## Choosing the operation

- **`generate_image`** — a new image from a prompt alone.
- **`edit_image`** — anything anchored to existing local pixels: inpainting,
  restyling, compositing several references, extending a scene.

If the user is iterating on something you just generated, that is an *edit*
against the saved file, not a fresh generate with a longer prompt. Editing
preserves what already worked.

## Before an edit: look at the references

Non-negotiable. Open and inspect every reference image before calling
`edit_image`. You are about to pay to transform pixels you have not seen.

- Confirm the subject, framing, palette, and resolution are what you assumed.
- Write down the invariants the user stated ("keep her jacket red", "don't move
  the horizon") and repeat them in the prompt as explicit constraints.
- Reference order matters, and **the first reference is the mask target**. Put
  the image being edited first; supporting style or context images follow.

### Masks

A mask marks the region to redraw with **transparent** pixels. The tool
enforces three rules locally, before spending anything:

- the mask's pixel dimensions match the first reference exactly;
- the mask's format matches the first reference's format;
- the mask has an alpha channel that is not fully opaque.

Because a mask needs alpha, use **PNG or WebP** references whenever you plan to
mask. A JPEG first reference cannot have a format-matching mask with alpha.

## Writing the prompt

Describe the finished image, not the process. Front-load the subject, then
composition, then style, then lighting, then medium.

- Be concrete about what must be true: "three ceramic mugs, left one chipped".
- Name what to exclude only when it matters; negations are weak.
- For edits, restate the invariants: "same camera angle, same lighting, only
  the sign text changes".
- Keep the prompt under 32,000 characters (a local limit, enforced before any
  request is sent).

## Controls and defaults

Every default below is applied when you omit the argument. Change one only when
the user's intent requires it.

| Argument | Default | Notes |
| --- | --- | --- |
| `quality` | `high` | `auto`, `low`, `medium`, `high`. Lower is cheaper and faster. |
| `size` | `1024x1024` | `auto` or `WIDTHxHEIGHT`: edges multiple of 16, max edge 3840, aspect at most 3:1, total pixels 655,360 to 8,294,400. |
| `output_format` | `png` | `png`, `jpeg`, `webp`. |
| `output_compression` | unset | `0` to `100`, JPEG/WebP only. Setting it with PNG fails locally. |
| `n` | `1` | Up to 10. Each image is billed. |
| `background` | `auto` | `auto` or `opaque` only. |
| `moderation` | `auto` | `auto` or `low`. `generate_image` only. |
| `output_dir` | `<working-directory>/generated-images/` | An override must be an **absolute** path. |
| `basename` | `image` | Never derived from the prompt. |

**gpt-image-2 does not support transparent backgrounds.** Asking for
`background="transparent"` fails immediately with a clear error rather than
silently returning an opaque image. If the user needs transparency, generate on
a plain contrasting background and say that removing it is a separate editing
step.

Files are never overwritten. A second `image.png` becomes `image-2.png`, then
`image-3.png`.

## After the call: look at what you made

A successful call is not a finished task. The result carries every absolute
path, and a preview of the first image when it fits inline.

1. **Open the saved file.** If no preview came back — because the image was
   over the inline limit, or because there were several — read it from its path.
2. **Compare against the request.** Subject present? Count correct? Text
   legible? Invariants preserved? Composition as asked?
3. **Report honestly.** If it missed, say what missed. Do not describe the
   image you asked for; describe the image you got.
4. **Iterate narrowly.** One targeted change per attempt, as an edit against
   the saved file. Do not silently rewrite the user's brief, and do not loop
   more than a couple of times without checking in — each attempt costs money.

## When it fails

Every failure returns a stable `code`. The useful distinctions:

| Code | What to do |
| --- | --- |
| `invalid_request`, `unsupported_option`, `invalid_input_file`, `invalid_mask` | Local rejection, nothing was spent. Fix the argument and retry. |
| `moderation_blocked` | OpenAI declined the content. Revise the request legitimately, explain the block, and never attempt to evade it. |
| `user_error` | OpenAI rejected the request. Read the provider message; do not resend unchanged. |
| `missing_credential` | `OPENAI_API_KEY` is not visible to the server. Ask the user to set it and reload MCP. |
| `access_denied` | Usually organization verification or billing. Report it; it is not something you can work around. |
| `rate_limited`, `service_error` | Transient. One bounded retry already happened. Wait before trying again. |
| `api_timeout`, `connection_error` | Deliberately not retried — the request may already have been billed. Check the output directory before resending. |

Never retry a `moderation_blocked` or `user_error` with the same input, and
never suggest phrasing intended to slip past moderation.

## Setup

The tools come from the `gpt-image-2` MCP server in this repository. If they are
not listed, see `README.md` for registration and reload, and confirm
`OPENAI_API_KEY` is set. Server startup and tool listing need no credential —
only an actual generation does.
