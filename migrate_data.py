import os
import json
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

DATA_DIR = Path(__file__).parent

def get_mime_type(filename):
    ext = filename.lower().split('.')[-1]
    if ext in ['png']: return 'image/png'
    if ext in ['jpg', 'jpeg']: return 'image/jpeg'
    if ext in ['webp']: return 'image/webp'
    if ext in ['gif']: return 'image/gif'
    return 'application/octet-stream'

def setup_db():
    print("Emptying tables...")
    try:
        supabase.table("menu_foods").delete().neq("id", 0).execute()
        supabase.table("menu_categories").delete().neq("id", 0).execute()
    except Exception as e:
        print(f"Warning on delete: {e}")
        
    print("Ensuring bucket exists...")
    try:
        supabase.storage.get_bucket("menu-images")
    except Exception:
        supabase.storage.create_bucket("menu-images", name="menu-images", options={"public": True})

def migrate_categories():
    print("Migrating Categories...")
    cat_file = DATA_DIR / "menu_categories.json"
    if not cat_file.exists():
        print("No categories file found.")
        return {}

    with open(cat_file, "r", encoding="utf-8") as f:
        categories = json.load(f)

    # map slug -> id for foods later
    cat_map = {}

    for cat in categories:
        local_img = cat.get("image_url", "")
        new_img_url = ""
        
        # Upload image if it's a local static file
        if local_img and local_img.startswith("/static/menu/categories/"):
            filename = local_img.split("/")[-1]
            local_path = DATA_DIR / "uploads" / "menu" / "categories" / filename
            if local_path.exists():
                print(f"Uploading category image: {filename}")
                with open(local_path, "rb") as f:
                    supabase.storage.from_("menu-images").upload(f"categories/{filename}", f, file_options={"content-type": get_mime_type(filename)})
                new_img_url = supabase.storage.from_("menu-images").get_public_url(f"categories/{filename}")
            else:
                print(f"File not found: {local_path}")

        # Insert to DB
        data = {
            "slug": cat["key"],
            "title": cat["title"],
            "sort_order": cat.get("sort_order", 0),
            "is_active": cat.get("is_active", True),
            "image_emoji": cat.get("image_emoji", ""),
            "image_url": new_img_url if new_img_url else local_img
        }
        resp = supabase.table("menu_categories").insert(data).execute()
        new_id = resp.data[0]["id"]
        cat_map[cat["key"]] = new_id
        print(f"Inserted category: {cat['title']} (ID: {new_id})")

    return cat_map

def migrate_foods(cat_map):
    print("\nMigrating Foods...")
    food_file = DATA_DIR / "menu_foods.json"
    if not food_file.exists():
        print("No foods file found.")
        return

    with open(food_file, "r", encoding="utf-8") as f:
        foods = json.load(f)

    for food in foods:
        image_field = food.get("image", "")
        new_img_url = ""
        emoji = ""
        
        if image_field.startswith("/static/menu/"):
            filename = image_field.split("/")[-1]
            local_path = DATA_DIR / "uploads" / "menu" / filename
            if local_path.exists():
                print(f"Uploading food image: {filename}")
                with open(local_path, "rb") as f:
                    supabase.storage.from_("menu-images").upload(f"foods/{filename}", f, file_options={"content-type": get_mime_type(filename)})
                new_img_url = supabase.storage.from_("menu-images").get_public_url(f"foods/{filename}")
            else:
                print(f"File not found: {local_path}")
        else:
            emoji = image_field # It's an emoji

        cat_slug = food.get("category")
        cat_id = cat_map.get(cat_slug)

        if not cat_id:
            print(f"Warning: Category {cat_slug} not found for food {food['name']}")
            continue

        data = {
            "name": food["name"],
            "full_name": food.get("fullName"),
            "description": food.get("description", ""),
            "price": food["price"],
            "category_id": cat_id,
            "image_emoji": emoji,
            "image_url": new_img_url,
            "is_active": food.get("is_active", True)
        }
        supabase.table("menu_foods").insert(data).execute()
        print(f"Inserted food: {food['name']}")

def main():
    setup_db()
    cat_map = migrate_categories()
    migrate_foods(cat_map)
    print("\nData check complete!")

if __name__ == "__main__":
    main()
