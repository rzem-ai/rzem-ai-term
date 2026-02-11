"""Login shell wrapper that launches the rzem-ai-term TUI.

This script is designed to be set as a user's login shell. When invoked:
1. It detects the user's original shell (from /etc/passwd or $SHELL)
2. Sets RZEM_USER_SHELL so the TUI spawns the right shell in tabs
3. Launches the Textual TUI application

Usage:
    Set as login shell:  sudo chsh -s /usr/local/bin/rzem-ai-term-shell <username>
    Or via sshd_config:  ForceCommand /usr/local/bin/rzem-ai-term-shell
"""

from __future__ import annotations

import os
import pwd
import sys


def _detect_user_shell() -> str:
    """Detect the user's original shell before rzem-ai-term was set."""
    # 1. Check if explicitly configured
    configured = os.environ.get("RZEM_USER_SHELL")
    if configured and os.path.isfile(configured):
        return configured

    # 2. Check config file
    config_path = os.path.expanduser("~/.config/rzem-ai-term/shell")
    try:
        with open(config_path) as f:
            shell = f.read().strip()
            if shell and os.path.isfile(shell):
                return shell
    except FileNotFoundError:
        pass

    # 3. Check /etc/passwd for the user's shell -- but skip if it's us
    try:
        pw = pwd.getpwuid(os.getuid())
        passwd_shell = pw.pw_shell
        # If the passwd shell is this script, fall back
        this_script = os.path.abspath(sys.argv[0])
        if passwd_shell and passwd_shell != this_script and "rzem-ai-term" not in passwd_shell:
            return passwd_shell
    except KeyError:
        pass

    # 4. Fall back to /bin/bash
    return "/bin/bash"


def main() -> None:
    """Entry point for the login shell wrapper."""
    # If invoked with -c (e.g., ssh user@host 'command'), run the command
    # directly in the user's shell rather than launching the TUI
    if len(sys.argv) >= 3 and sys.argv[1] == "-c":
        shell = _detect_user_shell()
        os.execvp(shell, [shell, "-c", sys.argv[2]])
        return

    # Detect and export the user's real shell
    user_shell = _detect_user_shell()
    os.environ["RZEM_USER_SHELL"] = user_shell

    # Launch the TUI
    from rzem_ai_term.app import RzemTermApp

    app = RzemTermApp(shell=user_shell)
    app.run()


if __name__ == "__main__":
    main()
