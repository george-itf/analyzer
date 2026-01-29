#!/usr/bin/env python3
"""Script to review and clean up duplicate ASIN mappings."""

import sys
sys.path.insert(0, '.')

from src.db.repository import Repository
from src.db.session import get_session
from sqlalchemy import text

def main():
    repo = Repository()
    duplicates = repo.find_duplicate_asins()
    
    if not duplicates:
        print("✅ No duplicates found!")
        return
    
    print(f"Found {len(duplicates)} duplicate ASINs\n")
    
    for asin, count, parts in duplicates:
        print(f"\n{'='*60}")
        print(f"ASIN: {asin} (mapped to {count} items)")
        print(f"Part numbers: {', '.join(parts)}")
        
        # Get details for each mapping
        with get_session() as s:
            details = s.execute(text("""
                SELECT ac.id, ac.part_number, si.description, si.cost_ex_vat_1
                FROM asin_candidates ac
                JOIN supplier_items si ON ac.supplier_item_id = si.id
                WHERE ac.asin = :asin
            """), {"asin": asin}).fetchall()
            
            print("\nDetails:")
            for cid, pn, desc, cost in details:
                print(f"  [{cid}] {pn}: {desc[:50]}... (£{float(cost):.2f})")
        
        # In a real cleanup, you'd prompt which to keep
        # For now, just report

if __name__ == "__main__":
    main()
