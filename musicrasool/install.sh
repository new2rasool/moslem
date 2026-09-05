#!/usr/bin/env bash
# ============================================================
#  MusicRasool - One-command automatic installer  (v2.0)
#  Linux / macOS
# ------------------------------------------------------------
#  Tested on:
#    Ubuntu 20.04 / 22.04 / 24.04, Debian 11 / 12,
#    CentOS 7+, Rocky / Alma 8+, Fedora, macOS (Homebrew)
# ============================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   MusicRasool Auto Installer  v2.0        ${NC}"
echo -e "${CYAN}============================================${NC}"

# ------------------------------------------------------------
# 1) Find a suitable Python (3.9 - 3.12 recommended)
# ------------------------------------------------------------
echo -e "${GREEN}[1/6] Looking for a suitable Python ...${NC}"
pick_python() {
    # preferred order: 3.10, 3.11, 3.9, 3.12, then plain python3
    for cand in python3.10 python3.11 python3.9 python3.12 python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            PYTHON_BIN="$cand"
            return 0
        fi
    done
    return 1
}
if ! pick_python; then
    echo -e "${RED}Python 3 is not installed.${NC}"
    echo -e "  Ubuntu/Debian : ${YELLOW}sudo apt install -y python3.10 python3.10-venv python3-pip${NC}"
    echo -e "  CentOS/Rocky  : ${YELLOW}sudo dnf install -y python3.10 python3-pip${NC}"
    echo -e "  macOS         : ${YELLOW}brew install python@3.10${NC}"
    exit 1
fi

PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER#*.}"; PY_MINOR="${PY_MINOR%%.*}"
echo -e "  Using ${GREEN}${PYTHON_BIN} (${PY_VER})${NC}"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo -e "${RED}Python 3.9+ is required (found ${PY_VER}).${NC}"
    exit 1
fi
if [ "$PY_MINOR" -ge 13 ]; then
    echo -e "${YELLOW}  Note: Python ${PY_VER} has no prebuilt ntgcalls wheels.${NC}"
    echo -e "${YELLOW}  The installer will try anyway (the bot includes a compat shim),${NC}"
    echo -e "${YELLOW}  but Python 3.10 - 3.12 is strongly recommended.${NC}"
fi

# ------------------------------------------------------------
# 2) System dependencies (FFmpeg + tools)
# ------------------------------------------------------------
echo -e "${GREEN}[2/6] Installing system dependencies ...${NC}"
install_system_deps() {
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -y
        sudo apt-get install -y ffmpeg python3-venv python3-pip git build-essential || true
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y epel-release || true
        sudo dnf install -y ffmpeg python3-pip git gcc-c++ || true
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y epel-release || true
        sudo yum install -y ffmpeg python3-pip git gcc-c++ || true
    elif command -v brew >/dev/null 2>&1; then
        brew install ffmpeg python@3.10 git || true
    else
        echo -e "${YELLOW}  No known package manager found - FFmpeg must be installed manually.${NC}"
    fi
}
install_system_deps || true

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${YELLOW}  ffmpeg not found. We will install the static ffmpeg via pip (imageio-ffmpeg) as a fallback.${NC}"
    FFMPEG_FALLBACK=1
else
    echo -e "  ffmpeg: $(ffmpeg -version 2>/dev/null | head -1)"
    FFMPEG_FALLBACK=0
fi

# ------------------------------------------------------------
# 3) Virtual environment
# ------------------------------------------------------------
echo -e "${GREEN}[3/6] Creating virtual environment ...${NC}"
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
    "$PYTHON_BIN" -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
python -m pip install --upgrade pip wheel setuptools

# ------------------------------------------------------------
# 4) Python requirements (STRICT pins + ntgcalls wheel fallback)
# ------------------------------------------------------------
echo -e "${GREEN}[4/6] Installing Python requirements ...${NC}"

# Install everything first. ntgcalls is handled separately because it
# is a native binding: we only accept prebuilt wheels (no source builds).
pip install -r <(grep -v '^ntgcalls' requirements.txt)

echo -e "  Installing ntgcalls (prebuilt wheel only) ..."
if pip install --only-binary=:all: "ntgcalls==1.1.3"; then
    echo -e "${GREEN}  ntgcalls 1.1.3 (classic enum names) installed.${NC}"
else
    echo -e "${YELLOW}  ntgcalls 1.1.3 has no wheel for this Python - trying 1.2.3 ...${NC}"
    if pip install --only-binary=:all: "ntgcalls==1.2.3"; then
        echo -e "${GREEN}  ntgcalls 1.2.3 installed (compat shim in clients.py handles it).${NC}"
    else
        echo -e "${RED}  Could not install ntgcalls from prebuilt wheels.${NC}"
        echo -e "${RED}  Please use Python 3.10 - 3.12 (64-bit) and retry.${NC}"
        exit 1
    fi
fi

# ffmpeg fallback via imageio-ffmpeg (static binary bundled)
if [ "$FFMPEG_FALLBACK" = "1" ]; then
    echo -e "${GREEN}  Installing static ffmpeg fallback ...${NC}"
    pip install -q imageio-ffmpeg==0.4.9
    # Ask the package where its binary actually is - the file name changes
    # between imageio-ffmpeg releases (e.g. ffmpeg-linux64-v4.2.2), so it
    # must not be hard-coded.
    FFMPEG_BIN="$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null)"
    if [ -n "$FFMPEG_BIN" ] && [ -f "$FFMPEG_BIN" ]; then
        chmod +x "$FFMPEG_BIN" 2>/dev/null || true
        ln -sf "$FFMPEG_BIN" venv/bin/ffmpeg 2>/dev/null || true
    fi
    if command -v ffmpeg >/dev/null 2>&1 || [ -x "venv/bin/ffmpeg" ]; then
        echo -e "${GREEN}  ffmpeg is now available.${NC}"
    else
        echo -e "${YELLOW}  Could not wire ffmpeg - please install it manually.${NC}"
        echo -e "${YELLOW}  (imageio_ffmpeg.get_ffmpeg_exe() is also used at runtime as a fallback)${NC}"
    fi
fi

# ------------------------------------------------------------
# 5) Configuration (.env) - interactive wizard
# ------------------------------------------------------------
echo -e "${GREEN}[5/6] Configuration ...${NC}"
if [ -f ".env" ]; then
    echo -e "  .env already exists - keeping it."
else
    echo -e "  No .env found - let's create it now."
    echo -e "  (You need: API_ID / API_HASH from ${CYAN}https://my.telegram.org${NC},"
    echo -e "   BOT_TOKEN from ${CYAN}https://t.me/BotFather${NC},"
    echo -e "   and your numeric ID from ${CYAN}https://t.me/userinfobot${NC})\n"

    read -rp "  API_ID     : " API_ID_IN
    read -rp "  API_HASH   : " API_HASH_IN
    read -rp "  BOT_TOKEN  : " BOT_TOKEN_IN
    read -rp "  OWNER_ID   : " OWNER_ID_IN
    read -rp "  SUDO_ID (Enter = same as OWNER_ID): " SUDO_ID_IN
    [ -z "$SUDO_ID_IN" ] && SUDO_ID_IN="$OWNER_ID_IN"

    if [ -z "$API_ID_IN" ] || [ -z "$API_HASH_IN" ] || [ -z "$BOT_TOKEN_IN" ] || [ -z "$OWNER_ID_IN" ]; then
        # Never copy .env.example: an unedited copy would start the bot with
        # placeholder credentials. Write a clearly-marked .env instead and
        # stop, so the operator must fill it in.
        echo -e "${RED}  Incomplete input - .env written with PLACEHOLDER values.${NC}"
        echo -e "${YELLOW}  The bot will refuse to start until you fill them in.${NC}"
        cat > .env <<EOF
# MusicRasool configuration - INCOMPLETE, fill in the values marked below
API_ID=${API_ID_IN:-PUT_YOUR_API_ID_HERE}
API_HASH=${API_HASH_IN:-PUT_YOUR_API_HASH_HERE}
BOT_TOKEN=${BOT_TOKEN_IN:-PUT_YOUR_BOT_TOKEN_HERE}
OWNER_ID=${OWNER_ID_IN:-PUT_YOUR_NUMERIC_USER_ID_HERE}
SUDO_ID=${SUDO_ID_IN}
DEFAULT_LANG=fa
DOWNLOAD_DIR=downloads
MELOBIT_API=https://api.melobit.com/v1
EOF
        :  # placeholders written - detected again in step 6
    else
        cat > .env <<EOF
# MusicRasool configuration
API_ID=$API_ID_IN
API_HASH=$API_HASH_IN
BOT_TOKEN=$BOT_TOKEN_IN
OWNER_ID=$OWNER_ID_IN
SUDO_ID=$SUDO_ID_IN
DEFAULT_LANG=fa
DOWNLOAD_DIR=downloads
MELOBIT_API=https://api.melobit.com/v1
EOF
        echo -e "${GREEN}  .env written.${NC}"

    fi
fi

# ------------------------------------------------------------
# 6) Done
# ------------------------------------------------------------
echo -e "${GREEN}[6/6] Setup complete.${NC}"
echo -e "${CYAN}============================================${NC}"

# Refuse to advertise "just run it" if the credentials are still placeholders.
if grep -q "PUT_YOUR_.*_HERE" .env 2>/dev/null; then
    echo -e "${RED}.env still contains PLACEHOLDER values - the bot will not start.${NC}"
    echo -e "${YELLOW}Edit .env and set API_ID, API_HASH, BOT_TOKEN and OWNER_ID.${NC}"
    echo -e "${CYAN}============================================${NC}"
    exit 1
fi

echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Run the bot:"
echo -e "     ${CYAN}./run.sh${NC}     (or: ${CYAN}source venv/bin/activate && python run.py${NC})"
echo -e "  2. In your private chat with the bot send ${CYAN}/login${NC} and follow the"
echo -e "     steps to log in the HELPER account:"
echo -e "       1) phone number   (e.g. +989123456789)"
echo -e "       2) login code     (sent to that phone/Telegram)"
echo -e "       3) 2FA password   (only if enabled)"
echo -e "  3. Send ${CYAN}/restart${NC} to activate the helper session, then add the"
echo -e "     helper account to your group(s) and enjoy streaming!"
echo -e "${CYAN}============================================${NC}"
