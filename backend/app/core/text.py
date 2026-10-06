"""Conservative text repair shared by collection and read-time presentation."""

from __future__ import annotations

_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "Ð", "Ø", "Ù")


def repair_common_mojibake(value: str) -> str:
    """Undo one common UTF-8-as-Latin-1 decode only when signals improve."""
    before = _mojibake_score(value)
    if before == 0:
        return value
    try:
        encoded = bytearray()
        for character in value:
            codepoint = ord(character)
            if codepoint <= 255:
                encoded.append(codepoint)
            else:
                encoded.extend(character.encode("cp1252"))
        candidate = bytes(encoded).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError):
        return value
    after = _mojibake_score(candidate)
    return candidate if after < before else value


def _mojibake_score(value: str) -> int:
    """Count common marker fragments and all Latin-1 C1 control bytes."""
    marker_count = sum(value.count(marker) for marker in _MOJIBAKE_MARKERS)
    control_count = sum(0x80 <= ord(character) <= 0x9F for character in value)
    return marker_count + control_count
