# HMI design for situation awareness (ISA-101, High Performance HMI, ISA-18.2)

Use this when designing or reviewing .NET HMI / eHMI canvases, CAT symbols and faceplates.
`eae_hmi_review` checks the parts that can be read from the files; the rest is in the manual checklist.
These are recognised practices, not EAE requirements: the **site HMI philosophy and style guide**
(ISA-101 lifecycle) decides the final colors and layouts.

## Situation awareness (Endsley)

Situation awareness is "the perception of the elements in the environment within a volume of time and
space, the comprehension of their meaning, and the projection of their status in the near future". A
display must support all three levels, not only show data:

| Level | Operator question | Display technique |
|---|---|---|
| 1 Perception | What is happening? Anything abnormal? | gray scene; color only for abnormal; alarm indicators with color + shape + text |
| 2 Comprehension | Is it OK? How far from normal? | moving analog indicators with normal range and alarm limits; values with units; state as text |
| 3 Projection | Where is it going? | embedded trends, rate-of-change arrows, targets/limits on trends |

Most legacy displays only support level 1 (raw numbers on a P&ID drawing) and leave levels 2–3 to the
operator's memory.

## ANSI/ISA-101.01 display hierarchy

| Level | Content | In EAE |
|---|---|---|
| 1 Overview | whole area at a glance: KPIs, area status, alarm counts per area; few controls | start canvas of a canvas resolution |
| 2 Unit control | one process unit: main loops, key values with analog indicators and trends; primary operating display | top-level canvases under the overview (`Canvases` in the resolution topology) |
| 3 Detail | all measurements and devices of a unit (P&ID-like) | child canvases (`Children`) |
| 4 Diagnostic | one device: parameters, tuning, maintenance data | CAT faceplates (`fMain`, `fAlarm`, …) opened from symbols |

Navigation should be identical on every display and reach any display in a few clicks. In EAE the
hierarchy is the topology in `CanvasesResolutionList.xml` / `WebCanvasesResolutionList.xml`; faceplates
give level 4 without extra canvases.

## High Performance HMI principles (ASM Consortium, Hollifield et al.)

- **Gray backgrounds** (light or medium gray), equipment drawn as simple 2D outlines in darker gray.
- **Color only for abnormal**: alarms and deviations get color; running/stopped, open/closed are shown by
  fill/shape and text, not red/green. Each color has one meaning across the whole HMI.
- **Alarm colors are exclusive**: red/orange/yellow (and magenta for e.g. suppressed) only for alarm
  priorities; never decorative.
- **Redundant coding**: alarm indicators combine color, shape and priority number/letter so they work for
  color-vision deficient operators (≈8% of men) and on grayscale.
- **Moving analog indicators** instead of bare numbers: a bar or pointer over the span, with the normal
  operating range shaded and alarm limits marked, answers "where am I versus where I should be".
- **Embedded trends** (short time window) for key values; show limits/targets on the trend.
- **No 3D, photos or animation** (spinning fans, flowing pipes): they add clutter and hide deviations.
- **Consistent typography**: one or two font families, a few sizes (title, label, value); readable at
  console distance (≥ 8–10 pt); text contrast ≥ 4.5:1.
- **Density**: show what the task needs; push detail down a level (faceplate) instead of filling a display.

## Alarms (ISA-18.2 / IEC 62682, EEMUA 191)

- 3–4 priorities, each with a distinct color, shape and text; priority distribution roughly
  low > medium > high.
- Unacknowledged alarms are distinguishable from acknowledged ones (e.g. blinking until acknowledged).
- Rate targets: about 1 alarm per 10 minutes per operator in steady state; ≤ 10 in 10 minutes during an
  upset is manageable. Floods, chattering and standing alarms are design defects.
- In EAE: alarm classes live in `HMI/Alarms/SystemAlarmClasses.xml` / `AlarmClasses.xml`
  (`<Class Name Prio>` with `State Came/CameNA/GoneNA` colors and a `Shortcut` letter); the review
  checks them (ALM-01…05).

## Applying it in EAE with eae-mcp

1. Agree the style guide (palette, fonts, indicator set, alarm classes) and put the colors into the HMI
   theme (`HMI/Colors/*.color.theme`) so displays use **theme tokens**, not hard-coded RGB.
2. Build CAT symbols that carry SA: value + unit + analog bar with normal band + state text + alarm
   indicator (`eae_cat_add_symbol`, then draw in EAE). Faceplates are the level-4 detail.
3. Create the canvas hierarchy with `eae_hmi_canvas_create` / `eae_ehmi_canvas_create` (overview first) and
   place instances with `eae_hmi_place_symbol` / `eae_ehmi_place_symbol`.
4. Run `eae_hmi_review` (optionally `level=1..4` per display) and fix warnings; go through the manual checks.

Review rules: HP-01 background, HP-02 static saturated color, HP-03 palette size, HP-04 alarm colors used
statically, HP-05 images, HP-06 typography, HP-07 text contrast, HP-08 density, HP-09 numbers without
analog context, HP-10 no trend on level-1/2 displays, NAV-01…03 hierarchy, ALM-01…05 alarm classes.
