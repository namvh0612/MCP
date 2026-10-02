"""Tiny simulator for the ST subset that eae-mcp generates (tests only).

Translates statement-per-line ST (IF/ELSIF/ELSE, WHILE, FOR, EXIT, assignments, calls with formal
arguments) to Python and runs it with IEC 61131-3 string semantics (1-based positions, MID(IN, L, P)).
"""

import re


def _lit(m: re.Match) -> str:
    s = m.group(1)
    out, i = [], 0
    while i < len(s):
        if s[i] == "$" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"R": "\r", "N": "\n", "T": "\t", "$": "$", "'": "'"}.get(nxt.upper(), nxt))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return repr("".join(out))


def FIND(s, sub):  # noqa: N802 - IEC names
    i = s.find(sub)
    return i + 1 if i >= 0 else 0


def MID(s, n, p):  # noqa: N802
    return s[p - 1:p - 1 + n] if n > 0 and p >= 1 else ""


LIB = {
    "FIND": FIND, "MID": MID, "LEN": len, "CONCAT": lambda a, b: a + b,
    "LEFT": lambda s, n: s[:max(n, 0)], "RIGHT": lambda s, n: s[len(s) - n:] if n > 0 else "",
    "MIN": min, "UINT_TO_INT": int, "STRING_TO_INT": lambda s: int(s.strip() or 0),
    "STRING_TO_DINT": lambda s: int(s.strip() or 0), "STRING_TO_REAL": lambda s: float(s or 0),
    "STRING_TO_LREAL": lambda s: float(s or 0), "TRUE": True, "FALSE": False,
}


def _expr(e: str) -> str:
    strings: list[str] = []
    e = re.sub(r"'((?:\$.|[^'$])*)'", lambda m: strings.append(_lit(m)) or f"\x00{len(strings) - 1}\x00", e)
    e = re.sub(r"\(\*.*?\*\)", "", e)
    e = re.sub(r"(\w+)\s*:=\s*", "\\1\x01", e)  # formal call arguments Name := value
    e = e.replace("<>", "\x02")
    e = re.sub(r"(?<![<>])=", "==", e)
    e = e.replace("\x01", "=").replace("\x02", "!=")
    e = re.sub(r"\bAND\b", " and ", e)
    e = re.sub(r"\bOR\b", " or ", e)
    e = re.sub(r"\bNOT\b", " not ", e)
    e = re.sub(r"\x00(\d+)\x00", lambda m: strings[int(m.group(1))], e)
    return e


def _call_args(e: str) -> str:
    return e


def translate(st: str) -> str:
    st = re.sub(r"\(\*.*?\*\)", "", st, flags=re.S)
    out, ind = [], 0
    for raw in st.splitlines():
        line = raw.strip()
        if not line:
            continue
        pad = "    " * ind
        m = re.match(r"IF (.*) THEN$", line)
        if m:
            out.append(f"{pad}if {_call_args(_expr(m.group(1)))}:")
            ind += 1
            continue
        m = re.match(r"ELSIF (.*) THEN$", line)
        if m:
            out.append(f"{'    ' * (ind - 1)}elif {_call_args(_expr(m.group(1)))}:")
            continue
        if line == "ELSE":
            out.append(f"{'    ' * (ind - 1)}else:")
            continue
        if line in ("END_IF;", "END_WHILE;", "END_FOR;"):
            out.append(f"{pad}pass")
            ind -= 1
            continue
        m = re.match(r"WHILE (.*) DO$", line)
        if m:
            out.append(f"{pad}while {_call_args(_expr(m.group(1)))}:")
            ind += 1
            continue
        m = re.match(r"FOR (\w+) := (.*) TO (.*) DO$", line)
        if m:
            out.append(f"{pad}for {m.group(1)} in range({_expr(m.group(2))}, ({_expr(m.group(3))}) + 1):")
            ind += 1
            continue
        if line == "EXIT;":
            out.append(f"{pad}break")
            continue
        for stmt in [s for s in line.split(";") if s.strip()]:
            m = re.match(r"\s*(\w+(?:\[[^\]]+\])?)\s*:=\s*(.*)$", stmt)
            if not m:
                raise ValueError(f"unsupported ST: {stmt}")
            out.append(f"{pad}{m.group(1)} = {_call_args(_expr(m.group(2)))}")
    return "\n".join(out)


def run(st: str, env: dict) -> dict:
    code = translate(st)
    scope = dict(LIB)
    scope.update(env)
    exec(compile(code, "<st>", "exec"), scope)  # noqa: S102 - test helper on generated code
    return {k: v for k, v in scope.items() if k not in LIB and not k.startswith("__")}
