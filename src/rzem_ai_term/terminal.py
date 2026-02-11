"""Terminal emulator widget using pyte for VT100 emulation and pty for shell subprocess."""

from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import signal
import struct
import termios
from typing import TYPE_CHECKING

import pyte
from textual.strip import Strip
from textual.widget import Widget
from textual.reactive import reactive
from rich.segment import Segment
from rich.style import Style

if TYPE_CHECKING:
    pass

# Map pyte bold/color attributes to Rich styles
_PYTE_COLORS = {
    "black": "black",
    "red": "red",
    "green": "green",
    "brown": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "white": "white",
    "default": None,
}


def _pyte_char_to_style(char: pyte.screens.Char) -> Style:
    """Convert a pyte character's attributes to a Rich Style."""
    fg = _PYTE_COLORS.get(char.fg, char.fg if char.fg != "default" else None)
    bg = _PYTE_COLORS.get(char.bg, char.bg if char.bg != "default" else None)
    return Style(
        color=fg,
        bgcolor=bg,
        bold=char.bold,
        italic=char.italics,
        underline=char.underscore,
        reverse=char.reverse,
        strike=char.strikethrough,
    )


class TerminalWidget(Widget):
    """A terminal emulator widget that runs a shell subprocess."""

    can_focus = True

    title: reactive[str] = reactive("shell")
    is_alive: reactive[bool] = reactive(True)

    DEFAULT_CSS = """
    TerminalWidget {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }
    TerminalWidget:focus {
        border: none;
    }
    """

    def __init__(
        self,
        shell: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._shell = shell or os.environ.get("RZEM_USER_SHELL", "/bin/bash")
        self._screen = pyte.Screen(80, 24)
        self._stream = pyte.Stream(self._screen)
        self._fd: int | None = None
        self._pid: int | None = None
        self._reader_task: asyncio.Task | None = None

    def on_mount(self) -> None:
        self._spawn_shell()
        self._resize_pty()

    def on_resize(self) -> None:
        self._resize_pty()

    def _spawn_shell(self) -> None:
        """Fork a PTY and exec the shell."""
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        # Don't let the child inherit our special shell setting
        env.pop("RZEM_USER_SHELL", None)

        pid, fd = pty.openpty()
        child_pid = os.fork()
        if child_pid == 0:
            # Child process
            os.close(pid)
            os.setsid()
            fcntl.ioctl(fd, termios.TIOCSCTTY, 0)
            os.dup2(fd, 0)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            if fd > 2:
                os.close(fd)
            os.execvpe(self._shell, [self._shell, "--login"], env)
        else:
            # Parent process
            os.close(fd)
            self._fd = pid
            self._pid = child_pid
            # Set non-blocking
            flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
            fcntl.fcntl(self._fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self._reader_task = asyncio.get_event_loop().create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Read output from the PTY and feed it to pyte."""
        loop = asyncio.get_event_loop()
        try:
            while self._fd is not None:
                try:
                    data = await loop.run_in_executor(None, self._blocking_read)
                    if not data:
                        break
                    self._stream.feed(data)
                    self.refresh()
                except OSError:
                    break
        finally:
            self.is_alive = False
            self.refresh()

    def _blocking_read(self) -> str:
        """Blocking read from the PTY fd, meant to run in an executor."""
        import select

        if self._fd is None:
            return ""
        try:
            r, _, _ = select.select([self._fd], [], [], 0.1)
            if r:
                data = os.read(self._fd, 65536)
                if not data:
                    return ""
                return data.decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return ""
        return ""

    def _resize_pty(self) -> None:
        """Resize the PTY and pyte screen to match the widget dimensions."""
        cols = self.size.width
        rows = self.size.height
        if cols < 1 or rows < 1:
            return
        self._screen.resize(rows, cols)
        if self._fd is not None:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)
                if self._pid is not None:
                    os.kill(self._pid, signal.SIGWINCH)
            except OSError:
                pass

    def render_line(self, y: int) -> Strip:
        """Render a single line from the pyte screen."""
        if y >= self._screen.lines:
            return Strip.blank(self.size.width)

        segments: list[Segment] = []
        buffer = self._screen.buffer
        line = buffer.get(y, {})

        for x in range(self._screen.columns):
            char = line.get(x, self._screen.default_char)
            style = _pyte_char_to_style(char)
            text = char.data if char.data else " "
            segments.append(Segment(text, style))

        return Strip(segments)

    def on_key(self, event) -> None:
        """Send keystrokes to the PTY."""
        event.stop()
        if self._fd is None or not self.is_alive:
            return

        key = event.key
        char = event.character

        # Map special keys to escape sequences
        key_map = {
            "escape": "\x1b",
            "enter": "\r",
            "tab": "\t",
            "backspace": "\x7f",
            "delete": "\x1b[3~",
            "up": "\x1b[A",
            "down": "\x1b[B",
            "right": "\x1b[C",
            "left": "\x1b[D",
            "home": "\x1b[H",
            "end": "\x1b[F",
            "pageup": "\x1b[5~",
            "pagedown": "\x1b[6~",
            "insert": "\x1b[2~",
            "f1": "\x1bOP",
            "f2": "\x1bOQ",
            "f3": "\x1bOR",
            "f4": "\x1bOS",
            "f5": "\x1b[15~",
            "f6": "\x1b[17~",
            "f7": "\x1b[18~",
            "f8": "\x1b[19~",
            "f9": "\x1b[20~",
            "f10": "\x1b[21~",
            "f11": "\x1b[23~",
            "f12": "\x1b[24~",
        }

        data = None

        # Handle ctrl+key combinations
        if key.startswith("ctrl+"):
            ctrl_char = key[5:]
            if ctrl_char == "c":
                data = "\x03"
            elif ctrl_char == "d":
                data = "\x04"
            elif ctrl_char == "z":
                data = "\x1a"
            elif ctrl_char == "l":
                data = "\x0c"
            elif ctrl_char == "a":
                data = "\x01"
            elif ctrl_char == "e":
                data = "\x05"
            elif ctrl_char == "k":
                data = "\x0b"
            elif ctrl_char == "u":
                data = "\x15"
            elif ctrl_char == "w":
                data = "\x17"
            elif ctrl_char == "r":
                data = "\x12"
            elif len(ctrl_char) == 1:
                data = chr(ord(ctrl_char.lower()) - ord("a") + 1)
        elif key in key_map:
            data = key_map[key]
        elif char:
            data = char

        if data is not None:
            try:
                os.write(self._fd, data.encode("utf-8"))
            except OSError:
                pass

    def kill(self) -> None:
        """Terminate the shell subprocess."""
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGTERM)
            except OSError:
                pass
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        if self._reader_task is not None:
            self._reader_task.cancel()

    def on_unmount(self) -> None:
        self.kill()
