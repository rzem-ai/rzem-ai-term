#!/usr/bin/env bash
#
# rzem-ai-term installer
#
# Installs the tabbed TUI terminal and optionally configures it
# as the login shell for SSH sessions.
#
# Usage:
#   sudo ./install.sh                    # Install only
#   sudo ./install.sh --setup <user>     # Install + configure for a user
#   sudo ./install.sh --uninstall <user> # Remove configuration for a user

set -euo pipefail

INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"
VENV_DIR="/opt/rzem-ai-term"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

install_package() {
    info "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip

    info "Installing rzem-ai-term..."
    "${VENV_DIR}/bin/pip" install "${SCRIPT_DIR}"

    # Create symlinks in /usr/local/bin
    info "Creating symlinks..."
    ln -sf "${VENV_DIR}/bin/rzem-ai-term" "${INSTALL_PREFIX}/bin/rzem-ai-term"
    ln -sf "${VENV_DIR}/bin/rzem-ai-term-shell" "${INSTALL_PREFIX}/bin/rzem-ai-term-shell"
    ln -sf "${VENV_DIR}/bin/rzem-ai-term-daemon" "${INSTALL_PREFIX}/bin/rzem-ai-term-daemon"

    # Register as a valid login shell
    if ! grep -q "rzem-ai-term-shell" /etc/shells 2>/dev/null; then
        info "Adding to /etc/shells..."
        echo "${INSTALL_PREFIX}/bin/rzem-ai-term-shell" >> /etc/shells
    fi

    # Install systemd service
    info "Installing systemd service..."
    cp "${SCRIPT_DIR}/systemd/rzem-ai-term@.service" /etc/systemd/system/
    systemctl daemon-reload

    # Create log directory
    mkdir -p /var/log/rzem-ai-term
    chmod 755 /var/log/rzem-ai-term

    # Create run directory
    mkdir -p /run/rzem-ai-term
    chmod 755 /run/rzem-ai-term

    info "Installation complete!"
}

setup_user() {
    local target_user="$1"

    # Verify user exists
    if ! id "${target_user}" &>/dev/null; then
        error "User '${target_user}' does not exist"
        exit 1
    fi

    # Save the user's current shell
    local current_shell
    current_shell="$(getent passwd "${target_user}" | cut -d: -f7)"
    info "User's current shell: ${current_shell}"

    # Save it for the TUI to use
    local config_dir
    config_dir="$(eval echo "~${target_user}")/.config/rzem-ai-term"
    mkdir -p "${config_dir}"
    echo "${current_shell}" > "${config_dir}/shell"
    chown -R "${target_user}:" "${config_dir}"

    info "Saved original shell to ${config_dir}/shell"

    # Change the user's shell
    chsh -s "${INSTALL_PREFIX}/bin/rzem-ai-term-shell" "${target_user}"
    info "Changed login shell for '${target_user}' to rzem-ai-term-shell"

    # Enable the daemon for this user
    systemctl enable "rzem-ai-term@${target_user}"
    systemctl start "rzem-ai-term@${target_user}" || true
    info "Enabled session daemon for '${target_user}'"

    echo ""
    info "Setup complete! When '${target_user}' logs in via SSH, they will"
    info "see the rzem-ai-term tabbed TUI interface."
    info ""
    info "To undo:  sudo $0 --uninstall ${target_user}"
}

uninstall_user() {
    local target_user="$1"

    if ! id "${target_user}" &>/dev/null; then
        error "User '${target_user}' does not exist"
        exit 1
    fi

    # Restore original shell
    local config_dir
    config_dir="$(eval echo "~${target_user}")/.config/rzem-ai-term"
    if [[ -f "${config_dir}/shell" ]]; then
        local original_shell
        original_shell="$(cat "${config_dir}/shell")"
        chsh -s "${original_shell}" "${target_user}"
        info "Restored shell to ${original_shell} for '${target_user}'"
    else
        chsh -s /bin/bash "${target_user}"
        warn "No saved shell found, defaulted to /bin/bash"
    fi

    # Stop and disable daemon
    systemctl stop "rzem-ai-term@${target_user}" 2>/dev/null || true
    systemctl disable "rzem-ai-term@${target_user}" 2>/dev/null || true
    info "Disabled session daemon for '${target_user}'"

    info "Uninstall complete for '${target_user}'"
}

usage() {
    cat <<'USAGE'
Usage:
  sudo ./install.sh                      Install rzem-ai-term system-wide
  sudo ./install.sh --setup <username>   Install and configure for a user
  sudo ./install.sh --uninstall <user>   Remove configuration for a user

Options:
  --help    Show this help message

Environment:
  INSTALL_PREFIX   Installation prefix (default: /usr/local)
USAGE
}

main() {
    case "${1:-}" in
        --help|-h)
            usage
            ;;
        --setup)
            check_root
            if [[ -z "${2:-}" ]]; then
                error "Usage: $0 --setup <username>"
                exit 1
            fi
            install_package
            setup_user "$2"
            ;;
        --uninstall)
            check_root
            if [[ -z "${2:-}" ]]; then
                error "Usage: $0 --uninstall <username>"
                exit 1
            fi
            uninstall_user "$2"
            ;;
        "")
            check_root
            install_package
            echo ""
            info "To configure for a user:  sudo $0 --setup <username>"
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"
