#!/usr/bin/env python3
"""
Auto-categorization service for Uber/Didi trips.
Reads work/home addresses from config/settings.json with fallback to hardcoded values.
"""
import re
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'settings.json'

# Fallback values if settings.json is missing (empty - user must configure)
_DEFAULT_WORK_ADDRESSES = []

_DEFAULT_HOME_ADDRESS = ""


def _load_settings():
    """Load settings from config file with fallback to defaults."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_work_addresses():
    """Get list of work addresses (normalized, lowercase)."""
    settings = _load_settings()
    return settings.get('work_addresses', _DEFAULT_WORK_ADDRESSES)


def get_home_address():
    """Get home address (normalized, lowercase)."""
    settings = _load_settings()
    return settings.get('home_address', _DEFAULT_HOME_ADDRESS)


def save_settings(work_addresses, home_address, personal_addresses=None):
    """Save updated addresses to config file."""
    settings = _load_settings()
    settings['work_addresses'] = work_addresses
    settings['home_address'] = home_address
    if personal_addresses is not None:
        settings['personal_addresses'] = personal_addresses

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


def normalize_address(addr):
    """Normalize address for fuzzy matching."""
    if not addr:
        return ""
    addr = str(addr).lower()
    # Remove accents/tildes
    addr = addr.replace('a\u0301', 'a').replace('e\u0301', 'e').replace('i\u0301', 'i')
    addr = addr.replace('o\u0301', 'o').replace('u\u0301', 'u').replace('n\u0303', 'n')
    addr = addr.replace('\u00e1', 'a').replace('\u00e9', 'e').replace('\u00ed', 'i')
    addr = addr.replace('\u00f3', 'o').replace('\u00fa', 'u').replace('\u00f1', 'n')
    # Remove common abbreviations and punctuation
    addr = re.sub(r'\bav\.?\s*', '', addr)
    addr = re.sub(r'\bavenida\s*', '', addr)
    addr = re.sub(r'\bcalle\s*', '', addr)
    addr = re.sub(r'\bgral\.?\s*', '', addr)
    addr = re.sub(r'\bgeneral\s*', '', addr)
    addr = re.sub(r',.*', '', addr)  # Remove everything after comma
    addr = re.sub(r'\s+', ' ', addr)  # Normalize spaces
    return addr.strip()


def categorize_trip(origin, destination):
    """
    Categorize a trip based on origin and destination.

    Returns: 'Laburo', 'Personal', or None (needs manual review)

    Logic:
    1. If ANY work address is involved -> Laburo
    2. If only home is involved (no work) -> Personal
    3. Otherwise -> None (unknown)
    """
    origin_norm = normalize_address(origin)
    destination_norm = normalize_address(destination)

    work_addresses = [normalize_address(w) for w in get_work_addresses()]
    home_address = normalize_address(get_home_address())

    # Priority 1: Check if any work address is involved
    for work_addr in work_addresses:
        if work_addr and (work_addr in origin_norm or work_addr in destination_norm):
            return 'Laburo'

    # Priority 2: If trip involves home but no work address, it's personal
    if home_address and (home_address in origin_norm or home_address in destination_norm):
        return 'Personal'

    # Priority 3: Unknown - needs manual review
    return None


def categorize_all_trips(db_module=None):
    """
    Auto-categorize all uncategorized trips in the database.

    Args:
        db_module: database module (imported here to avoid circular imports)

    Returns:
        dict with categorized, needs_review, work, personal counts
    """
    if db_module is None:
        from services import database as db_module

    trips = db_module.get_all_trips()
    updates = []
    stats = {'categorized': 0, 'needs_review': 0, 'work': 0, 'personal': 0}

    for trip in trips:
        # Skip trips that already have a manually-set category
        if trip['category'] and not trip['auto_categorized']:
            continue

        category = categorize_trip(trip['origin'], trip['destination'])

        if category:
            updates.append((trip['id'], category))
            stats['categorized'] += 1
            if category == 'Laburo':
                stats['work'] += 1
            else:
                stats['personal'] += 1
        else:
            stats['needs_review'] += 1
            # Mark as needing review
            with db_module.get_connection() as conn:
                conn.execute(
                    "UPDATE trips SET needs_review = 1 WHERE id = ?",
                    (trip['id'],)
                )

    if updates:
        db_module.bulk_update_categories(updates)

    return stats
