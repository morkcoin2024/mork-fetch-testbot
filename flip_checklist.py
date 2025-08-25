# flip_checklist.py
def score(t: dict):
    """
    Returns (score:int 0-100, verdict:str, details:str)
    Example features: LP, age, holders, taxes, renounce/mint auth, liquidity lock
    """
    score = 0
    details = []

    # LP
    lp = float(t.get("lp", 0))
    if lp >= 20000:
        score += 25
        details.append("LP: ✅ 20k+")
    elif lp >= 5000:
        score += 15
        details.append("LP: ✅ 5k+")
    else:
        details.append("LP: ⚠️ low")

    # Age
    age = int(t.get("age", 0))
    if age >= 3600:
        score += 15
        details.append("Age: ✅ ≥1h")
    elif age >= 600:
        score += 10
        details.append("Age: ✅ ≥10m")
    else:
        details.append("Age: ⚠️ new")

    # Holders
    holders = int(t.get("holders", 0))
    if holders >= 300:
        score += 20
        details.append("Holders: ✅ 300+")
    elif holders >= 50:
        score += 10
        details.append("Holders: ✅ 50+")
    else:
        details.append("Holders: ⚠️ few")

    # Taxes
    if int(t.get("buy_tax", 0)) == 0 and int(t.get("sell_tax", 0)) == 0:
        score += 10
        details.append("Tax: ✅ 0/0")
    else:
        details.append("Tax: ⚠️")

    # Renounce & Mint revoke
    if bool(t.get("renounced", False)):
        score += 10
        details.append("Renounced: ✅")
    else:
        details.append("Renounced: ⚠️")
    if bool(t.get("mint_revoked", False)):
        score += 10
        details.append("Mint auth: ✅ revoked")
    else:
        details.append("Mint auth: ⚠️")

    # Liquidity lock
    if bool(t.get("liquidity_locked", False)):
        score += 10
        details.append("LP lock: ✅")
    else:
        details.append("LP lock: ⚠️")

    verdict = "BUY" if score >= 80 else ("WATCH" if score >= 60 else "PASS")
    return min(score, 100), verdict, " | ".join(details)
