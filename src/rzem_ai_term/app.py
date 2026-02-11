"""Main Textual application providing a tabbed terminal interface."""

from __future__ import annotations

import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from rzem_ai_term.terminal import TerminalWidget


class TerminalTabPane(TabPane):
    """A tab pane containing a terminal emulator."""

    def __init__(self, tab_title: str, tab_id: str, shell: str | None = None) -> None:
        super().__init__(tab_title, id=tab_id)
        self._shell = shell
        self._terminal: TerminalWidget | None = None

    def compose(self) -> ComposeResult:
        self._terminal = TerminalWidget(shell=self._shell)
        yield self._terminal

    @property
    def terminal(self) -> TerminalWidget | None:
        return self._terminal


class RzemTermApp(App):
    """A tabbed terminal emulator TUI designed for SSH login shell use."""

    TITLE = "rzem-ai-term"

    CSS = """
    Screen {
        background: $surface;
    }
    Header {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
    }
    Footer {
        dock: bottom;
        height: 1;
    }
    TabbedContent {
        height: 1fr;
    }
    TabbedContent ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        padding: 0;
        height: 1fr;
    }
    TerminalWidget {
        height: 1fr;
        width: 1fr;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-darken-2;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+t", "new_tab", "New Tab", show=True, priority=True),
        Binding("ctrl+w", "close_tab", "Close Tab", show=True, priority=True),
        Binding("ctrl+shift+right", "next_tab", "Next Tab", show=True, priority=True),
        Binding("ctrl+shift+left", "prev_tab", "Prev Tab", show=True, priority=True),
        Binding("ctrl+q", "quit_app", "Quit", show=True, priority=True),
    ]

    def __init__(self, shell: str | None = None) -> None:
        super().__init__()
        self._shell = shell
        self._tab_counter = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs"):
            tab_id = self._next_tab_id()
            with TabPane("shell-1", id=tab_id):
                yield TerminalWidget(shell=self._shell)
        yield Static("rzem-ai-term | ctrl+t: new tab | ctrl+w: close | ctrl+q: quit", id="status-bar")
        yield Footer()

    def _next_tab_id(self) -> str:
        self._tab_counter += 1
        return f"tab-{self._tab_counter}"

    def on_mount(self) -> None:
        # Focus the terminal in the first tab
        terminals = self.query(TerminalWidget)
        if terminals:
            terminals.first().focus()

    async def action_new_tab(self) -> None:
        """Create a new terminal tab."""
        tab_id = self._next_tab_id()
        tab_num = self._tab_counter
        pane = TerminalTabPane(f"shell-{tab_num}", tab_id, shell=self._shell)
        tabs = self.query_one("#tabs", TabbedContent)
        await tabs.add_pane(pane)
        tabs.active = tab_id
        # Focus the terminal in the new tab after a brief delay to let it mount
        self.set_timer(0.1, self._focus_active_terminal)

    def _focus_active_terminal(self) -> None:
        """Focus the terminal widget in the active tab."""
        tabs = self.query_one("#tabs", TabbedContent)
        active_pane = tabs.get_pane(tabs.active)
        if active_pane:
            terminals = active_pane.query(TerminalWidget)
            if terminals:
                terminals.first().focus()

    async def action_close_tab(self) -> None:
        """Close the current tab. If it's the last tab, exit the app."""
        tabs = self.query_one("#tabs", TabbedContent)
        if tabs.tab_count <= 1:
            self.exit()
            return
        active = tabs.active
        pane = tabs.get_pane(active)
        if pane:
            # Kill the terminal process
            terminals = pane.query(TerminalWidget)
            for term in terminals:
                term.kill()
            await tabs.remove_pane(active)
            self._focus_active_terminal()

    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        tabs = self.query_one("#tabs", TabbedContent)
        tab_list = list(tabs.query("Tab"))
        if not tab_list:
            return
        active_tab = tabs.active
        ids = [t.id for t in tab_list if t.id]
        if active_tab in ids:
            idx = ids.index(active_tab)
            next_idx = (idx + 1) % len(ids)
            tabs.active = ids[next_idx]
        self.set_timer(0.05, self._focus_active_terminal)

    def action_prev_tab(self) -> None:
        """Switch to the previous tab."""
        tabs = self.query_one("#tabs", TabbedContent)
        tab_list = list(tabs.query("Tab"))
        if not tab_list:
            return
        active_tab = tabs.active
        ids = [t.id for t in tab_list if t.id]
        if active_tab in ids:
            idx = ids.index(active_tab)
            prev_idx = (idx - 1) % len(ids)
            tabs.active = ids[prev_idx]
        self.set_timer(0.05, self._focus_active_terminal)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Focus the terminal when a tab is activated."""
        self.set_timer(0.05, self._focus_active_terminal)

    def action_quit_app(self) -> None:
        """Kill all terminals and exit."""
        for term in self.query(TerminalWidget):
            term.kill()
        self.exit()


def main() -> None:
    """Entry point for the TUI application."""
    import argparse

    parser = argparse.ArgumentParser(description="rzem-ai-term: tabbed terminal TUI")
    parser.add_argument(
        "--shell",
        default=None,
        help="Shell to use in terminal tabs (default: $RZEM_USER_SHELL or /bin/bash)",
    )
    args = parser.parse_args()

    app = RzemTermApp(shell=args.shell)
    app.run()


if __name__ == "__main__":
    main()
