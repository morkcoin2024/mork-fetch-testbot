#!/usr/bin/env python3
"""
Verify CLIPPY transaction to confirm tokens were actually received
Transaction: 2HzjGQbYE3uPtFMXwkbjrcUvhzkGibptqRMfRcD6oMnyFA2qaahMXfXrvDk66m9VMdf1shVm1mTbUxbBfrAswTNg
"""
from solana.rpc.api import Client
from solders.pubkey import Pubkey as PublicKey


def verify_clippy_transaction():
    """Verify the CLIPPY transaction actually delivered tokens"""
    print("🔍 VERIFYING CLIPPY TRANSACTION")
    print("=" * 60)

    tx_hash = (
        "2HzjGQbYE3uPtFMXwkbjrcUvhzkGibptqRMfRcD6oMnyFA2qaahMXfXrvDk66m9VMdf1shVm1mTbUxbBfrAswTNg"
    )
    clippy_mint = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"

    try:
        # Load test wallet
        with open("test_wallet_info.txt") as f:
            lines = f.read().strip().split("\n")
            public_key = lines[0].split(": ")[1].strip()

        print(f"Transaction: {tx_hash}")
        print(f"Wallet: {public_key}")
        print(f"Target token: {clippy_mint}")
        print()

        # Step 1: Check transaction details
        print("Step 1: Transaction Status")
        print("-" * 30)

        client = Client("https://api.mainnet-beta.solana.com")
        pubkey = PublicKey.from_string(public_key)

        # Get transaction details
        from solders.signature import Signature

        signature = Signature.from_string(tx_hash)
        tx_response = client.get_transaction(
            signature, encoding="json", max_supported_transaction_version=0
        )

        if tx_response.value:
            print("✅ Transaction found on blockchain")
            tx_data = tx_response.value

            # Check transaction success
            if tx_data.meta and tx_data.meta.err is None:
                print("✅ Transaction succeeded (no errors)")
            else:
                print(
                    f"❌ Transaction failed: {tx_data.meta.err if tx_data.meta else 'Unknown error'}"
                )
                return False

            # Check SOL balance changes
            if tx_data.meta and tx_data.meta.pre_balances and tx_data.meta.post_balances:
                pre_balance = tx_data.meta.pre_balances[0] / 1_000_000_000
                post_balance = tx_data.meta.post_balances[0] / 1_000_000_000
                sol_spent = pre_balance - post_balance
                print(f"💰 SOL spent: {sol_spent:.6f}")

        else:
            print("❌ Transaction not found")
            return False

        # Step 2: Check for CLIPPY tokens in wallet
        print("\nStep 2: Token Balance Verification")
        print("-" * 30)

        # Get all token accounts for the wallet
        token_accounts = client.get_token_accounts_by_owner(
            pubkey,
            {"programId": PublicKey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")},
            encoding="jsonParsed",
        )

        clippy_found = False
        clippy_balance = 0

        if token_accounts.value:
            print(f"Found {len(token_accounts.value)} token accounts")

            for account in token_accounts.value:
                account_data = account.account.data.parsed
                if account_data and "info" in account_data:
                    token_info = account_data["info"]
                    mint = token_info.get("mint", "")
                    balance = float(token_info.get("tokenAmount", {}).get("uiAmount", 0))

                    if mint == clippy_mint:
                        clippy_found = True
                        clippy_balance = balance
                        print(f"🎯 CLIPPY tokens found: {balance:,.0f}")
                        break

            if not clippy_found:
                print("❌ NO CLIPPY TOKENS FOUND IN WALLET")
                return False
        else:
            print("❌ No token accounts found")
            return False

        # Step 3: Verify transaction logs for token transfer
        print("\nStep 3: Transaction Log Analysis")
        print("-" * 30)

        if tx_data.meta and tx_data.meta.log_messages:
            transfer_found = False
            for log in tx_data.meta.log_messages:
                if "Transfer" in log and clippy_mint[:8] in log:
                    transfer_found = True
                    print(f"✅ Token transfer log found: {log}")

            if not transfer_found:
                print("⚠️ No explicit token transfer logs found")

        # Final verification
        print("\n" + "=" * 60)
        print("FINAL VERIFICATION RESULT")
        print("=" * 60)

        if clippy_found and clippy_balance > 0:
            print("🎉 SUCCESS! TOKENS VERIFIED IN WALLET")
            print(f"✅ Transaction hash: {tx_hash}")
            print(f"✅ CLIPPY balance: {clippy_balance:,.0f} tokens")
            print(f"✅ Wallet: {public_key}")
            print()
            print("🟢 CONCLUSION: PumpPortal documentation method WORKS!")
            print("🟢 Real tokens were successfully acquired")
            print("🟢 Emergency stop can be safely lifted")
            return True
        else:
            print("❌ FAILURE: No tokens in wallet")
            print("❌ Transaction succeeded but delivered 0 tokens")
            print("❌ Same issue as before - wallet drain without tokens")
            return False

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


if __name__ == "__main__":
    success = verify_clippy_transaction()
    if success:
        print("\n✅ VERIFICATION PASSED - System ready for live trading")
    else:
        print("\n❌ VERIFICATION FAILED - Keep emergency stop active")
