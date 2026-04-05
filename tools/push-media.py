#!/usr/bin/env python3
"""Push website media files to GitHub using the Git Data API.

Uses requests library directly (not gh CLI) to handle large blob uploads
reliably without shell encoding issues.
"""
import os
import sys
import json
import base64
import subprocess

REPO = "Pastorsimon1798/cerafica"
WEBSITE_DIR = os.path.join(os.path.dirname(__file__), "..", "website")
API_PREFIX = f"/repos/{REPO}"


def get_token():
    """Get GitHub token from gh CLI."""
    result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("ERROR: Cannot get GitHub token. Run 'gh auth login'", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def api(method, path, data=None, token=None):
    """Make a GitHub API request."""
    import urllib.request
    url = f"https://api.github.com{API_PREFIX}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "push-media.py"
    }

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {error_body[:200]}", file=sys.stderr)
        return None, e.code


def main():
    token = get_token()
    print(f"Token: {token[:8]}...")

    # Get current commit
    print("Getting current ref...")
    ref_data, status = api("GET", "/git/ref/heads/master", token=token)
    if not ref_data:
        print("ERROR getting ref", file=sys.stderr)
        return
    parent_sha = ref_data["object"]["sha"]
    print(f"  Parent: {parent_sha[:12]}")

    # Get current tree
    print("Getting current commit tree...")
    commit_data, status = api("GET", f"/git/commits/{parent_sha}", token=token)
    if not commit_data:
        print("ERROR getting commit", file=sys.stderr)
        return
    base_tree_sha = commit_data["tree"]["sha"]
    print(f"  Base tree: {base_tree_sha[:12]}")

    # Get existing tree entries
    print("Getting existing tree entries...")
    tree_data, status = api("GET", f"/git/trees/{base_tree_sha}?recursive=1", token=token)
    existing = {}
    if tree_data:
        for entry in tree_data.get("tree", []):
            if entry["type"] == "blob":
                existing[entry["path"]] = entry

    # Collect files to upload
    files_to_upload = []
    products_dir = os.path.join(WEBSITE_DIR, "images", "products")

    for filename in sorted(os.listdir(products_dir)):
        filepath = os.path.join(products_dir, filename)
        if not os.path.isfile(filepath):
            continue

        rel_path = f"website/images/products/{filename}"
        size = os.path.getsize(filepath)

        existing_entry = existing.get(rel_path)
        if existing_entry and existing_entry.get("size", 0) == size:
            print(f"  SKIP {filename} ({size} bytes, same size)")
            continue

        files_to_upload.append((rel_path, filepath, size))
        print(f"  UPLOAD {filename} ({size} bytes)")

    if not files_to_upload:
        print("All files up to date!")
        return

    # Upload blobs
    print(f"\nUploading {len(files_to_upload)} blobs...")
    tree_entries = []

    for i, (rel_path, filepath, size) in enumerate(files_to_upload):
        print(f"  [{i+1}/{len(files_to_upload)}] {os.path.basename(filepath)} ({size} bytes)...", end=" ", flush=True)

        with open(filepath, "rb") as f:
            content = f.read()

        b64 = base64.b64encode(content).decode("ascii")
        blob_data, status = api("POST", "/git/blobs", {"content": b64, "encoding": "base64"}, token=token)

        if blob_data and "sha" in blob_data:
            sha = blob_data["sha"]
            tree_entries.append({
                "path": rel_path,
                "mode": "100644",
                "type": "blob",
                "sha": sha
            })
            print(f"OK ({sha[:12]})")
        else:
            print("FAILED")

    if not tree_entries:
        print("No blobs uploaded!")
        return

    # Create tree
    print(f"\nCreating tree with {len(tree_entries)} entries...")
    tree_data, status = api("POST", "/git/trees", {"base_tree": base_tree_sha, "tree": tree_entries}, token=token)
    if not tree_data:
        print("ERROR creating tree", file=sys.stderr)
        return
    new_tree_sha = tree_data["sha"]
    print(f"  Tree: {new_tree_sha[:12]}")

    # Create commit
    print("Creating commit...")
    commit_data, status = api("POST", "/git/commits", {
        "message": "Restore all product media with real files\n\nPhotos restored from inventory/available/ and output/framed/.\nVideos compressed with CRF 28 for web delivery.",
        "parents": [parent_sha],
        "tree": new_tree_sha
    }, token=token)
    if not commit_data:
        print("ERROR creating commit", file=sys.stderr)
        return
    new_commit_sha = commit_data["sha"]
    print(f"  Commit: {new_commit_sha[:12]}")

    # Update ref
    print("Updating ref...")
    ref_data, status = api("PATCH", "/git/refs/heads/master", {"sha": new_commit_sha}, token=token)
    if not ref_data:
        print("ERROR updating ref", file=sys.stderr)
        return

    print(f"\nDone! Commit: {new_commit_sha[:12]}")
    print(f"https://github.com/{REPO}/commit/{new_commit_sha}")


if __name__ == "__main__":
    main()
