from typing import List

__all__ = ["format_build_failures"]


def format_build_failures(phase: str, failures: List[tuple[str, Exception]]) -> str:
    lines = [f"{name}: {error}" for name, error in failures]
    return f"{phase} failed for {len(failures)} creator(s):\n" + "\n".join(lines)
