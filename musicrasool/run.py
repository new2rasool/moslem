#!/usr/bin/env python3
"""
MusicRasool launcher.

Usage:
    python run.py
"""
import sys

import main

if __name__ == "__main__":
    try:
        main.run()
    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
        sys.exit(0)
