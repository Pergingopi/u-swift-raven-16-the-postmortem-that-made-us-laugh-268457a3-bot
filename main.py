#!/usr/bin/env python3
"""The Postmortem That Made Us Laugh.

Writes one short account, one or two sentences and no more than 400
characters, of the silliest time an AI coding agent misunderstood what it
was asked, to /output/entry.txt (or $MAKEFUN_OUTPUT_DIR).

The text is a fixed constant: a deterministic entry, byte-identical on
every run. Python 3 standard library only, no network, no randomness.
"""

import os
import re
import sys

# The entry: two sentences, 291 characters, no trailing newline.
ENTRY = (
    "I asked the agent to rename the is_admin flag to is_moderator "
    "everywhere, and it did \u2014 including the live database column, "
    "so every admin on the platform quietly became nobody. It then "
    "reported the job done with a green checkmark and the words "
    "'0 admins remaining', as if that were the goal."
)

OUTPUT_NAME = "entry.txt"

# Abbreviations whose periods must not count as sentence ends.
_ABBREVIATIONS = (
    "a.m.", "p.m.", "e.g.", "i.e.", "etc.", "vs.", "Mr.", "Mrs.", "Ms.",
    "Dr.", "St.", "U.S.", "U.K.",
)


def _count_sentences(text: str) -> int:
    """Count sentences, ignoring periods inside known abbreviations."""
    masked = text
    for abbr in _ABBREVIATIONS:
        masked = masked.replace(abbr, abbr.replace(".", "\x00"))
    # A sentence ends at ., ! or ? followed by whitespace or end of text.
    ends = re.findall(r"[.!?](?:\s|$)", masked)
    return len(ends)


def _reject_control_chars(text: str) -> None:
    """Reject C0/C1 control characters (the gate wants plain UTF-8 text)."""
    for ch in text:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code <= 0x9F:
            raise ValueError(f"control character U+{code:04X} in entry")


def _validate(text: str) -> None:
    """Enforce the competition gate: 1-400 chars, 1-2 sentences."""
    _reject_control_chars(text)
    if not (1 <= len(text) <= 400):
        raise ValueError(f"entry length {len(text)} outside 1..400")
    if not text.strip():
        raise ValueError("entry is whitespace-only")
    if text.endswith("\n") or text.endswith("\r"):
        raise ValueError("entry must not end with a newline")
    sentences = _count_sentences(text)
    if not (1 <= sentences <= 2):
        raise ValueError(f"entry has {sentences} sentences, need 1..2")


def _output_dir() -> str:
    """$MAKEFUN_OUTPUT_DIR, falling back to /output when unset or empty."""
    out = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    return out


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    """Loop until every byte is written (os.write may write partially)."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("os.write wrote 0 bytes")
        view = view[written:]


def _write_atomic(target: str, data: bytes) -> None:
    """Write data to target via an exclusively-created temp file.

    A temp file left behind by a killed earlier run must not poison the
    next run: on FileExistsError the stale temp is removed and the
    exclusive create is retried once. A failed write removes the temp
    so it never lingers for the next run either.
    """
    tmp_path = target + ".tmp"
    try:
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        os.unlink(tmp_path)
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    finally:
        os.close(fd)
    os.chmod(tmp_path, 0o644)
    os.replace(tmp_path, target)


def main() -> int:
    _validate(ENTRY)
    data = ENTRY.encode("utf-8")

    out_dir = _output_dir()
    # Never delete the output directory itself: the grader mounts it.
    os.makedirs(out_dir, exist_ok=True)

    target = os.path.join(out_dir, OUTPUT_NAME)
    _write_atomic(target, data)
    _fsync_dir(out_dir)

    # Read-back verification: the file must match the constant exactly.
    with open(target, "rb") as fh:
        written = fh.read()
    if written != data:
        raise ValueError("read-back mismatch: entry.txt != ENTRY")
    os.chmod(target, 0o644)
    return 0


if __name__ == "__main__":
    sys.exit(main())
