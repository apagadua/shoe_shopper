from pathlib import Path
from backend.services.supabase_client import supabase
from datetime import datetime, timezone

def load_tolerances():
    # Fetch all active tolerances, should only be one
    result = (
        supabase.table("tolerances")
        .select("*")
        .eq("active", True)
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data

    # if no active tolerances, return none
    if not rows:
        return None
    
    # if one active tolerance, return it
    if len(rows) == 1:
        return rows[0]
    
    # if multiple active tolerances, return the most recent one and deactivate the rest
    most_recent = rows[0]
    old_ids = [row["id"] for row in rows[1:]]
    
    supabase.table("tolerances").update({"active": False}).in_("id", old_ids).execute()
    return most_recent

def save_tolerances(tolerances, feedback_count, timestamp):
    # deactivate old tolerances
    supabase.table("tolerances").update({"active": False}).eq("active", True).execute()

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    # insert new tolerances
    supabase.table("tolerances").insert({
        "tolerances": tolerances,
        "total_feedback_count": feedback_count,
        "active": True,
        "created_at": timestamp,
        "last_feedback_timestamp": timestamp
    }).execute()