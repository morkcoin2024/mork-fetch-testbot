#!/usr/bin/env python3
"""
Create controlled test wallet for funding
"""
import base58
from solders.keypair import Keypair

# Create new test wallet
keypair = Keypair()
public_key = str(keypair.pubkey())
private_key = base58.b58encode(keypair.secret()).decode('ascii')

print("🔑 NEW TEST WALLET CREATED:")
print(f"Public Key: {public_key}")
print(f"Private Key: {private_key}")
print("")
print("📝 ACTION REQUIRED:")
print(f"Send 0.1 SOL to: {public_key}")
print("Then we can run the real controlled test")

# Save wallet info
with open('test_wallet_info.txt', 'w') as f:
    f.write(f"Public Key: {public_key}\n")
    f.write(f"Private Key: {private_key}\n")
    f.write(f"Created for: Controlled test with 0.1 SOL\n")

print("✅ Wallet info saved to test_wallet_info.txt")