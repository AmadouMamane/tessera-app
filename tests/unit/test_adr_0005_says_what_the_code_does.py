"""ADR 0005 described a function-calling binding that has never existed.

"The tool registry is assembled at agent startup and exposed to the LLM via LangGraph's
tool-binding mechanism" was the ADR's justification, repeated in three docstrings and in
`CLAUDE.md`'s canonical tree — four artefacts agreeing with each other and none of them with
`src/`. There is no `bind_tools`, no `tool_choice`, no `ToolNode`, no `tools=`. A worker
decides in Python which action to take, builds its arguments in Python, and calls it through
`guarded_invoke`.

ADR 0005 §Amendment 1 settles it: the separation stays, the justification is corrected, and
wiring the function-calling is recorded as a product change with its own evaluation campaign
rather than a refactor.

This witness holds the two together. If the binding is ever wired, it goes red — and the
right response is to update the ADR, not to delete this file.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
_ADR = _REPO / "docs" / "decisions" / "0005-tools-vs-workers-separation.md"

#: The LangChain / LangGraph binding APIs, anywhere in the tree.
_BINDING = re.compile(r"\bbind_tools\s*\(|\btool_choice\s*=|\bToolNode\s*\(")

#: A provider SDK would be handed the schemas as a keyword argument instead, and the only
#: place an SDK is called is `src/tessera/llm/`. Searching for `tools=` tree-wide is useless —
#: it is an ordinary parameter name in the registry, the guard and four observability modules
#: — so this pattern is scoped to where it could only mean one thing. That scoping is a
#: DECLARED limit of this witness: a binding wired from somewhere else would not be seen here.
_SDK_KWARG = re.compile(r"\btools\s*=|\bfunctions\s*=")
_SDK_DIR = "llm"


def _binding_sites() -> list[str]:
    sites: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        in_sdk_layer = path.parent.name == _SDK_DIR
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            hit = _BINDING.search(line) or (in_sdk_layer and _SDK_KWARG.search(line))
            if hit:
                sites.append(f"{path.relative_to(_REPO)}:{number}: {line.strip()}")
    return sites


def test_the_detector_can_see() -> None:
    """It matches the real thing when the real thing is put in front of it (ADR 0026)."""
    assert _BINDING.search("model = llm.bind_tools(TOOLS)")
    assert _BINDING.search("graph.add_node('act', ToolNode(TOOLS))")
    assert _BINDING.search("resp = client.generate(prompt, tool_choice='auto')")
    assert _SDK_KWARG.search("response = client.chat(messages, tools=SCHEMAS)")
    # …and not on the ordinary parameter name that fills this codebase.
    assert not _BINDING.search("from tessera.agent import tools")
    assert not _BINDING.search("tools=_as_str_tuple(raw.get('tools')),")


def test_no_function_calling_binding_exists_in_src() -> None:
    sites = _binding_sites()
    assert not sites, (
        "a function-calling binding has appeared. That is a product change, not a refactor: "
        "letting the model choose the tool changes what the agent does, so the null floor, "
        "the discrimination classification and the catalogue's pass rates all describe a "
        "different system afterwards. Update ADR 0005 §Amendment 1 and re-measure — do not "
        "delete this test.\n  " + "\n  ".join(sites)
    )


def test_the_adr_records_the_correction() -> None:
    """The ADR must carry the amendment, or this file is policing a decision nobody took."""
    text = _ADR.read_text(encoding="utf-8")
    assert "Amendment 1" in text
    assert "has never existed in this repository" in text
    assert "typed action target" in text


def test_no_doc_still_calls_a_tool_llm_callable() -> None:
    """The claim lived in four places at once; a correction in one of them is not a fix."""
    offenders: list[str] = []
    for name in ("CLAUDE.md", "AGENTS.md", "docs/structure.md", "docs/design.md"):
        path = _REPO / name
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "LLM-callable function-call target" in line:
                offenders.append(f"{name}:{number}")
    assert not offenders, (
        "these still describe tools as function-call targets exposed to the model:\n  "
        + "\n  ".join(offenders)
    )
