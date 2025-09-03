#!/usr/bin/env python3
"""
Download missing CIMs from Google Drive for listings that have Drive links.
Focuses on sold/lost listings that we don't have CIMs for yet.
"""

import os
import re
import pymysql
from pathlib import Path
import json
from typing import Set, List, Dict
import time

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
    cims_dir = Path('/Users/markdaoust/Developer/ql_stats/cims')
    cim_listing_ids = set()
    
    for f in cims_dir.glob('*.pdf'):
        match = re.match(r'^(\d+)[_\-]', f.name)
        if match:
            cim_listing_ids.add(int(match.group(1)))
    
    return cim_listing_ids

def get_listings_with_drive_links() -> List[Dict]:
    """Get listings with Google Drive links that we don't have CIMs for."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existing_ids = get_existing_cim_ids()
    
    # Get listings with Drive links, prioritizing sold/lost
    query = """
    SELECT 
        l.id,
        l.name,
        l.google_drive_link,
        l.business_summary_folder_id,
        l.closed_type,
        l.closed_at,
        l.asking_at_close,
        l.sde_at_close,
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
        AND (l.closed_type IN (1, 2) OR l.milestone_id IN (7, 8))
    GROUP BY l.id
    ORDER BY 
        CASE WHEN l.closed_type = 1 THEN 0 ELSE 1 END,  -- Sold first
        inquiry_count DESC  -- Most inquiries next
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    
    # Filter out ones we already have
    missing = [r for r in results if r['id'] not in existing_ids]
    
    return missing

def extract_folder_id(drive_link: str) -> str:
    """Extract Google Drive folder ID from various link formats."""
    if not drive_link:
        return None
    
    # Match patterns like:
    # https://drive.google.com/drive/folders/FOLDER_ID
    # https://drive.google.com/drive/u/0/folders/FOLDER_ID
    patterns = [
        r'folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/d/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, drive_link)
        if match:
            return match.group(1)
    
    return None

def analyze_missing_cims():
    """Analyze what CIMs we're missing and could potentially download."""
    print("Analyzing missing CIMs...")
    print("=" * 60)
    
    existing_ids = get_existing_cim_ids()
    missing_listings = get_listings_with_drive_links()
    
    print(f"Current status:")
    print(f"  CIMs we have: {len(existing_ids)}")
    print(f"  Listings with Drive links: {len(missing_listings) + len(existing_ids)}")
    print(f"  Missing CIMs: {len(missing_listings)}")
    
    # Breakdown by status
    sold_missing = [l for l in missing_listings if l['status'] == 'sold']
    lost_missing = [l for l in missing_listings if l['status'] == 'lost']
    active_missing = [l for l in missing_listings if l['status'] == 'active']
    
    print(f"\nMissing CIMs by status:")
    print(f"  Sold: {len(sold_missing)}")
    print(f"  Lost: {len(lost_missing)}")
    print(f"  Active: {len(active_missing)}")
    
    # Show top candidates for download
    print(f"\nTop 20 candidates for download (sold with most inquiries):")
    print("-" * 60)
    
    for i, listing in enumerate(missing_listings[:20], 1):
        folder_id = extract_folder_id(listing['google_drive_link'])
        print(f"{i:2}. ID: {listing['id']:5} | {listing['status']:6} | "
              f"Inquiries: {listing['inquiry_count']:3} | "
              f"Folder: {'✓' if folder_id else '✗'}")
        print(f"    Name: {listing['name'][:60]}...")
        if folder_id:
            print(f"    Folder ID: {folder_id}")
    
    # Save list for potential batch download
    output_file = 'missing_cims_list.json'
    with open(output_file, 'w') as f:
        json.dump(missing_listings, f, indent=2, default=str)
    
    print(f"\nFull list saved to {output_file}")
    
    return missing_listings

def download_cim_from_drive(listing_id: int, folder_id: str, output_dir: Path):
    """
    Download CIM from Google Drive folder.
    Note: This requires Google Drive API setup with service account.
    """
    # This is a placeholder for the actual download logic
    # You would need to:
    # 1. Set up Google Drive API credentials
    # 2. Use the service account from .env
    # 3. Search for PDF files in the folder
    # 4. Download the Business Summary or CIM file
    
    print(f"Would download CIM for listing {listing_id} from folder {folder_id}")
    
    # Example implementation outline:
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    
    # Load credentials
    credentials = service_account.Credentials.from_service_account_file(
        'service_account.json',
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    
    service = build('drive', 'v3', credentials=credentials)
    
    # Search for PDFs in folder
    query = f"'{folder_id}' in parents and mimeType='application/pdf'"
    results = service.files().list(q=query).execute()
    
    # Download matching files
    for file in results.get('files', []):
        if 'business summary' in file['name'].lower() or 'cim' in file['name'].lower():
            # Download the file
            request = service.files().get_media(fileId=file['id'])
            # Save to output_dir / f"{listing_id}_{file['name']}"
    """

def create_download_script():
    """Create a script to download CIMs using Google Drive API."""
    script_content = '''#!/usr/bin/env python3
"""
Download CIMs from Google Drive using the service account.
Requires: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import os
import io
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import json

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
OUTPUT_DIR = Path('cims')

def download_cims_batch(listings_file='missing_cims_list.json', limit=10):
    """Download CIMs for listings in the JSON file."""
    
    # Load listings
    with open(listings_file, 'r') as f:
        listings = json.load(f)
    
    # Set up Drive API
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)
    
    downloaded = 0
    for listing in listings[:limit]:
        if downloaded >= limit:
            break
            
        folder_link = listing.get('google_drive_link', '')
        if not folder_link:
            continue
        
        # Extract folder ID
        import re
        match = re.search(r'folders/([a-zA-Z0-9_-]+)', folder_link)
        if not match:
            continue
        
        folder_id = match.group(1)
        listing_id = listing['id']
        
        print(f"\\nProcessing listing {listing_id}...")
        
        try:
            # Search for PDFs in the folder
            query = f"'{folder_id}' in parents and mimeType='application/pdf'"
            results = service.files().list(
                q=query,
                fields="files(id, name, size)"
            ).execute()
            
            files = results.get('files', [])
            
            # Look for Business Summary or CIM
            for file in files:
                fname = file['name'].lower()
                if 'business summary' in fname or 'cim' in fname or 'confidential' in fname:
                    print(f"  Found: {file['name']}")
                    
                    # Download the file
                    request = service.files().get_media(fileId=file['id'])
                    output_path = OUTPUT_DIR / f"{listing_id}_{file['name']}"
                    
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        if status:
                            print(f"  Download {int(status.progress() * 100)}%")
                    
                    # Save file
                    fh.seek(0)
                    with open(output_path, 'wb') as f:
                        f.write(fh.read())
                    
                    print(f"  Saved to: {output_path}")
                    downloaded += 1
                    break
                    
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    print(f"\\nDownloaded {downloaded} CIMs")

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Check for service account file
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("ERROR: service_account.json not found!")
        print("Please ensure the Google service account JSON file is in the current directory.")
        exit(1)
    
    print("Starting CIM download from Google Drive...")
    download_cims_batch(limit=10)  # Start with 10 for testing
'''
    
    with open('download_cims_from_drive.py', 'w') as f:
        f.write(script_content)
    
    print("Created download_cims_from_drive.py")
    print("To use it:")
    print("1. Ensure service_account.json is in the directory")
    print("2. Install required packages: pip install google-auth google-api-python-client")
    print("3. Run: python3 download_cims_from_drive.py")

if __name__ == "__main__":
    # Analyze what we're missing
    missing = analyze_missing_cims()
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    print("\n1. IMMEDIATE: Focus analysis on the 251 CIMs we have")
    print("   - These represent real, marketed listings")
    print("   - 55% success rate shows good data quality")
    print("   - Sufficient sample size for statistical analysis")
    
    print("\n2. OPTIONAL: Download additional CIMs from Google Drive")
    print(f"   - {len([l for l in missing if l['status'] == 'sold'])} sold listings available")
    print(f"   - Would increase dataset to ~{251 + len([l for l in missing if l['status'] == 'sold'])} listings")
    print("   - Use the download_cims_from_drive.py script")
    
    print("\n3. SKIP: The 36,000+ 'listings' in database")
    print("   - Most are just valuation requests or leads")
    print("   - Never became actual listings")
    print("   - Would dilute the analysis quality")
    
    # Create the download script
    create_download_script()