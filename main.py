"""
Mork F.E.T.C.H Bot - Main Entry Point
Production-ready Solana trading bot with safety systems
"""

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)