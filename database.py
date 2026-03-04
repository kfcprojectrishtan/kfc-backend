import os
import json
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

# Load env
load_dotenv(Path(__file__).parent / ".env")
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key)

# ═══════════════════════════════════════════════
#  ORDERS
# ═══════════════════════════════════════════════

def get_all(status: str = None, phone: str = None, limit: int = 50, offset: int = 0) -> List[Dict]:
    query = supabase.table('orders').select('*').order('created_at', desc=True)
    if status:
        query = query.eq('status', status)
    if phone:
        query = query.eq('phone', phone)
        
    query = query.range(offset, offset + limit - 1)
    return query.execute().data

def get_by_id(order_id: str) -> Optional[Dict]:
    res = supabase.table('orders').select('*').eq('id', order_id).execute()
    return res.data[0] if res.data else None

def create(order: Dict) -> Dict:
    # Ensure items is list
    if 'items' not in order or not isinstance(order['items'], list):
        order['items'] = []
    res = supabase.table('orders').insert(order).execute()
    return res.data[0]

def update_status(order_id: str, status: str) -> Optional[dict]:
    res = supabase.table('orders').update({'status': status}).eq('id', order_id).execute()
    if len(res.data) > 0:
        return res.data[0]
    return None

def update_tg_msg_id(order_id: str, msg_id: int) -> bool:
    res = supabase.table('orders').update({'tg_msg_id': msg_id}).eq('id', order_id).execute()
    return len(res.data) > 0

def count(status: str = None, phone: str = None) -> int:
    query = supabase.table('orders').select('id', count='exact')
    if status:
        query = query.eq('status', status)
    if phone:
        query = query.eq('phone', phone)
    res = query.execute()
    return res.count if res.count is not None else 0

def stats_today() -> dict:
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    # In Supabase we can use gte and lt for dates or string match
    res = supabase.table('orders').select('total,status').gte('created_at', f"{today_prefix}T00:00:00").execute()
    orders = res.data
    
    total_sales = sum(o.get("total", 0) for o in orders if o.get("status") == "delivered")
    total_orders = len(orders)
    return {
        "revenue": total_sales,
        "orders_count": total_orders
    }

def stats_monthly() -> list:
    res = supabase.table('orders').select('total,status,created_at').execute()
    orders = res.data
    
    daily: dict[str, dict] = {}
    for o in orders:
        if not o.get('created_at'): continue
        dstr = o['created_at'][:10]
        if dstr not in daily:
            daily[dstr] = {"date": dstr, "revenue": 0, "orders_count": 0}
        
        daily[dstr]["orders_count"] += 1
        if o.get("status") == "delivered":
            daily[dstr]["revenue"] += o.get("total", 0)
            
    dates = sorted(daily.keys())
    return [daily[d] for d in dates]

# ═══════════════════════════════════════════════
#  ORDER COUNTER
# ═══════════════════════════════════════════════

def _max_order_number_from_orders() -> int:
    # We used string IDs like '0001', '0123'
    res = supabase.table('orders').select('id').execute()
    max_num = 0
    for row in res.data:
        try:
            val = int(row['id'])
            if val > max_num:
                max_num = val
        except:
            pass
    return max_num

def next_order_number() -> int:
    res = supabase.table('order_counter').select('last_number').eq('id', 1).execute()
    if not res.data:
        # Failsafe
        max_id = _max_order_number_from_orders()
        ans = max_id + 1
        supabase.table('order_counter').insert({'id': 1, 'last_number': ans}).execute()
        return ans
    
    current = res.data[0]['last_number']
    ans = max(current, _max_order_number_from_orders()) + 1
    supabase.table('order_counter').update({'last_number': ans}).eq('id', 1).execute()
    return ans

def order_id_from_number(num: int) -> str:
    return f"{num:04d}"

# ═══════════════════════════════════════════════
#  TELEGRAM USERS
# ═══════════════════════════════════════════════

def get_telegram_user(phone: str) -> Optional[dict]:
    res = supabase.table('telegram_users').select('*').eq('phone', phone).execute()
    return res.data[0] if res.data else None

def get_telegram_user_by_chat_id(chat_id: int) -> Optional[dict]:
    res = supabase.table('telegram_users').select('*').eq('chat_id', chat_id).execute()
    return res.data[0] if res.data else None

def save_telegram_user(phone: str, chat_id: int, username: str = None, full_name: str = None):
    data = {
        'phone': phone,
        'chat_id': chat_id,
        'username': username,
        'full_name': full_name
    }
    
    existing = get_telegram_user(phone)
    if existing:
        supabase.table('telegram_users').update(data).eq('phone', phone).execute()
    else:
        supabase.table('telegram_users').insert(data).execute()

def update_telegram_user_coins(phone: str, coins: int):
    # This just updates the cached coin value in telegram_users table
    user = get_telegram_user(phone)
    if user:
        supabase.table('telegram_users').update({'coins': coins}).eq('phone', phone).execute()

# ═══════════════════════════════════════════════
#  OTP CODES
# ═══════════════════════════════════════════════

def get_otp(phone: str) -> Optional[dict]:
    res = supabase.table('otp_codes').select('*').eq('phone', phone).execute()
    if not res.data:
        return None
    otp = res.data[0]
    # Check expiry (naive timestamp comparison via python)
    # the schema now uses TIMESTAMPTZ, but the python code originally did time.time() float
    # We will convert format
    return otp

def save_otp(phone: str, code: str, expires_at: float, mode: str = "login"):
    # Convert POSIX timestamp to ISO format for TIMESTAMPTZ column
    dt = datetime.fromtimestamp(expires_at).isoformat()
    data = {
        'phone': phone,
        'code': code,
        'expires_at': dt,
        'mode': mode,
        'attempts': 0
    }
    supabase.table('otp_codes').upsert(data).execute()

def delete_otp(phone: str):
    supabase.table('otp_codes').delete().eq('phone', phone).execute()

def increment_otp_attempts(phone: str) -> int:
    otp = get_otp(phone)
    if not otp: return 0
    att = otp.get('attempts', 0) + 1
    supabase.table('otp_codes').update({'attempts': att}).eq('phone', phone).execute()
    return att

# ═══════════════════════════════════════════════
#  REGISTERED USERS
# ═══════════════════════════════════════════════

def get_registered_user(phone: str) -> Optional[dict]:
    res = supabase.table('registered_users').select('*').eq('phone', phone).execute()
    return res.data[0] if res.data else None

def save_registered_user(phone: str, first_name: str, last_name: str):
    data = {
        'phone': phone,
        'first_name': first_name,
        'last_name': last_name
    }
    supabase.table('registered_users').upsert(data).execute()

# ═══════════════════════════════════════════════
#  BANNED USERS
# ═══════════════════════════════════════════════

def is_banned(phone: str) -> bool:
    res = supabase.table('banned_users').select('id').eq('phone', phone).eq('is_active', True).execute()
    return len(res.data) > 0 if res.data else False

def ban_user(phone: str, reason: str = None, admin_id: int = None):
    data = {
        'phone': phone,
        'reason': reason,
        'banned_by': admin_id,
        'is_active': True,
        'banned_at': datetime.utcnow().isoformat()
    }
    # For upsert, supabase python needs a list of dicts or dict. The schema constraint is phone = UNIQUE.
    # To upsert carefully, we check if it exists or use upsert.
    # supabase-py v2 upsert on primary keys, but phone is UNIQUE not PK.
    # So we'll try to find it first.
    existing = supabase.table('banned_users').select('id').eq('phone', phone).execute()
    if existing.data:
        supabase.table('banned_users').update(data).eq('phone', phone).execute()
    else:
        supabase.table('banned_users').insert(data).execute()

def unban_user(phone: str):
    supabase.table('banned_users').update({'is_active': False}).eq('phone', phone).execute()

# ═══════════════════════════════════════════════
#  COINS
# ═══════════════════════════════════════════════

def get_coins(phone: str) -> int:
    res = supabase.table('coins_transactions').select('amount').eq('phone', phone).execute()
    return sum(row['amount'] for row in res.data)

def add_coins(phone: str, amount: int, order_id: str) -> int:
    if amount <= 0:
        return get_coins(phone)
    
    supabase.table('coins_transactions').insert({
        'phone': phone,
        'amount': amount,
        'order_id': order_id
    }).execute()
    
    total = get_coins(phone)
    update_telegram_user_coins(phone, total)
    return total

def spend_coins(phone: str, amount: int, order_id: str) -> int:
    if amount <= 0:
        return get_coins(phone)
        
    current = get_coins(phone)
    if current < amount:
        return current
        
    supabase.table('coins_transactions').insert({
        'phone': phone,
        'amount': -amount,
        'order_id': order_id
    }).execute()
    
    total = get_coins(phone)
    update_telegram_user_coins(phone, total)
    return total

# ═══════════════════════════════════════════════
#  MENU CATEGORIES
# ═══════════════════════════════════════════════

def menu_get_categories(active_only: bool = False) -> List[dict]:
    query = supabase.table('menu_categories').select('*').order('sort_order', desc=False)
    if active_only:
        query = query.eq('is_active', True)
    res = query.execute()
    
    # Restore the 'key' property since the frontend/backend relies on 'key' instead of 'slug'
    cats = res.data
    for cat in cats:
        cat['key'] = cat.pop('slug', '')
    return cats

def menu_create_category(cat: dict):
    # Convert 'key' back to 'slug'
    slug = cat.pop('key')
    cat['slug'] = slug
    
    # Auto-generate ID if not completely handled by SERIAL
    # Removing 'id' since it's a SERIAL primary key in postgres
    if 'id' in cat:
        del cat['id']
        
    res = supabase.table('menu_categories').insert(cat).execute()
    return res.data[0] if res.data else {}

def menu_update_category(cat_id: int, patch: dict):
    if 'key' in patch:
        patch['slug'] = patch.pop('key')
    res = supabase.table('menu_categories').update(patch).eq('id', cat_id).execute()
    return res.data[0] if res.data else {}

def menu_delete_category(cat_id: int):
    # First check if foods depend on this category
    res = supabase.table('menu_foods').select('id').eq('category_id', cat_id).execute()
    if res.data:
        raise ValueError("Bu kategoriyada ovqatlar bor! Oldin ularni o'chiring.")
        
    supabase.table('menu_categories').delete().eq('id', cat_id).execute()

# ═══════════════════════════════════════════════
#  MENU FOODS
# ═══════════════════════════════════════════════

def menu_get_foods(category: str = None, search: str = None, active_only: bool = False) -> List[dict]:
    # We joined menu_foods with menu_categories to support searching by category 'key' (slug)
    query = supabase.table('menu_foods').select('*, menu_categories(slug)').order('id', desc=False)
    if active_only:
        query = query.eq('is_active', True)
    if search:
        query = query.ilike('name', f"%{search}%")
        
    res = query.execute()
    foods = res.data
    
    final_foods = []
    for food in foods:
        cat_data = food.get('menu_categories') or {}
        cat_slug = cat_data.get('slug', '')
        # Only return items matching category if filter applied
        if category and cat_slug != category:
            continue
            
        food['category'] = cat_slug
        
        # Combine image_emoji and image_url to the old single 'image' format if it matches
        if food.get('image_url'):
            food['image'] = food['image_url']
        elif food.get('image_emoji'):
            food['image'] = food['image_emoji']
        else:
            food['image'] = ''
            
        final_foods.append(food)
        
    return final_foods

def menu_create_food(food: dict):
    cat_slug = food.pop('category', '')
    res = supabase.table('menu_categories').select('id').eq('slug', cat_slug).execute()
    if res.data:
        food['category_id'] = res.data[0]['id']
        
    if 'id' in food:
        del food['id']
        
    # Split 'image' back into image_url or image_emoji
    image_val = food.pop('image', '')
    if image_val.startswith('http') or image_val.startswith('/static/'):
        food['image_url'] = image_val
        food['image_emoji'] = ''
    else:
        food['image_url'] = ''
        food['image_emoji'] = image_val
        
    res = supabase.table('menu_foods').insert(food).execute()
    return res.data[0] if res.data else {}

def menu_update_food(food_id: int, patch: dict):
    if 'category' in patch:
        cat_slug = patch.pop('category')
        res = supabase.table('menu_categories').select('id').eq('slug', cat_slug).execute()
        if res.data:
            patch['category_id'] = res.data[0]['id']
            
    if 'image' in patch:
        image_val = patch.pop('image')
        if image_val.startswith('http') or image_val.startswith('/static/'):
            patch['image_url'] = image_val
            patch['image_emoji'] = ''
        else:
            patch['image_url'] = ''
            patch['image_emoji'] = image_val
            
    res = supabase.table('menu_foods').update(patch).eq('id', food_id).execute()
    return res.data[0] if res.data else {}

def menu_delete_food(food_id: int):
    supabase.table('menu_foods').delete().eq('id', food_id).execute()
