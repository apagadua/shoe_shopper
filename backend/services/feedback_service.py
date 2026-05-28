from backend.services.supabase_client import supabase

def get_feedback_rows(last_feedback_timestamp=None):
    # Only fetch feedback rows that are newer than the last feedback timestamp in the tolerances
    rows = (
        supabase.table("user_feedback")
        .select("*")
        .order("created_at", desc=False)
        .execute()
        .data
    )
    if rows:
        new_feedback_timestamp = rows[-1]["created_at"]
    else:
        new_feedback_timestamp = last_feedback_timestamp
    return rows, new_feedback_timestamp