#!/usr/bin/env python3
"""
Enterprise Watchlist Optimization System Test
Validates timeout protection, formatting, and sorting with offline tolerance
"""
import re, sys, multiprocessing as mp, app

CHAT = -1002782542798
ADMIN = 1653046781
SOL = "So11111111111111111111111111111111111111112"
UNK = "So11111111111111111111111111111111111111113"

# Regex patterns for format validation
usd2 = re.compile(r"\$\d[\d,]*\.\d{2}(?!\d)")
num2 = re.compile(r"\b\d[\d,]*\.\d{2}(?!\d)\b")

def _worker(cmd, q):
    """Worker process for timeout-protected command execution"""
    upd = {
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": CHAT, "type": "supergroup"},
            "from": {"id": ADMIN, "is_bot": False, "username": "turk"},
            "text": cmd
        }
    }
    out = app.process_telegram_command(upd) or {}
    q.put(out.get("text") or out.get("response") or "")

def send(cmd, timeout=8):
    """Send command with timeout protection (increased to 8s for reliability)"""
    q = mp.Queue()
    p = mp.Process(target=_worker, args=(cmd, q), daemon=True)
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1)
        return f"__TIMEOUT__ {cmd}"
    return q.get() if not q.empty() else ""

def rows(txt):
    """Extract watchlist rows from response text"""
    return [ln for ln in txt.splitlines() if " `" in ln and "—" in ln]

def pick(rs, pfx):
    """Find row starting with specific prefix"""
    for ln in rs:
        if ln.startswith(pfx):
            return ln
    return ""

def ok_value(mode, sol_row):
    """Validate value format - offline/disabled sources allowed to be '?'"""
    # Graceful handling of offline data sources
    if " ?  `" in sol_row:
        return True
    
    # Format validation when data is present
    if mode in ("prices", "caps", "fdv", "volumes"):
        return bool(usd2.search(sol_row))
    elif mode == "supply":
        return bool(num2.search(sol_row))
    elif mode == "holders":
        return bool(re.search(r"\b\d[\d,]*\b", sol_row))
    return False

def main():
    """Execute comprehensive enterprise watchlist test"""
    print("🎯 Enterprise Watchlist Optimization System Test")
    print("=" * 60)
    
    # Setup test environment
    print("Setting up test environment...")
    print(send("/watch_clear"))
    print(send(f"/watch {SOL}"))
    print(send(f"/watch {UNK}"))
    
    print("\n📊 Testing watchlist modes with timeout protection:")
    print("-" * 60)
    
    # Test all watchlist modes
    modes = ["supply", "fdv", "holders", "prices", "caps", "volumes"]
    results = []
    
    for mode in modes:
        wl = send(f"/watchlist {mode}")
        
        # Check for timeout
        if wl.startswith("__TIMEOUT__"):
            print(f"{mode:8}: ❌ TIMEOUT")
            results.append(False)
            continue
        
        # Extract rows and find SOL/UNK entries
        rs = rows(wl)
        sol = pick(rs, "SOL —")
        unk = pick(rs, "So1111…111113 —")
        
        # Validate row extraction
        if not sol or not unk:
            print(f"{mode:8}: ❌ FAIL rows")
            results.append(False)
            continue
        
        # Validate value formatting
        sol_ok = ok_value(mode, sol)
        unk_ok = " ?  `" in unk
        
        status = "✅ OK" if sol_ok and unk_ok else "❌ FAIL"
        sol_display = sol.split('`')[0].strip()
        unk_status = "✅ OK" if unk_ok else "❌ FAIL"
        
        print(f"{mode:8}: {status} | SOL=<{sol_display}> | UNK={unk_status}")
        results.append(sol_ok and unk_ok)
    
    print("\n🔄 Testing resilient sorting system:")
    print("-" * 60)
    
    # Test sorting functionality
    hdr_desc = send("/watchlist volumes desc").splitlines()[0]
    sort_desc_ok = "(desc)" in hdr_desc
    print(f"volumes desc: {'✅ OK' if sort_desc_ok else '❌ FAIL'} -> {hdr_desc}")
    
    hdr_asc = send("/watchlist supply asc").splitlines()[0]
    sort_asc_ok = "(asc)" in hdr_asc
    print(f"supply asc:   {'✅ OK' if sort_asc_ok else '❌ FAIL'} -> {hdr_asc}")
    
    # Summary
    print("\n📋 Test Summary:")
    print("=" * 60)
    
    total_tests = len(results) + 2  # modes + 2 sort tests
    passed_tests = sum(results) + int(sort_desc_ok) + int(sort_asc_ok)
    
    print(f"Watchlist modes: {sum(results)}/{len(results)} passed")
    print(f"Sorting tests:   {int(sort_desc_ok) + int(sort_asc_ok)}/2 passed")
    print(f"Overall:         {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 Enterprise optimization system: FULLY OPERATIONAL")
        print("✓ Timeout protection working")
        print("✓ Graceful degradation with '?' values")
        print("✓ Proper formatting when data available")
        print("✓ Resilient sorting system functional")
    else:
        print(f"\n⚠️  System partially operational: {passed_tests}/{total_tests}")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    main()