from backend.services.supabase_client import supabase

def get_feedback_rows():
    return supabase.table("feedback").select("*").execute().data