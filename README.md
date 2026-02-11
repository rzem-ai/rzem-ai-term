# rzem-ai-term

A tabbed TUI terminal application that runs as an SSH login shell on Ubuntu. When users SSH into the server, they're greeted with a Textual-based interface providing multiple terminal tabs instead of a bare shell prompt.

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  macOS/Windows Terminal Emulator                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │  SSH connection ──► SSHD ──► rzem-ai-term-shell   │  │
│  │                                                   │  │
│  │  ┌─ rzem-ai-term TUI ──────────────────────────┐  │  │
│  │  │ [shell-1] [shell-2] [shell-3]        ctrl+t  │  │  │
│  │  │┌─────────────────────────────────────────────┐│  │  │
│  │  ││ user@server:~$ _                            ││  │  │
│  │  ││                                             ││  │  │
│  │  ││                                             ││  │  │
│  │  │└─────────────────────────────────────────────┘│  │  │
│  │  │ ctrl+t: new tab | ctrl+w: close | ctrl+q: quit│  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

1. **SSHD** handles authentication and the SSH connection (unchanged)
2. **rzem-ai-term-shell** is set as the user's login shell
3. The shell wrapper detects the user's original shell and launches the **Textual TUI**
4. The TUI provides a tabbed interface — each tab runs a full shell session
5. An optional **systemd daemon** provides session logging and health checks

## Requirements

- Ubuntu 20.04+ (or any systemd-based Linux)
- Python 3.10+
- OpenSSH server (sshd)

## Installation

```bash
# Clone the repository
git clone https://github.com/rzem-ai/rzem-ai-term.git
cd rzem-ai-term

# Install system-wide and configure for a user
sudo ./install.sh --setup <username>
```

This will:
- Create a Python venv at `/opt/rzem-ai-term`
- Install the package and dependencies (textual, pyte)
- Symlink executables to `/usr/local/bin/`
- Register `rzem-ai-term-shell` in `/etc/shells`
- Save the user's current shell for use inside tabs
- Change the user's login shell to `rzem-ai-term-shell`
- Enable the session tracking daemon

### Install Only (without configuring a user)

```bash
sudo ./install.sh
# Then later:
sudo ./install.sh --setup <username>
```

### Uninstall for a User

```bash
sudo ./install.sh --uninstall <username>
```

This restores the user's original shell and disables the daemon.

## Usage

### Connecting

From any terminal emulator on macOS or Windows:

```bash
ssh user@your-server
```

You'll see the tabbed TUI interface instead of a bare shell prompt.

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+T` | Open a new terminal tab |
| `Ctrl+W` | Close current tab (exits app if last tab) |
| `Ctrl+Shift+Right` | Switch to next tab |
| `Ctrl+Shift+Left` | Switch to previous tab |
| `Ctrl+Q` | Quit (closes all tabs) |

All standard shell keybindings (Ctrl+C, Ctrl+D, Ctrl+Z, etc.) work inside each tab.

### Running Commands via SSH

Non-interactive SSH commands bypass the TUI and run directly:

```bash
# This runs in the user's shell, not the TUI
ssh user@server 'ls -la /tmp'
```

### Running Without SSH (for testing)

```bash
# Run the TUI directly
rzem-ai-term

# Specify a shell
rzem-ai-term --shell /bin/zsh
```

## Alternative: ForceCommand (per-connection, no chsh)

Instead of changing the user's login shell, you can use `ForceCommand` in sshd_config:

```
# /etc/ssh/sshd_config
Match User myuser
    ForceCommand /usr/local/bin/rzem-ai-term-shell
```

Then reload sshd: `sudo systemctl reload sshd`

## Configuration

### User Shell Override

The TUI detects the user's original shell automatically. To override:

```bash
# Set via config file
mkdir -p ~/.config/rzem-ai-term
echo "/bin/zsh" > ~/.config/rzem-ai-term/shell

# Or via environment variable
export RZEM_USER_SHELL=/bin/zsh
```

### Session Daemon

The optional systemd daemon provides session tracking and logging:

```bash
# Check daemon status
systemctl status rzem-ai-term@username

# View session logs
journalctl -u rzem-ai-term@username

# Health check
echo "status" | socat - UNIX-CONNECT:/run/rzem-ai-term/username.sock
```

## Project Structure

```
rzem-ai-term/
├── pyproject.toml              # Package metadata and dependencies
├── install.sh                  # System-wide installer
├── systemd/
│   └── rzem-ai-term@.service   # Systemd template unit
└── src/rzem_ai_term/
    ├── __init__.py
    ├── app.py                  # Main Textual TUI application
    ├── terminal.py             # Terminal emulator widget (pyte + pty)
    ├── shell.py                # Login shell wrapper
    └── daemon.py               # Session tracking daemon
```

## Compatible Terminal Emulators

Tested with:
- **macOS**: Terminal.app, iTerm2, Alacritty, Kitty, WezTerm
- **Windows**: Windows Terminal, PuTTY, MobaXterm
- **Linux**: gnome-terminal, Konsole, Alacritty, Kitty

Any terminal emulator that supports xterm-256color should work.

## License

MIT
