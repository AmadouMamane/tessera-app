"""A verdict carries its evidence, or it is not a verdict.

[ADR 0026](../../docs/decisions/0026-a-witness-interrogates-the-thing.md) closed with a
prediction and an admission: the class was *not* closed by construction — "the pattern is
semantic, not syntactic" — and so "when the fourth appears, it will appear the same way the
first three did: as a green light over a hole."

It was already there, green, while the ADR was being written. `make claim` — the tool built to
stop two agents writing into one worktree — resolved an agent's identity from the **name of the
directory it was standing in** (`scripts/worktree_owner.py`, `whoami()`). Every Claude session in
`agents/claude/` therefore resolved to the owner `"claude"`, read the marker, **found its own name
in it, and concluded it was home.** Seven live sessions had their working directory in that tree
on 2026-07-13. The marker never refused any of them. It was not identifying a *writer*; it was
identifying a *role* — the neighbourhood, one more time, in the very instrument built to police
the neighbourhood.

There is no syntactic net for "asked the wrong question". But there *is* one for the shape the
wrong answer always takes, and this module is it.

Every one of those failures reduced a verdict to a **bit** and threw the evidence away. `check()`
returned ``0``; the ratchet returned ``True``; `dev-status` printed a green tick. A bit cannot be
interrogated. You cannot ask ``True`` *what it looked at*, and so nobody ever did — for three
incidents and, it turns out, four.

So make the bit unrepresentable:

    Verdict = Ok(evidence) | NotOk(reason) | CannotSay(blind_spot)

* **``Ok`` cannot be constructed without its evidence.** ``evidence`` is a required field with no
  default, and the empty string is rejected. A witness that observed nothing has *nothing to pass
  to the constructor* — it is structurally unable to fabricate an ``Ok``. This is ADR 0026's
  corollary ("a witness that cannot see must report a blind spot; it may never report *ok*")
  demoted from a rule people must remember into a rule the type system enforces. It is also the
  eval screen's first criterion — *never a verdict without its proof* — brought down from the UI
  into the code.

* **``CannotSay`` is a first-class state**, not a degenerate ``NotOk`` and emphatically not an
  ``Ok``. "I could not look" and "I looked and it was fine" are different facts, and every one of
  the incidents above consisted of a system that could not tell them apart.

* **A ``Verdict`` may not be used as a boolean.** ``__bool__`` raises. Without that line the type
  is decoration: ``if check(path):`` would read a ``NotOk`` — *and a ``CannotSay``* — as **true**,
  because every object is truthy, and we would have rebuilt the original bug on top of the fix.

What this does *not* claim: it does not stop anyone asking the neighbourhood. It stops them
**publishing the answer without saying what they asked**. That is the part that was expensive.

The debt is declared, not hidden: `tests/unit/test_verdict_debt.py` freezes the number of
witnesses in this repo that still return a bare ``bool``. It is a number that must go down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, NoReturn, assert_never, final

__all__ = [
    "EXIT_OK",
    "EXIT_REFUSED",
    "CannotSay",
    "NotOk",
    "Ok",
    "Verdict",
    "exit_code",
    "render",
]

#: The witness looked, and what it saw is good.
EXIT_OK: Final = 0

#: **Do not proceed.** Both a refusal (``NotOk``) and a blind spot (``CannotSay``) exit with this
#: code, and that is deliberate: to a caller — a Makefile, a CI step — they mean the same thing,
#: *stop*. The reason they mean it differs enormously, and that difference is carried where a human
#: reads it (``render`` prints ``[NOT OK]`` or ``[CANNOT SAY]``) rather than in a third exit code
#: that some shell, somewhere, would eventually treat as success. ``2`` and not ``1`` so "you may
#: not proceed" stays distinguishable from "I crashed".
EXIT_REFUSED: Final = 2


class _Verdict:
    """Base of the three verdicts. It exists for exactly one reason: to forbid ``bool(verdict)``.

    Every object in Python is truthy. So ``if check(tree):`` — the most natural line a caller will
    ever write — would silently treat a refusal and a blind spot as success. That is not a
    hypothetical: it is the shape of all four incidents this module answers. The failure must not
    be *discouraged*; it must be **impossible**.
    """

    __slots__ = ()

    def __bool__(self) -> NoReturn:
        """Refuse to be a bit. Loudly, with the reason, at the exact line that tried."""
        raise TypeError(
            f"{type(self).__name__} is a Verdict, not a boolean — and every object is truthy, so "
            "`if check(...):` would read a NotOk (and a CannotSay!) as SUCCESS. That is the bug "
            "this type exists to make unrepresentable (ADR 0026: a witness that cannot see may "
            "never report 'ok'). Match on it:\n"
            "    match check(...):\n"
            "        case Ok(evidence): ...\n"
            "        case NotOk(reason): ...\n"
            "        case CannotSay(blind_spot): ..."
        )


@final
@dataclass(frozen=True, slots=True)
class Ok(_Verdict):
    """The witness looked, and here is **what it looked at**.

    ``evidence`` has no default and may not be empty. This is the entire load-bearing design: a
    witness with nothing to report cannot construct this class, because it has nothing to pass.
    An ``Ok`` therefore always arrives carrying the answer to *"and what did you actually examine?"*
    — the question nobody asked ``True`` for three incidents running.

    Args:
        evidence: What was observed, in a sentence a human can check. Not a restatement of the
            verdict ("the check passed") but the *fact* that produced it ("session 3797cfdf holds
            this tree since 12:36, pid 14340 alive").
    """

    evidence: str

    def __post_init__(self) -> None:
        """Reject the empty evidence — the one way an ``Ok`` could still be fabricated."""
        if not self.evidence.strip():
            raise ValueError(
                "Ok('') is not a verdict: an empty string is not evidence. Name the thing you "
                "actually examined, or say CannotSay — which is an honest answer, and free."
            )


@final
@dataclass(frozen=True, slots=True)
class NotOk(_Verdict):
    """The witness looked, and it is **not** fine. ``reason`` says why, in the caller's terms.

    Args:
        reason: What is wrong, and — where the fix is knowable — how to make it right.
    """

    reason: str

    def __post_init__(self) -> None:
        """A refusal without a reason sends the reader hunting. Refuse it."""
        if not self.reason.strip():
            raise ValueError("NotOk('') tells the reader nothing. Say what is wrong.")


@final
@dataclass(frozen=True, slots=True)
class CannotSay(_Verdict):
    """The witness **could not look**. This is a fact to publish, never a reason to pass.

    The state that did not exist, and whose absence cost three weeks of green lights over holes.
    It is not a soft failure and it is not a warning: it is the honest report of a **blind spot**,
    and it exits non-zero precisely so that nobody may proceed on the strength of it.

    Args:
        blind_spot: What could not be observed, and what would let the next caller observe it.
    """

    blind_spot: str

    def __post_init__(self) -> None:
        """An unnamed blind spot is indistinguishable from no blind spot. Refuse it."""
        if not self.blind_spot.strip():
            raise ValueError(
                "CannotSay('') is a blind spot about a blind spot. Name what you could not see."
            )


#: The closed union. Deliberately an alias over three ``@final`` classes rather than an open base
#: class: ``render`` and ``exit_code`` match on it exhaustively under ``assert_never``, so a fourth
#: verdict invented tomorrow cannot be added without every consumer being made to handle it —
#: mypy fails the build until they do. Illegal states unrepresentable (ADR 0019 §I1).
Verdict = Ok | NotOk | CannotSay


def render(verdict: Verdict) -> str:
    """One line, prefixed with the verdict's name, carrying its payload.

    The prefix is not decoration. ``[CANNOT SAY]`` in a terminal is the difference between an
    operator who knows there is a hole and an operator who thinks the check passed.

    Args:
        verdict: The verdict to render.

    Returns:
        A single line, e.g. ``[CANNOT SAY] no TESSERA_SESSION_ID in the environment``.
    """
    match verdict:
        case Ok(evidence=evidence):
            return f"[OK] {evidence}"
        case NotOk(reason=reason):
            return f"[NOT OK] {reason}"
        case CannotSay(blind_spot=blind_spot):
            return f"[CANNOT SAY] {blind_spot}"
    assert_never(verdict)  # pragma: no cover — exhaustive; the line exists so mypy proves it is


def exit_code(verdict: Verdict) -> int:
    """The process's verdict, as a number a Makefile can act on.

    ``Ok`` — and only ``Ok`` — is ``0``. A ``CannotSay`` exits ``2``, exactly like a refusal,
    because a caller that proceeds on a blind spot has done the thing all four incidents did.

    Args:
        verdict: The verdict to translate.

    Returns:
        :data:`EXIT_OK` for :class:`Ok`, :data:`EXIT_REFUSED` for the other two.
    """
    match verdict:
        case Ok():
            return EXIT_OK
        case NotOk() | CannotSay():
            return EXIT_REFUSED
    assert_never(verdict)  # pragma: no cover — exhaustive; the line exists so mypy proves it is
