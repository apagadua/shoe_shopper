from backend.services.supabase_client import supabase

def get_feedback_rows(last_feedback_timestamp=None):
    # Only fetch feedback rows that are newer than the last feedback timestamp in the tolerances
    if last_feedback_timestamp:
        return supabase.table("user_feedback").select("*").gt("created_at", last_feedback_timestamp).execute().data
    else:
        return supabase.table("user_feedback").select("*").execute().data