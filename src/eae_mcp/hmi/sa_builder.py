"""Generate situation-awareness CAT symbols (.NET HMI and eHMI) from a declarative design.

A design lists *elements*, each bound to a variable of the CAT's HMI interface (IThis input, i.e. data the
CAT sends to the HMI):

- value : label + live number (+ unit) and, with `range`, a moving analog indicator: gray span, normal band,
          alarm-limit ticks and a pointer that turns to the priority color only outside the limits;
- state : label + state text from a value→text table; abnormal states get the priority color at runtime;
- alarm : indicator in the title row: hidden when inactive, shape + color + number of the priority when active
          (BOOL active flag, or INT priority code 0..4);
- text  : label + live string.

Widgets and code follow what EAE itself writes (learned from SolarPlantDemo/golden): static graphics are
gray, colors are only set at runtime by generated code, so the result passes eae_hmi_review.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field

from ..model import Interface
from . import designer as ds
from . import sa_style as st

NL = "\r\n"
T3 = "\t\t\t"

DOTNET_T = {"REAL": ("float", "0F"), "LREAL": ("double", "0D"), "INT": ("short", "((short)(0))"),
            "DINT": ("int", "0"), "UINT": ("ushort", "((ushort)(0))"), "USINT": ("byte", "((byte)(0))"),
            "BYTE": ("byte", "((byte)(0))"), "SINT": ("sbyte", "((sbyte)(0))"), "BOOL": ("bool", "false"),
            "STRING": ("string", "null")}
EHMI_T = {"REAL": "double", "LREAL": "double", "INT": "short", "BOOL": "bool", "STRING": "string"}


class DesignError(ValueError):
    pass


@dataclass
class ElementSpec:
    kind: str  # value | state | alarm | text
    var: str
    label: str | None = None
    unit: str | None = None
    range: tuple[float, float] | None = None  # span of the analog indicator
    normal: tuple[float, float] | None = None  # normal operating range (shaded)
    limits: tuple[float | None, float | None] | None = None  # low / high alarm limits
    priority: int = 2
    states: dict[str, str] = field(default_factory=dict)  # value → text ("true"/"false" for BOOL)
    abnormal: list[str] = field(default_factory=list)  # state values shown as abnormal


@dataclass
class SymbolDesign:
    title: str
    elements: list[ElementSpec]
    width: int = 240


# -- validation --------------------------------------------------------------------------------


def _base(t: str) -> str:
    return t.split("[")[0].upper()


def check_design(d: SymbolDesign, hmi: Interface, technology: str) -> list[str]:
    """Raise DesignError for errors; return warnings."""
    warnings: list[str] = []
    if not d.title.strip() or len(d.title) > 40:
        raise DesignError("title must be 1..40 characters.")
    if not 160 <= d.width <= 600:
        raise DesignError("width must be 160..600 px.")
    if not d.elements:
        raise DesignError("A symbol needs at least one element.")
    types = {v.name: v.type for v in hmi.input_vars if v.name not in ("QI",)}
    carried = {w for e in hmi.event_inputs if e.name != "INIT" for w in e.with_vars}
    seen = set()
    for e in d.elements:
        if e.kind not in ("value", "state", "alarm", "text"):
            raise DesignError(f"{e.var}: kind must be value, state, alarm or text.")
        if e.var not in types:
            raise DesignError(f"'{e.var}' is not an input of the HMI interface (vars: {', '.join(types) or 'none'}). "
                              "Add it with eae_fb_update_interface on <Cat>_HMI first.")
        if (e.kind, e.var) in seen:
            raise DesignError(f"{e.var} is used twice as {e.kind}.")
        seen.add((e.kind, e.var))
        t = _base(types[e.var])
        if t not in DOTNET_T or (technology in ("ehmi", "both") and t not in EHMI_T):
            raise DesignError(f"{e.var}: type {types[e.var]} is not supported for {technology} symbols.")
        if e.var not in carried:
            warnings.append(f"warning: {e.var} is not carried by any HMI input event (WITH); it will never update.")
        if e.kind == "value":
            if t in ("BOOL", "STRING"):
                raise DesignError(f"{e.var}: a value element needs a number, not {t}.")
            if e.range:
                lo, hi = e.range
                if not lo < hi:
                    raise DesignError(f"{e.var}: range must be [low, high] with low < high.")
                for name, pair in (("normal", e.normal), ("limits", e.limits)):
                    for x in pair or ():
                        if x is not None and not lo <= x <= hi:
                            raise DesignError(f"{e.var}: {name} {x} is outside range {e.range}.")
                if e.normal and not e.normal[0] < e.normal[1]:
                    raise DesignError(f"{e.var}: normal must be [low, high].")
            elif e.normal or e.limits:
                raise DesignError(f"{e.var}: normal/limits need a range for the analog indicator.")
            elif not e.range:
                warnings.append(f"info: {e.var} has no range; add range/normal/limits so the operator sees the "
                                "value against its normal band (SA level 2).")
        if e.kind == "state" and not e.states:
            raise DesignError(f"{e.var}: a state element needs states, e.g. {{'0': 'Stopped', '1': 'Running'}}.")
        if e.kind == "state" and t == "BOOL" and not set(e.states) <= {"true", "false"}:
            raise DesignError(f"{e.var}: BOOL states use the keys 'true' and 'false'.")
        if e.kind == "alarm" and t not in ("BOOL", "INT", "SINT", "DINT", "USINT", "BYTE", "UINT"):
            raise DesignError(f"{e.var}: an alarm element needs BOOL (active) or an integer priority code.")
        if e.kind == "text" and t != "STRING":
            raise DesignError(f"{e.var}: a text element needs a STRING.")
        st.priority(e.priority)
        if any(c in (e.label or "") + (e.unit or "") + "".join(e.states.values()) for c in '"\\\r\n'):
            raise DesignError(f"{e.var}: texts must not contain quotes, backslashes or line breaks.")
    return warnings


# -- layout ------------------------------------------------------------------------------------


@dataclass
class Box:
    name: str
    kind: str  # card | title | label | value | state | text | track | band | tick | pointer | alarm | alarmtext | exec
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    var: str | None = None
    element: ElementSpec | None = None
    shape: str | None = None


def _id(s: str) -> str:
    return re.sub(r"\W", "_", s)


def layout(d: SymbolDesign) -> tuple[list[Box], int, int]:
    W = d.width
    pad = 8
    boxes = [Box("card", "card", 0, 0, W, 0), Box("title", "title", pad, 4, W - 2 * pad - 30, 20, d.title)]
    alarms = [e for e in d.elements if e.kind == "alarm"]
    for i, e in enumerate(alarms):
        x = W - pad - 22 - i * 26
        n = _id(e.var)
        boxes.append(Box(f"alm{n}", "alarm", x, 4, 20, 20, var=e.var, element=e))
        boxes.append(Box(f"almTxt{n}", "alarmtext", x + 6, 6, 10, 14, var=e.var, element=e))
        boxes.append(Box(f"x{n}", "exec", 0, 0, 0, 0, var=e.var, element=e))
    y = 30.0
    for e in d.elements:
        n = _id(e.var)
        label = e.label or e.var
        if e.kind == "value":
            text = f"{label} ({e.unit})" if e.unit else label
            boxes.append(Box(f"lbl{n}", "label", pad, y + 3, W - 2 * pad - 90, 18, text, element=e))
            boxes.append(Box(f"val{n}", "value", W - pad - 90, y, 90, 22, var=e.var, element=e))
            y += 26
            if e.range:
                tw = W - 2 * pad
                boxes.append(Box(f"trk{n}", "track", pad, y + 3, tw, 8, element=e))
                lo, hi = e.range

                def px(v: float) -> float:
                    return pad + (v - lo) / (hi - lo) * tw
                if e.normal:
                    boxes.append(Box(f"nrm{n}", "band", px(e.normal[0]), y + 3, px(e.normal[1]) - px(e.normal[0]), 8,
                                     element=e))
                for j, lim in enumerate(e.limits or ()):
                    if lim is not None:
                        boxes.append(Box(f"lim{n}{'LH'[j]}", "tick", px(lim), y, 0, 14, element=e))
                boxes.append(Box(f"ptr{n}", "pointer", pad - 2, y, 4, 14, var=e.var, element=e))
                boxes.append(Box(f"x{n}", "exec", 0, 0, 0, 0, var=e.var, element=e))
                y += 20
        elif e.kind == "state":
            boxes.append(Box(f"lbl{n}", "label", pad, y + 3, W / 2 - pad, 18, label, element=e))
            boxes.append(Box(f"sta{n}", "state", W / 2, y, W / 2 - pad, 22, "—", var=e.var, element=e))
            boxes.append(Box(f"x{n}", "exec", 0, 0, 0, 0, var=e.var, element=e))
            y += 26
        elif e.kind == "text":
            boxes.append(Box(f"lbl{n}", "label", pad, y + 3, W / 2 - pad, 18, label, element=e))
            boxes.append(Box(f"txt{n}", "text", W / 2, y, W / 2 - pad, 22, var=e.var, element=e))
            y += 26
    H = int(y + 6)
    boxes[0].h = H
    return boxes, W, H


# -- .NET HMI --------------------------------------------------------------------------------------


def _c(rgb: st.RGB) -> str:
    r, g, b = rgb
    return f"new NxtControl.Drawing.Color(((byte)({r})), ((byte)({g})), ((byte)({b})))"


def _brush(rgb: st.RGB) -> str:
    return f"new NxtControl.Drawing.Brush({_c(rgb)})"


def _pen(rgb: st.RGB, width: float = 1) -> str:
    return f"new NxtControl.Drawing.Pen({_c(rgb)}, {width:g}F, NxtControl.Drawing.DashStyle.Solid)"


def _font(size: int, bold: bool = False) -> str:
    return f'new NxtControl.Drawing.Font("{st.FONT}", {size}F, System.Drawing.FontStyle.{"Bold" if bold else "Regular"})'


def _rect(b: Box) -> str:
    return ("new NxtControl.Drawing.RectF(" + ", ".join(f"((float)({ds.num(v)}))" for v in (b.x, b.y, b.w, b.h)) + ")")


def _shape_points(b: Box, shape: str) -> list[tuple[float, float]]:
    x, y, w, h = b.x, b.y, b.w, b.h
    if shape == "triangle":
        return [(x + w / 2, y), (x + w, y + h), (x, y + h)]
    if shape == "diamond":
        return [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _dotnet_sections(boxes: list[Box], types: dict[str, str]) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    prelude, sections, fields = [], [], []
    for b in boxes:
        n = b.name
        props: list[tuple[str, str]] = []
        extra: list[str] = []  # multi-line statements placed after the sorted properties
        begin = False
        if b.kind in ("card", "track", "band", "pointer"):
            typ = "NxtControl.GuiFramework.Rectangle"
            color = {"card": st.PANEL, "track": st.TRACK, "band": st.NORMAL_BAND, "pointer": st.POINTER}[b.kind]
            pen = st.BORDER if b.kind in ("card", "track") else color
            props = [("Bounds", _rect(b)), ("Brush", _brush(color)), ("Font", _font(8)), ("Name", f'"{n}"'),
                     ("Pen", _pen(pen))]
        elif b.kind in ("title", "label", "alarmtext"):
            typ = "NxtControl.GuiFramework.FreeText"
            size, bold, color = ((st.SIZE_TITLE, True, st.TEXT) if b.kind == "title" else
                                 (st.SIZE_TEXT, True, st.TEXT) if b.kind == "alarmtext" else (st.SIZE_TEXT, False, st.TEXT_2))
            props = [("Color", _c(color)), ("Font", _font(size, bold)), ("Location",
                     f"new NxtControl.Drawing.PointF({ds.num(b.x)}, {ds.num(b.y)})"), ("Name", f'"{n}"'),
                     ("Text", ds.string(b.text))]
            if b.kind == "alarmtext":
                props += [("Visible", "false")]
        elif b.kind == "tick":
            typ = "NxtControl.GuiFramework.Line"
            props = [("EndPoint", f"new NxtControl.Drawing.PointF({ds.num(b.x)}, {ds.num(b.y + b.h)})"),
                     ("Name", f'"{n}"'), ("Pen", _pen(st.LIMIT, 2)),
                     ("StartPoint", f"new NxtControl.Drawing.PointF({ds.num(b.x)}, {ds.num(b.y)})")]
        elif b.kind == "alarm":
            shape = st.priority(b.element.priority).shape
            if shape == "circle":
                typ = "NxtControl.GuiFramework.Ellipse"
                props = [("Bounds", _rect(b)), ("Brush", _brush(st.INDICATOR_IDLE)), ("Font", _font(8)),
                         ("Name", f'"{n}"'), ("Pen", _pen(st.BORDER))]
            else:
                typ = "NxtControl.GuiFramework.Polygon"
                props = [("Bounds", _rect(b)), ("Brush", _brush(st.INDICATOR_IDLE)), ("Closed", "true"),
                         ("Font", _font(8)), ("Name", f'"{n}"'), ("Pen", _pen(st.BORDER))]
                pts = _shape_points(b, shape)
                extra = [f"{T3}this.{n}.Points.AddRange(new NxtControl.Drawing.PointF[] {{"]
                extra += [f"{T3}new NxtControl.Drawing.PointF({ds.num(px)}, {ds.num(py)})," for px, py in pts]
                extra[-1] = extra[-1][:-1] + "});"
            props += [("Visible", "false")]
        elif b.kind == "value":
            ct, zero = DOTNET_T[_base(types[b.var])]
            typ = f"System.HMI.Symbols.Base.TextBox<{ct}>"
            begin = True
            props = [("Brush", 'new NxtControl.Drawing.Brush("Transparent")'),
                     ("DesignMatrix", ds.matrix(b.x, b.y, b.w / 250, b.h / 27)), ("IgnoreMouseEvents", "true"),
                     ("IsOnlyInput", "true"), ("IsPrefixSuffixOutside", "false"), ("Name", f'"{n}"'),
                     ("NumberBase", "NxtControl.GuiFramework.NumberBase.Decimal"),
                     ("Pen", 'new NxtControl.Drawing.Pen("Transparent")'), ("TagName", ds.string(b.var)),
                     ("TextAlignment", "NxtControl.Drawing.ContentAlignment.MiddleRight"), ("Value", zero)]
        elif b.kind == "text":
            typ = "System.HMI.Symbols.Base.Label"
            begin = True
            props = [("BorderStyle", "System.Windows.Forms.BorderStyle.None"),
                     ("DesignMatrix", ds.matrix(b.x, b.y)), ("FontScale", "false"), ("IsOnlyInput", "true"),
                     ("Name", f'"{n}"'), ("Pen", 'new NxtControl.Drawing.Pen("LabelPen")'), ("TagName", ds.string(b.var))]
        elif b.kind == "state":
            typ = "NxtControl.GuiFramework.Label"
            props = [("AngleIgnore", "true"), ("BorderStyle", "System.Windows.Forms.BorderStyle.None"),
                     ("Bounds", _rect(b)), ("Brush", 'new NxtControl.Drawing.Brush("Transparent")'),
                     ("Font", _font(st.SIZE_TEXT, True)), ("FontScale", "true"), ("Name", f'"{n}"'),
                     ("Pen", 'new NxtControl.Drawing.Pen("Transparent")'), ("Text", ds.string(b.text)),
                     ("TextAlignment", "NxtControl.Drawing.ContentAlignment.MiddleLeft"),
                     ("TextAutoSizeHorizontalOffset", "10"), ("TextColor", _c(st.TEXT)),
                     ("TextPadding", "new NxtControl.Drawing.Padding(2)")]
        elif b.kind == "exec":
            ct, zero = DOTNET_T[_base(types[b.var])]
            typ = f"System.HMI.Symbols.Base.Execute<{ct}>"
            begin = True
            props = [("DesignMatrix", "new NxtControl.Drawing.Matrix2D(1D, 0D, 0D, 1D, double.NaN, double.NaN)"),
                     ("IsOnlyInput", "true"), ("Location", "new NxtControl.Drawing.PointF(double.NaN, double.NaN)"),
                     ("Name", f'"{n}"'), ("Size", "new NxtControl.Drawing.SizeF(double.NegativeInfinity, "
                                                  "double.NegativeInfinity)"),
                     ("TagName", ds.string(b.var)), ("Value", zero),
                     ("ValueChanged", f"new System.EventHandler<NxtControl.GuiFramework.ValueChangedEventArgs>"
                                      f"(this.{n}ValueChanged)")]
        else:
            raise DesignError(b.kind)
        prelude.append(f"{T3}this.{n} = new {typ}();")
        lines = [f"{T3}this.{n}.BeginInit();"] if begin else []
        entries = [(p, [f"{T3}this.{n}.{p} {'+=' if p == 'ValueChanged' else '='} {v};"]) for p, v in props]
        if extra:
            entries.append(("Points", extra))  # multi-line statement, kept at its alphabetical place
        for _, ls in sorted(entries, key=lambda e: e[0].lower()):
            lines += ls
        if begin:
            lines.append(f"{T3}this.{n}.EndInit();")
        sections.append((n, lines))
        fields.append(f"\t\tprivate {typ} {n};")
    return prelude, sections, fields


def dotnet_designer(header: str, ns: str, sym: str, boxes: list[Box], types: dict[str, str], W: int, H: int) -> str:
    prelude, sections, fields = _dotnet_sections(boxes, types)
    shapes = [n for n, _ in sections]
    body = "".join(p + NL for p in prelude)
    parts = [f"{T3}// {NL}{T3}// {n}{NL}{T3}// {NL}" + NL.join(lines) for n, lines in sections]
    own = [f"{T3}this.Shapes.AddRange(new System.ComponentModel.IComponent[] {{"]
    own += [f"{T3}this.{n}," for n in shapes]
    own[-1] = own[-1][:-1] + "});"
    own.append(f"{T3}this.SymbolSize = new System.Drawing.Size({W}, {H});")
    parts.append(f"{T3}// {NL}{T3}// {sym}{NL}{T3}// {NL}" + NL.join(own) + NL)
    text = (header + NL.join(["using System;", "using System.ComponentModel;", "using System.Collections;",
                              "using NxtControl.GuiFramework;", "", f"namespace {ns}", "{", "\t/// <summary>",
                              f"\t/// Summary description for {sym}.", "\t/// </summary>", f"\tpartial class {sym}", "\t{",
                              "", "\t\t#region Component Designer generated code", "\t\t/// <summary>",
                              "\t\t/// Required method for Designer support - do not modify",
                              "\t\t/// the contents of this method with the code editor.", "\t\t/// </summary>",
                              "\t\tprivate void InitializeComponent()", "\t\t{", ""])
            + body + NL.join(parts) + f"{NL}\t\t}}{NL}" + "".join(f + NL for f in fields)
            + NL.join(["\t\t#endregion", "\t}", "}", ""]))
    ds.parse(text)  # must fit the constrained model so later edits work
    return text


def _cs_color(rgb: st.RGB) -> str:
    return f"new NxtControl.Drawing.Color((byte){rgb[0]}, (byte){rgb[1]}, (byte){rgb[2]})"


def dotnet_code_behind(header: str, ns: str, sym: str, boxes: list[Box], types: dict[str, str]) -> str:
    """C# event handlers: move pointers, color abnormal values/states, show alarm indicators."""
    m: list[str] = []
    for b in boxes:
        if b.kind != "exec":
            continue
        e = b.element
        n = _id(e.var)
        p = st.priority(e.priority)
        m += ["", f"\t\tvoid {b.name}ValueChanged(object sender, ValueChangedEventArgs e)", "\t\t{"]
        if e.kind == "value":
            ptr = next(x for x in boxes if x.name == f"ptr{n}")
            trk = next(x for x in boxes if x.name == f"trk{n}")
            lo, hi = e.range
            low, high = (e.limits or (None, None))
            cond = " || ".join(c for c in ((f"v < {low!r}" if low is not None else ""),
                                           (f"v > {high!r}" if high is not None else "")) if c) or "false"
            m += ["\t\t\tdouble v;", "\t\t\ttry { v = Convert.ToDouble(e.Value); } catch (Exception) { return; }",
                  f"\t\t\tdouble k = (v - {lo!r}) / ({hi!r} - {lo!r});",
                  "\t\t\tif (k < 0) k = 0; else if (k > 1) k = 1;",
                  f"\t\t\tfloat x = (float)({trk.x!r} + k * {trk.w!r}) - 2F;",
                  f"\t\t\tbool abnormal = {cond};",
                  f"\t\t\tptr{n}.Bounds = new NxtControl.Drawing.RectF(x, {ptr.y!r}F, abnormal ? 6F : 4F, {ptr.h!r}F);",
                  f"\t\t\tptr{n}.Brush = new NxtControl.Drawing.Brush(abnormal ? {_cs_color(p.color)} : {_cs_color(st.POINTER)});"]
        elif e.kind == "state":
            is_bool = _base(types[e.var]) == "BOOL"
            m += ["\t\t\tstring key = e.Value == null ? \"\" : " +
                  ("((bool)e.Value ? \"true\" : \"false\");" if is_bool else "e.Value.ToString();"),
                  "\t\t\tstring text = key;", "\t\t\tbool abnormal = false;", "\t\t\tswitch (key)", "\t\t\t{"]
            for k, v in e.states.items():
                m += [f"\t\t\t\tcase \"{k}\": text = \"{v}\"; abnormal = {'true' if k in e.abnormal else 'false'}; break;"]
            m += ["\t\t\t}", f"\t\t\tsta{n}.Text = text;",
                  f"\t\t\tsta{n}.Brush = abnormal ? new NxtControl.Drawing.Brush({_cs_color(p.color)}) : "
                  "new NxtControl.Drawing.Brush(\"Transparent\");",
                  f"\t\t\tsta{n}.TextColor = abnormal ? {_cs_color(p.text_color)} : {_cs_color(st.TEXT)};"]
        elif e.kind == "alarm":
            if _base(types[e.var]) == "BOOL":
                m += [f"\t\t\tint level = (e.Value != null && (bool)e.Value) ? {e.priority} : 0;"]
            else:
                m += ["\t\t\tint level = 0;", "\t\t\ttry { level = Convert.ToInt32(e.Value); } catch (Exception) { }"]
            m += ["\t\t\tNxtControl.Drawing.Color c;", "\t\t\tswitch (level)", "\t\t\t{"]
            for lvl, pr in st.PRIORITIES.items():
                m += [f"\t\t\t\tcase {lvl}: c = {_cs_color(pr.color)}; break;"]
            m += ["\t\t\t\tdefault: c = " + _cs_color(st.INDICATOR_IDLE) + "; break;", "\t\t\t}",
                  f"\t\t\talm{n}.Brush = new NxtControl.Drawing.Brush(c);", f"\t\t\talm{n}.Visible = level > 0;",
                  f"\t\t\talmTxt{n}.Text = level > 0 ? level.ToString() : \"\";", f"\t\t\talmTxt{n}.Visible = level > 0;"]
        m.append("\t\t}")
    return (header + NL.join(["", "using System;", "using NxtControl.GuiFramework;", "", f"namespace {ns}", "{",
                              "\t/// <summary>", f"\t/// {sym}: situation-awareness symbol generated by eae-mcp.",
                              "\t/// </summary>", f"\tpublic partial class {sym} : NxtControl.GuiFramework.HMISymbol", "\t{",
                              f"\t\tpublic {sym}()", "\t\t{", "\t\t\t//",
                              "\t\t\t// The InitializeComponent() call is required for Windows Forms designer support.",
                              "\t\t\t//", "\t\t\tInitializeComponent();", "\t\t}"] + m + ["\t}", "}", ""]))


def dotnet_resx(template: bytes, boxes: list[Box], W: int, H: int) -> bytes:
    text = template.decode("utf-8-sig")
    meta = "".join(f'  <metadata name="{b.name}.Name" xml:space="preserve">{NL}    <value>{b.name}</value>{NL}'
                   f"  </metadata>{NL}" for b in boxes)
    text = text.replace('  <metadata name="$this.Size"', meta + '  <metadata name="$this.Size"', 1)
    text = text.replace("<value>600, 400</value>", f"<value>{W}, {H}</value>", 1)
    return text.encode("utf-8")


# -- eHMI --------------------------------------------------------------------------------------------


def _jc(rgb: st.RGB) -> list:
    return [rgb[0], rgb[1], rgb[2], 1]


def ehmi_objects(boxes: list[Box], types: dict[str, str]) -> list[dict]:
    out = []
    for b in boxes:
        n = b.name
        if b.kind in ("card", "track", "band", "pointer", "alarm"):
            color = {"card": st.PANEL, "track": st.TRACK, "band": st.NORMAL_BAND, "pointer": st.POINTER,
                     "alarm": st.INDICATOR_IDLE}[b.kind]
            shape = st.priority(b.element.priority).shape if b.kind == "alarm" else "square"
            o = {"type": "NxtControl.GuiFramework.Ellipse" if shape == "circle" else "NxtControl.GuiFramework.Rectangle",
                 "name": n, "left": b.x, "top": b.y, "width": b.w, "height": b.h, "brush": {"color": _jc(color)},
                 "pen": {"color": _jc(st.BORDER if b.kind in ("card", "track", "alarm") else color)}}
            if b.kind == "alarm":
                o["visible"] = False
                if shape == "diamond":
                    o["radius"] = 6
            out.append(o)
        elif b.kind in ("title", "label", "alarmtext"):
            o = {"type": "NxtControl.GuiFramework.FreeText", "name": n, "left": b.x, "top": b.y, "width": b.w,
                 "height": b.h, "text": b.text,
                 "fontSize": st.SIZE_TITLE if b.kind == "title" else st.SIZE_TEXT, "fontFamily": st.FONT,
                 "fontStyle": "normal", "textColor": _jc(st.TEXT_2 if b.kind == "label" else st.TEXT)}
            if b.kind != "label":
                o["fontWeight"] = "bold"
            if b.kind == "alarmtext":
                o["visible"] = False
            out.append(o)
        elif b.kind == "tick":
            out.append({"type": "NxtControl.GuiFramework.Rectangle", "name": n, "left": b.x - 1, "top": b.y,
                        "width": 2, "height": b.h, "brush": {"color": _jc(st.LIMIT)}, "pen": {"color": _jc(st.LIMIT)}})
        elif b.kind in ("value", "text"):
            out.append({"type": "System.WEB.Symbols.Base.Label", "name": n, "left": b.x, "top": b.y, "width": b.w,
                        "height": b.h, "brush": {"color": "Transparent"}, "pen": {"color": "Transparent"},
                        "text": "${Value}", "backColor": "Transparent", "textColor": _jc(st.TEXT),
                        "prefixColor": _jc(st.TEXT_2), "suffixColor": _jc(st.TEXT_2), "tagName": b.var,
                        "valueType": EHMI_T[_base(types[b.var])], "numberBase": 0,
                        "ranges": {"defaultProps": {"text": "${Value}", "pen": {"color": "Transparent"},
                                                    "backColor": "Transparent", "textColor": _jc(st.TEXT)},
                                   "range": []}})
        elif b.kind == "state":
            out.append({"type": "NxtControl.GuiFramework.FreeText", "name": n, "left": b.x, "top": b.y + 3,
                        "width": b.w, "height": 18, "text": b.text, "fontSize": st.SIZE_TEXT, "fontFamily": st.FONT,
                        "fontStyle": "normal", "fontWeight": "bold", "textColor": _jc(st.TEXT)})
        elif b.kind == "exec":
            out.append({"type": "System.WEB.Symbols.Base.Execute", "name": n, "left": None, "top": None,
                        "_events_": [{"name": "valueChanged", "eventName": f"{n}_valueChanged"}], "tagName": b.var,
                        "valueType": EHMI_T[_base(types[b.var])], "isOnlyInput": True})
    return out


def _ts_color(rgb: st.RGB) -> str:
    return f"[{rgb[0]}, {rgb[1]}, {rgb[2]}, 1]"


def ehmi_ts(header: str, ns: str, sym: str, boxes: list[Box], types: dict[str, str]) -> str:
    m: list[str] = []
    for b in boxes:
        if b.kind != "exec":
            continue
        e = b.element
        n = _id(e.var)
        p = st.priority(e.priority)
        m += ["", f"    protected {b.name}_valueChanged(sender: any, ea: any) {{", "      const raw = this.ev(sender, ea);"]
        if e.kind == "value":
            ptr = next(x for x in boxes if x.name == f"ptr{n}")
            trk = next(x for x in boxes if x.name == f"trk{n}")
            lo, hi = e.range
            low, high = (e.limits or (None, None))
            cond = " || ".join(c for c in ((f"v < {low!r}" if low is not None else ""),
                                           (f"v > {high!r}" if high is not None else "")) if c) or "false"
            m += ["      const v = Number(raw);", "      if (isNaN(v)) return;",
                  f"      const k = Math.min(1, Math.max(0, (v - {lo!r}) / ({hi!r} - {lo!r})));",
                  f"      const abnormal = {cond};",
                  f"      const ptr = this.find('ptr{n}');",
                  f"      this.put(ptr, 'left', {trk.x!r} + k * {trk.w!r} - 2);",
                  f"      this.put(ptr, 'width', abnormal ? 6 : {ptr.w!r});",
                  f"      this.put(ptr, 'brush', {{ color: abnormal ? {_ts_color(p.color)} : {_ts_color(st.POINTER)} }});"]
        elif e.kind == "state":
            table = json.dumps(e.states)
            m += ["      const key = raw === true ? 'true' : raw === false ? 'false' : String(raw);",
                  f"      const texts: any = {table};", f"      const abnormalKeys: string[] = {json.dumps(e.abnormal)};",
                  "      const abnormal = abnormalKeys.indexOf(key) >= 0;",
                  f"      const lbl = this.find('sta{n}');",
                  "      this.put(lbl, 'text', texts[key] !== undefined ? texts[key] : key);",
                  f"      this.put(lbl, 'textColor', abnormal ? {_ts_color(p.color)} : {_ts_color(st.TEXT)});"]
        elif e.kind == "alarm":
            colors = json.dumps({str(k): list(v.color) + [1] for k, v in st.PRIORITIES.items()})
            if _base(types[e.var]) == "BOOL":
                m += [f"      const level = raw === true || raw === 'true' ? {e.priority} : 0;"]
            else:
                m += ["      const level = Math.round(Number(raw)) || 0;"]
            m += [f"      const colors: any = {colors};", f"      const shape = this.find('alm{n}');",
                  f"      const text = this.find('almTxt{n}');",
                  "      this.put(shape, 'visible', level > 0);", "      this.put(text, 'visible', level > 0);",
                  "      if (level > 0) {", "        this.put(shape, 'brush', { color: colors[String(level)] || colors['1'] });",
                  "        this.put(text, 'text', String(level));", "      }"]
        m.append("    }")
    helpers = ["", "    private ev(sender: any, ea: any): any {",
               "      if (ea) { if (ea.value !== undefined) return ea.value; if (ea.Value !== undefined) return ea.Value; }",
               "      if (sender) { if (sender.value !== undefined) return sender.value; "
               "if (sender.Value !== undefined) return sender.Value; }",
               "      return null;", "    }", "",
               "    private put(obj: any, key: string, value: any): void {",
               "      if (!obj) return;", "      if (obj._set) obj._set(key, value, true); else obj[key] = value;", "    }"]
    return (header + NL.join([f"namespace {ns} {{", "", f"  export class {sym} extends NxtControl.GuiFramework.RuntimeSymbol {{",
                              "", "    /**", "     * Type of an object (never change this)", "     * @type String",
                              "     * @default", "     */", f"    @System.DefaultValue('{ns}.{sym}')",
                              "    protected type: string;", "", "    /**** DO NOT DELETE CONSTRUCTOR *****/",
                              "    constructor() {", "      // do not delete next line", "      super();", "    }"]
                             + m + helpers + ["  } ", "}", ""]))


# -- design review gate -----------------------------------------------------------------------------


def gate(technology: str, name: str, designer_text: str | None, json_data: dict | None) -> list[dict]:
    """Run eae_hmi_review rules on the generated content; generated symbols must have no warnings."""
    from . import review as rv
    found = []
    if designer_text is not None:
        found += rv.review_display(rv.extract_dotnet(name, "", designer_text), {})
    if json_data is not None:
        found += rv.review_display(rv.extract_ehmi(name, "", json_data), {})
    return [vars(f) for f in found if f.severity == "warning"]


def stamp(now: _dt.datetime | None = None) -> dict[str, str]:
    now = now or _dt.datetime.now()
    return {"DATE": f"{now.month}/{now.day}/{now.year}", "TIME": now.strftime("%I:%M %p").lstrip("0")}


# -- draft from the HMI interface --------------------------------------------------------------------

_ALARM = re.compile(r"alarm|alm|fault|trip|prio", re.I)
_STATE = re.compile(r"state|status|mode|run|open|close|on$|enable|ready|auto", re.I)


def suggest(hmi: Interface, title: str) -> dict:
    """A draft design from the HMI interface plus the engineering data still missing.

    Never invents ranges, limits or state texts: those come from the description or the user.
    """
    elements, questions = [], []
    for v in hmi.input_vars:
        if v.name in ("QI",):
            continue
        t = _base(v.type)
        if t == "STRING":
            elements.append({"kind": "text", "var": v.name})
        elif _ALARM.search(v.name) and t in ("BOOL", "INT", "SINT", "DINT", "USINT", "BYTE", "UINT"):
            elements.append({"kind": "alarm", "var": v.name, "priority": 2})
            questions.append(f"{v.name}: alarm priority (1 critical … 4 low)" +
                             ("" if t == "BOOL" else ", or confirm it carries the priority code 0..4"))
        elif t == "BOOL" or (_STATE.search(v.name) and t in DOTNET_T and t not in ("REAL", "LREAL")):
            states = {"false": "Off", "true": "On"} if t == "BOOL" else {}
            elements.append({"kind": "state", "var": v.name, "states": states, "abnormal": []})
            questions.append(f"{v.name}: state texts" + (" (default Off/On)" if t == "BOOL" else " for each value")
                             + " and which states are abnormal")
        elif t in DOTNET_T:
            elements.append({"kind": "value", "var": v.name, "unit": None, "range": None, "normal": None,
                             "limits": None})
            questions.append(f"{v.name}: unit, span [low, high], normal range, low/high alarm limits")
    order = {"alarm": 0, "value": 1, "state": 2, "text": 3}
    elements.sort(key=lambda e: order[e["kind"]])
    return {"title": title, "elements": elements, "missing": questions,
            "note": "Fill units/ranges/limits/state texts from the description or ask the engineer; "
                    "do not guess limits. Then call eae_hmi_symbol_build."}
