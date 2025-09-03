#!/usr/bin/env python3
"""
Parallel CIM downloader - runs multiple download processes to speed up bulk downloads.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from typing import List, Dict
import pymysql
from concurrent.futures import ProcessPoolExecutor, as_completed
import re

def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',
        port=3307,
        user='forge',
        password='mFGaHKEBBYLqpnUV3VUW',
        database='ac_prod',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def get_existing_cim_ids() -> set:
    """Get listing IDs for CIMs we already have."""
    cims_dir = Path('cims')
    cim_listing_ids = set()
    
    for f in cims_dir.glob('*.pdf'):
        match = re.match(r'^(\d+)[_\-]', f.name)
        if match:
            cim_listing_ids.add(int(match.group(1)))
    
    return cim_listing_ids

def get_all_downloadable_listings() -> List[int]:
    """Get all listing IDs that have Drive folders and we don't have CIMs for."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existing_ids = get_existing_cim_ids()
    
    # Get listings with business summary folders
    cursor.execute("""
        SELECT DISTINCT l.id
        FROM listings l
        WHERE 
            (l.business_summary_folder_id IS NOT NULL AND l.business_summary_folder_id != '')
            OR (l.drive_folder_id IS NOT NULL AND l.drive_folder_id != '')
            OR (l.google_drive_link IS NOT NULL AND l.google_drive_link != '')
        ORDER BY 
            CASE WHEN l.closed_type = 1 THEN 0 ELSE 1 END,  -- Sold first
            l.id
    """)
    
    all_ids = [row['id'] for row in cursor.fetchall()]
    conn.close()
    
    # Filter out existing
    missing_ids = [lid for lid in all_ids if lid not in existing_ids]
    
    return missing_ids

def download_batch(batch_ids: List[int], worker_id: int) -> Dict:
    """Download a batch of CIMs using the main download script."""
    from download_cims_from_drive import (
        get_listings_to_download, 
        process_listing,
        SERVICE_ACCOUNT_FILE,
        SCOPES,
        OUTPUT_DIR
    )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    results = {
        'worker_id': worker_id,
        'total': len(batch_ids),
        'successful': 0,
        'failed': 0,
        'listings': []
    }
    
    try:
        # Set up Drive API for this worker
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        
        # Get full listing data for our batch
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT 
                l.id,
                l.name,
                l.google_drive_link,
                l.business_summary_folder_id,
                l.drive_folder_id,
                l.closed_type,
                CASE
                    WHEN l.closed_type = 1 THEN 'sold'
                    WHEN l.closed_type = 2 THEN 'lost'
                    ELSE 'active'
                END as status
            FROM listings l
            WHERE l.id IN ({','.join(map(str, batch_ids))})
        """)
        
        listings = cursor.fetchall()
        conn.close()
        
        # Process each listing
        for i, listing in enumerate(listings):
            try:
                print(f"[Worker {worker_id}] Processing {i+1}/{len(listings)}: {listing['id']}")
                result = process_listing(service, listing)
                
                if result['downloaded']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    
                results['listings'].append(result)
                
                # Small delay to avoid rate limits
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error processing {listing['id']}: {e}")
                results['failed'] += 1
                
    except Exception as e:
        print(f"[Worker {worker_id}] Fatal error: {e}")
        results['error'] = str(e)
    
    return results

def parallel_download(total_limit: int = 100, workers: int = 3):
    """Download CIMs in parallel using multiple workers."""
    
    print(f"Starting parallel download with {workers} workers")
    print("="*60)
    
    # Get listings to download
    missing_ids = get_all_downloadable_listings()
    
    if not missing_ids:
        print("No missing CIMs to download!")
        return
    
    # Apply limit
    if total_limit and len(missing_ids) > total_limit:
        missing_ids = missing_ids[:total_limit]
    
    print(f"Found {len(missing_ids)} CIMs to download")
    
    # Split into batches for workers
    batch_size = len(missing_ids) // workers + 1
    batches = []
    for i in range(0, len(missing_ids), batch_size):
        batch = missing_ids[i:i+batch_size]
        if batch:
            batches.append(batch)
    
    print(f"Split into {len(batches)} batches (~{batch_size} each)")
    
    # Run parallel downloads
    start_time = time.time()
    all_results = []
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_batch, batch, i): i 
            for i, batch in enumerate(batches)
        }
        
        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                result = future.result()
                all_results.append(result)
                print(f"\n[Worker {worker_id}] Completed: {result['successful']} successful, {result['failed']} failed")
            except Exception as e:
                print(f"\n[Worker {worker_id}] Failed: {e}")
    
    # Summarize results
    elapsed = time.time() - start_time
    total_successful = sum(r['successful'] for r in all_results)
    total_failed = sum(r['failed'] for r in all_results)
    
    print("\n" + "="*60)
    print("PARALLEL DOWNLOAD COMPLETE")
    print("="*60)
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print(f"Total successful: {total_successful}")
    print(f"Total failed: {total_failed}")
    print(f"Success rate: {total_successful/(total_successful+total_failed)*100:.1f}%")
    print(f"Downloads per second: {total_successful/elapsed:.2f}")
    
    # Save detailed results
    with open('parallel_download_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print("\nDetailed results saved to parallel_download_results.json")

def monitor_progress():
    """Monitor download progress in real-time."""
    initial_count = len(get_existing_cim_ids())
    print(f"Starting with {initial_count} CIMs")
    
    while True:
        time.sleep(10)
        current_count = len(get_existing_cim_ids())
        new_downloads = current_count - initial_count
        
        if new_downloads > 0:
            print(f"Progress: {new_downloads} new CIMs downloaded (Total: {current_count})")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Parallel CIM Downloader')
    parser.add_argument('--limit', type=int, default=100, help='Total number of CIMs to download')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers')
    parser.add_argument('--monitor', action='store_true', help='Monitor progress only')
    
    args = parser.parse_args()
    
    if args.monitor:
        print("Monitoring download progress (Ctrl+C to stop)...")
        try:
            monitor_progress()
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    else:
        # Check service account exists
        if not os.path.exists('service_account.json'):
            print("ERROR: service_account.json not found!")
            sys.exit(1)
        
        # Check current status
        existing = len(get_existing_cim_ids())
        missing = len(get_all_downloadable_listings())
        
        print(f"Current status:")
        print(f"  CIMs already downloaded: {existing}")
        print(f"  CIMs available to download: {missing}")
        
        if missing == 0:
            print("\nAll available CIMs have been downloaded!")
            sys.exit(0)
        
        # Confirm before starting
        print(f"\nWill download up to {args.limit} CIMs using {args.workers} workers")
        response = input("Continue? (yes/no): ")
        
        if response.lower() == 'yes':
            parallel_download(args.limit, args.workers)
        else:
            print("Cancelled")