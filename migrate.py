import json
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from the .env file
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def migrate_settings():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL or SUPABASE_KEY is missing from your environment or .env file.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Check if user_settings.json exists
    if not os.path.exists("user_settings.json"):
        print("❌ Error: user_settings.json not found in the current directory.")
        return

    # Load local JSON data
    with open("user_settings.json", "r") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"❌ Error parsing user_settings.json: {e}")
            return

    rows_to_insert = []
    for user_id, conf in data.items():
        rows_to_insert.append({
            "user_id": str(user_id),
            "src": conf.get("src"),
            "dst": conf.get("dst"),
            "lang": conf.get("lang", "en"),
            "username": conf.get("username", ""),
            "active": conf.get("active", True)
        })

    print(f"🔄 Preparing to migrate {len(rows_to_insert)} user settings to Supabase...")

    try:
        # Upsert handles inserting new records or updating existing ones safely
        response = supabase.table("user_settings").upsert(rows_to_insert).execute()
        print("✅ Migration completed successfully! All user settings have been saved to Supabase.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate_settings()