# Mork F.E.T.C.H Test Bot

Test environment for the Mork F.E.T.C.H Bot - "The Degens' Best Friend"

## Purpose

This is a complete test environment for developing and testing new features without affecting production users.

## Features

- Complete bot functionality in simulation mode
- Safe testing environment
- Isolated from production users
- Full database models and session management

## Setup

1. Clone this repository to Replit
2. Configure secrets:
   - `TELEGRAM_BOT_TOKEN` (new test bot token)
   - `DATABASE_URL` (shared with production)
   - `OPENAI_API_KEY` (shared with production)
3. Deploy and set webhook

## Test Bot Details

- **Telegram**: @MorkSniperTestBot
- **Environment**: TEST MODE
- **Trading**: Simulation only

## Architecture

Same as production bot but configured for safe testing.

## Commands

- `/start` - Welcome message
- `/help` - Show all commands
- `/simulate` - Practice trading
- `/status` - Check session status

## Development

This test environment allows safe development without affecting production users at @MorkSniperBot.
