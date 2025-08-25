"""
Admin notification system for Mork F.E.T.C.H Bot
Provides real-time DM summaries and fetch statistics to admin users.
"""

import logging
import os

from telegram.constants import ParseMode

from eventbus import publish

ADMIN_ID = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID", "0") or "0")


async def _dm_admin_summary(context, stats: dict):
    """Send fetch summary DM to admin with comprehensive statistics."""
    if not ADMIN_ID:
        logging.debug("No admin ID configured for DM notifications")
        return

    # Format comprehensive fetch summary
    txt = (
        "📊 *FETCH SUMMARY*\n"
        f"- Pump.fun: *{stats.get('pumpfun', '-')}*\n"
        f"- Dex search: *{stats.get('dex_search', '-')}*\n"
        f"- Dex early: *{stats.get('dex_early', '-')}*\n"
        f"- On-chain: *{stats.get('onchain', '-')}*\n"
        f"- Ranked: *{stats.get('ranked', '-')}*\n"
        f"- Filter eff: *{stats.get('filter_efficiency', '-')}%*\n"
        f"- Notes: {stats.get('note', '-')}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=txt, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
        )
        publish("dm.summary.sent", {"ok": True, "admin_id": ADMIN_ID})
        logging.info("Admin fetch summary sent successfully")
    except Exception as e:
        publish("dm.summary.sent", {"ok": False, "err": str(e), "admin_id": ADMIN_ID})
        logging.error(f"Failed to send admin summary: {e}")


async def _dm_admin_alert(context, alert_type: str, message: str):
    """Send critical alert DM to admin."""
    if not ADMIN_ID:
        return

    alert_txt = f"🚨 *{alert_type.upper()}*\n{message}"

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=alert_txt,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        publish("dm.alert.sent", {"ok": True, "type": alert_type})
    except Exception as e:
        publish("dm.alert.sent", {"ok": False, "type": alert_type, "err": str(e)})


def calculate_fetch_stats(
    all_items, filtered_items, pumpfun_failed=False, dex_failed=False, onchain_failed=False
):
    """Calculate comprehensive fetch statistics for admin reporting."""

    # Count by source
    pumpfun_count = len([x for x in all_items if (x.get("source") or "").startswith("pumpfun")])
    dex_count = len([x for x in all_items if (x.get("source") or "") == "dexscreener"])
    onchain_count = len([x for x in all_items if (x.get("source") or "") == "pumpfun-chain"])
    dex_early_count = len(
        [x for x in all_items if (x.get("source") or "") in ("dexscreener-new", "dxs-new")]
    )

    # Calculate filter efficiency
    filter_efficiency = round((len(filtered_items) / len(all_items)) * 100, 1) if all_items else 0

    # Generate status notes
    notes = []
    if pumpfun_failed:
        notes.append("pumpfun REST 530 → chain/early fallback")
    if dex_failed:
        notes.append("dex API timeout")
    if onchain_failed:
        notes.append("RPC unavailable")
    if not notes:
        notes.append("all sources ok")

    return {
        "pumpfun": pumpfun_count,
        "dex_search": dex_count,
        "dex_early": dex_early_count,
        "onchain": onchain_count,
        "ranked": len(filtered_items),
        "filter_efficiency": filter_efficiency,
        "total_raw": len(all_items),
        "note": " | ".join(notes),
    }


async def send_fetch_summary(context, all_items, filtered_items, **failure_flags):
    """Send comprehensive fetch summary to admin with source breakdown."""
    stats = calculate_fetch_stats(all_items, filtered_items, **failure_flags)
    await _dm_admin_summary(context, stats)

    # Publish detailed fetch analytics
    publish(
        "fetch.summary.generated",
        {
            "stats": stats,
            "sources_active": len(
                [s for s in ["pumpfun", "dex", "onchain"] if stats.get(s, 0) > 0]
            ),
            "efficiency_grade": (
                "A"
                if stats["filter_efficiency"] > 25
                else "B" if stats["filter_efficiency"] > 15 else "C"
            ),
        },
    )
