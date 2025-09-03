#!/usr/bin/env python3
"""
Download CIMs from Google Drive using the service account.
Searches through folders and subfolders for Business Summary PDFs.
"""

import os
import io
import re
import json
import time
import pymysql
from pathlib import Path
from typing import List, Dict, Optional, Set
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
OUTPUT_DIR = Path('cims')
CACHE_FILE = 'drive_search_cache.json'
MAX_WORKERS = 3  # Parallel downloads

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

def get_existing_cim_ids() -> Set[int]:
    """Get listing IDs for CIMs we already have."""
    cim_listing_ids = set()
    
    for f in OUTPUT_DIR.glob('*.pdf'):
        match = re.match(r'^(\d+)[_\-]', f.name)
        if match:
            cim_listing_ids.add(int(match.group(1)))
    
    return cim_listing_ids

def get_listings_to_download(limit: int = None) -> List[Dict]:
    """Get listings with Google Drive links that we don't have CIMs for."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existing_ids = get_existing_cim_ids()
    
    # Focus on sold and lost listings with Drive links
    query = """
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
        END as status,
        COUNT(i.id) as inquiry_count
    FROM listings l
    LEFT JOIN inquiries i ON l.id = i.listing_id
    WHERE 
        l.google_drive_link IS NOT NULL 
        AND l.google_drive_link != ''
        AND l.deleted_at IS NULL
    GROUP BY l.id
    ORDER BY 
        CASE WHEN l.closed_type = 1 THEN 0 ELSE 1 END,  -- Sold first
        inquiry_count DESC  -- Most inquiries next
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    
    # Filter out ones we already have
    missing = [r for r in results if r['id'] not in existing_ids]
    
    return missing

def extract_folder_id(url: str) -> Optional[str]:
    """Extract Google Drive folder ID from various URL formats."""
    if not url:
        return None
    
    patterns = [
        r'/folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/d/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def search_folder_recursive(service, folder_id: str, listing_id: int, depth: int = 0, max_depth: int = 3) -> Optional[Dict]:
    """
    Recursively search a folder and its subfolders for Business Summary PDFs.
    """
    if depth > max_depth:
        return None
    
    try:
        # Search for PDFs in current folder
        query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, size, mimeType)",
            pageSize=100
        ).execute()
        
        files = results.get('files', [])
        
        # Look for Business Summary or CIM files
        for file in files:
            fname = file['name'].lower()
            # Check for various naming patterns
            if any(term in fname for term in [
                'business summary', 
                'cim', 
                'confidential',
                'information memorandum',
                'executive summary',
                f'{listing_id}',  # Sometimes named with listing ID
                'start here'  # Common pattern in file names
            ]):
                print(f"    Found: {file['name']}")
                return file
        
        # If not found, search subfolders
        if depth < max_depth:
            # Get all folders in current folder
            folder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            folder_results = service.files().list(
                q=folder_query,
                fields="files(id, name)",
                pageSize=50
            ).execute()
            
            subfolders = folder_results.get('files', [])
            
            # Search each subfolder
            for subfolder in subfolders:
                print(f"    Searching subfolder: {subfolder['name']}")
                result = search_folder_recursive(service, subfolder['id'], listing_id, depth + 1, max_depth)
                if result:
                    return result
        
    except HttpError as e:
        if e.resp.status == 404:
            print(f"    Folder not found or no access: {folder_id}")
        else:
            print(f"    Error searching folder: {e}")
    
    return None

def download_file(service, file_id: str, output_path: Path) -> bool:
    """Download a file from Google Drive."""
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status and status.progress():
                print(f"      Download {int(status.progress() * 100)}%", end='\r')
        
        # Save file
        fh.seek(0)
        with open(output_path, 'wb') as f:
            f.write(fh.read())
        
        print(f"      Saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"      Error downloading: {e}")
        return False

def process_listing(service, listing: Dict) -> Dict:
    """Process a single listing to find and download its CIM."""
    listing_id = listing['id']
    result = {
        'listing_id': listing_id,
        'name': listing['name'],
        'status': listing['status'],
        'found': False,
        'downloaded': False,
        'file_name': None,
        'error': None
    }
    
    print(f"\nProcessing listing {listing_id}: {listing['name'][:50]}...")
    
    # Try different folder sources
    folder_ids = []
    
    # 1. Business summary folder (most likely)
    if listing.get('business_summary_folder_id'):
        folder_ids.append(('business_summary_folder', listing['business_summary_folder_id']))
    
    # 2. Main drive folder
    if listing.get('drive_folder_id'):
        folder_ids.append(('drive_folder', listing['drive_folder_id']))
    
    # 3. Extract from Google Drive link
    if listing.get('google_drive_link'):
        folder_id = extract_folder_id(listing['google_drive_link'])
        if folder_id:
            folder_ids.append(('drive_link', folder_id))
    
    if not folder_ids:
        result['error'] = 'No folder IDs found'
        print(f"  No folder IDs found for listing {listing_id}")
        return result
    
    # Try each folder
    for folder_type, folder_id in folder_ids:
        print(f"  Searching in {folder_type}: {folder_id}")
        
        file = search_folder_recursive(service, folder_id, listing_id)
        
        if file:
            result['found'] = True
            result['file_name'] = file['name']
            
            # Clean filename for saving
            safe_name = re.sub(r'[^\w\s\-\.]', '', file['name'])
            safe_name = re.sub(r'\s+', '_', safe_name)
            output_path = OUTPUT_DIR / f"{listing_id}_{safe_name}"
            
            # Download the file
            if download_file(service, file['id'], output_path):
                result['downloaded'] = True
                print(f"  ✓ Successfully downloaded CIM for listing {listing_id}")
            else:
                result['error'] = 'Download failed'
            
            break
    
    if not result['found']:
        result['error'] = 'No CIM found in any folder'
        print(f"  ✗ No CIM found for listing {listing_id}")
    
    return result

def download_cims_batch(limit: int = 10, start_from: int = 0):
    """Download CIMs for listings in batches."""
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Check for service account file
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("ERROR: service_account.json not found!")
        print("Please add the Google service account JSON file to the current directory.")
        return
    
    # Set up Drive API
    print("Setting up Google Drive API...")
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)
    
    # Test connection
    try:
        about = service.about().get(fields="user").execute()
        print(f"Connected as: {about['user']['emailAddress']}")
    except Exception as e:
        print(f"Failed to connect to Google Drive API: {e}")
        return
    
    # Get listings to download
    print("\nFetching listings from database...")
    listings = get_listings_to_download()
    
    # Apply start and limit
    if start_from:
        listings = listings[start_from:]
    if limit:
        listings = listings[:limit]
    
    print(f"Found {len(listings)} listings to process")
    
    # Process listings
    results = []
    successful = 0
    failed = 0
    
    for i, listing in enumerate(listings, 1):
        print(f"\n[{i}/{len(listings)}]", end='')
        result = process_listing(service, listing)
        results.append(result)
        
        if result['downloaded']:
            successful += 1
        else:
            failed += 1
        
        # Rate limiting
        time.sleep(0.5)
    
    # Save results
    results_file = 'cim_download_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Summary
    print("\n" + "="*60)
    print("DOWNLOAD SUMMARY")
    print("="*60)
    print(f"Total processed: {len(results)}")
    print(f"Successfully downloaded: {successful}")
    print(f"Failed/Not found: {failed}")
    print(f"Results saved to: {results_file}")
    
    # Show failures
    failures = [r for r in results if not r['downloaded']]
    if failures:
        print("\nFailed downloads:")
        for f in failures[:10]:
            print(f"  {f['listing_id']}: {f['error']}")

def validate_downloads():
    """Validate that downloaded CIMs match their listings."""
    print("Validating downloaded CIMs...")
    
    existing_ids = get_existing_cim_ids()
    print(f"Found {len(existing_ids)} CIM files")
    
    # Check database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT 
            id,
            name,
            closed_type,
            CASE
                WHEN closed_type = 1 THEN 'sold'
                WHEN closed_type = 2 THEN 'lost'
                ELSE 'active'
            END as status
        FROM listings
        WHERE id IN ({','.join(map(str, existing_ids))})
    """)
    
    db_listings = {r['id']: r for r in cursor.fetchall()}
    conn.close()
    
    # Validate each CIM
    print("\nValidation results:")
    missing_in_db = []
    status_breakdown = {'sold': 0, 'lost': 0, 'active': 0}
    
    for listing_id in existing_ids:
        if listing_id in db_listings:
            status = db_listings[listing_id]['status']
            status_breakdown[status] += 1
        else:
            missing_in_db.append(listing_id)
    
    print(f"  Sold: {status_breakdown['sold']}")
    print(f"  Lost: {status_breakdown['lost']}")
    print(f"  Active: {status_breakdown['active']}")
    
    if missing_in_db:
        print(f"  Missing in database: {len(missing_in_db)}")
        print(f"    IDs: {missing_in_db[:10]}")

if __name__ == "__main__":
    import sys
    
    print("CIM Downloader from Google Drive")
    print("="*60)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'validate':
            validate_downloads()
        elif sys.argv[1] == 'test':
            print("Testing with 5 listings...")
            download_cims_batch(limit=5)
        else:
            limit = int(sys.argv[1])
            print(f"Downloading {limit} CIMs...")
            download_cims_batch(limit=limit)
    else:
        print("\nUsage:")
        print("  python3 download_cims_from_drive.py test     # Test with 5 listings")
        print("  python3 download_cims_from_drive.py 50       # Download 50 CIMs")
        print("  python3 download_cims_from_drive.py validate # Validate existing CIMs")
        print("\nNote: Requires service_account.json in current directory")
        
        # Check current status
        existing = len(get_existing_cim_ids())
        print(f"\nCurrent status: {existing} CIMs already downloaded")
        
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print("\n⚠️  WARNING: service_account.json not found!")
            print("   Please add your Google service account credentials file")