#!/usr/bin/env python3
"""
Test Google Drive access and explore folder structure to understand how CIMs are stored.
"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def explore_folder(service, folder_id, max_items=10):
    """Explore contents of a folder."""
    try:
        # List all items in the folder
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size)",
            pageSize=max_items
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print("  Empty folder or no access")
            return
        
        print(f"  Found {len(files)} items:")
        for file in files:
            size_str = f" ({int(file.get('size', 0))/1024/1024:.1f} MB)" if file.get('size') else ""
            mime = file['mimeType'].split('.')[-1]
            
            if 'folder' in file['mimeType']:
                print(f"    📁 {file['name']}")
            elif 'pdf' in file['mimeType']:
                print(f"    📄 {file['name']}{size_str}")
            else:
                print(f"    📎 {file['name']} ({mime}){size_str}")
                
        return files
        
    except HttpError as e:
        if e.resp.status == 404:
            print(f"  ❌ Folder not found or no access")
        elif e.resp.status == 403:
            print(f"  ❌ Permission denied")
        else:
            print(f"  ❌ Error: {e}")
        return None

def test_specific_listing(service, listing_id, folder_id):
    """Test access to a specific listing's folder."""
    print(f"\nTesting Listing {listing_id}:")
    print(f"  Folder ID: {folder_id}")
    
    files = explore_folder(service, folder_id)
    
    # If we found subfolders, explore them too
    if files:
        subfolders = [f for f in files if 'folder' in f['mimeType']]
        if subfolders:
            print("\n  Exploring subfolders:")
            for subfolder in subfolders[:3]:  # Limit to first 3
                print(f"\n  Subfolder: {subfolder['name']}")
                explore_folder(service, subfolder['id'], max_items=5)

def main():
    """Test Google Drive access with various folder IDs."""
    
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("ERROR: service_account.json not found!")
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
        print(f"✓ Connected as: {about['user']['emailAddress']}\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return
    
    # Test cases from the failed downloads
    test_cases = [
        # Listing 18658 - sold with 1206 inquiries
        (18658, "1jAqjCiJeHBIZkrDYhlicS95iE50b4h5G"),
        
        # Listing 18211 - has business_summary_folder_id
        (18211, "19J9d6X_pkg0fnfbrXW3K0XSnOfyqOpqx"),
        
        # Listing 22841 - business_summary_folder same as drive link
        (22841, "1GosxqaaMTGx1cp8Ly_HkBzd-A83F2jmv"),
    ]
    
    for listing_id, folder_id in test_cases:
        test_specific_listing(service, listing_id, folder_id)
    
    # Also test if we can search for PDFs across the entire drive
    print("\n" + "="*60)
    print("Testing global search for Business Summary PDFs:")
    
    try:
        # Search for any PDFs with "business summary" in the name
        query = "mimeType='application/pdf' and (name contains 'business summary' or name contains 'Business Summary')"
        results = service.files().list(
            q=query,
            fields="files(id, name, parents)",
            pageSize=10
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            print(f"Found {len(files)} Business Summary PDFs accessible:")
            for file in files[:5]:
                print(f"  - {file['name']}")
                if 'parents' in file:
                    print(f"    Parent folder: {file['parents'][0]}")
        else:
            print("No Business Summary PDFs found or accessible")
            
    except Exception as e:
        print(f"Error searching: {e}")
    
    # Test searching for CIM files
    print("\n" + "="*60)
    print("Testing global search for CIM files:")
    
    try:
        query = "mimeType='application/pdf' and (name contains 'CIM' or name contains 'cim' or name contains 'Confidential')"
        results = service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=10
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            print(f"Found {len(files)} CIM/Confidential PDFs:")
            for file in files[:5]:
                print(f"  - {file['name']}")
        else:
            print("No CIM PDFs found or accessible")
            
    except Exception as e:
        print(f"Error searching: {e}")

if __name__ == "__main__":
    main()