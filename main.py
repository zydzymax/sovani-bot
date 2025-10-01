#!/usr/bin/env python3
"""Main entrypoint for SoVAni Bot.

This is the new entrypoint as of Stage 6 (project restructuring).
The actual bot logic is in app/bot/entry.py.
"""

if __name__ == "__main__":
    from app.bot.entry import main

    main()
