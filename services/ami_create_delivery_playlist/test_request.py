#!/usr/bin/env python3
"""Test script to send a request to the ami_create_delivery_playlist service."""

import asyncio
import json
from httpx import AsyncClient

# Test request data
TEST_REQUEST = {
    "user_id": "121",
    "user_login": "pierrer@rvx.is",
    "title": "undefined",
    "entity_type": "Version",
    "server_hostname": "apavatn.shotgrid.autodesk.com",
    "referrer_path": "/detail/HumanUser/121",
    "page_id": "6655",
    "session_uuid": "85c5f926-8c1a-11f1-94bc-0a58a9feac02",
    "project_name": "Zero_Flow",
    "project_id": "353",
    "target_column": "description",
    "ids": "87772",
    "selected_ids": "87772",
    "cols": "image,code,entity,sg_version_type,sg_task,sg_status_list,user,description,created_at",
    "view": "Default",
    "column_display_names": "Thumbnail,Version Name,Link,Product Type,Task,Status,Artist,Submission Note,Date Created",
    "sort_column": "created_at",
    "sort_direction": "desc",
    "timestamp": "2026-07-30T15:20:58Z",
    "signature": "fc69eb0822c92d95ecb5a0967a7d78df31fc85afd724fce5951b38e197627a91"
}


async def test_request(base_url: str = "http://localhost:8082") -> None:
    """Send a test request to the service."""
    async with AsyncClient() as client:
        print(f"Sending request to {base_url}...")
        print(f"Request data:\n{json.dumps(TEST_REQUEST, indent=2)}\n")

        try:
            response = await client.post(f"{base_url}/", data=TEST_REQUEST)
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"\nResponse Body:\n{response.text[:1000]}...")

            if response.status_code == 200:
                print("\n✓ Request successful")
            else:
                print(f"\n✗ Request failed with status {response.status_code}")
        except Exception as e:
            print(f"✗ Error sending request: {e}")


def test_request_sync(base_url: str = "http://localhost:8082") -> None:
    """Synchronous wrapper for test_request."""
    asyncio.run(test_request(base_url))


if __name__ == "__main__":
    import sys

    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8082"
    test_request_sync(base_url)
