from typing import Iterable, Optional
import subprocess


class CmdError(RuntimeError):
    def __init__(self, msg: str, cmd: Iterable[str], proc: Optional[subprocess.CompletedProcess[str]] = None):
        message = f"{msg}: {cmd!r}"

        if proc is not None:
            message += f"\ncode={proc.returncode}"
            message += f"\nstdout:\n{proc.stdout}"
            message += f"\nstderr:\n{proc.stderr}"

        super().__init__(message)
