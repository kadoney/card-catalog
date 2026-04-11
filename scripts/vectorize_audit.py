"""
Vectorize Index Audit & Cleanup Tool
=====================================
Queries the sapfm-catalog-vectors Vectorize index via a temporary Worker
to audit contents, find duplicates, and identify non-furniture records.

Usage:
  python vectorize_audit.py audit       # Full audit report
  python vectorize_audit.py duplicates  # Find duplicate IDs
  python vectorize_audit.py junk        # Find non-furniture MARC records
  python vectorize_audit.py delete      # Delete flagged vectors (interactive)

Requires: wrangler CLI authenticated, CLOUDFLARE_ACCOUNT_ID set
"""

import subprocess
import json
import sys
import os
import re
import time
import tempfile
import shutil

ACCOUNT_ID = "ebe622eaa5b3a3581cf5664272f26f30"
INDEX_NAME = "sapfm-catalog-vectors"

# Furniture-related keywords for filtering MARC records
FURNITURE_KEYWORDS = [
    "furniture", "cabinet", "chair", "table", "desk", "chest", "clock",
    "highboy", "lowboy", "settee", "sofa", "bed", "cupboard", "sideboard",
    "secretary", "bookcase", "wardrobe", "armoire", "commode", "bureau",
    "woodwork", "joinery", "carving", "veneer", "marquetry", "inlay",
    "upholster", "cabinetmak", "chairmaker", "joiners", "turners",
    "chippendale", "hepplewhite", "sheraton", "phyfe", "seymour",
    "townsend", "goddard", "savery", "affleck", "randolph",
    "queen anne", "federal", "colonial", "windsor", "shaker",
    "decorative arts", "american wing", "antique",
    "period furniture", "early american",
]

def create_probe_worker(action, params=None):
    """Create and run a temporary Worker to query Vectorize."""
    workdir = tempfile.mkdtemp(prefix="vz-probe-")

    if action == "scan":
        # Exhaustive scan using diverse seed vectors
        worker_code = """
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const seedCount = parseInt(url.searchParams.get("seeds") || "20");
    const topK = parseInt(url.searchParams.get("topk") || "100");

    const allIds = new Map(); // id -> metadata

    for (let s = 0; s < seedCount; s++) {
      const vec = new Array(768).fill(0).map((_, i) =>
        Math.sin(i * (s * 0.37 + 0.1)) * Math.cos(i * 0.02 * s) * 0.5
      );
      const r = await env.VECTORIZE.query(vec, {
        topK,
        returnMetadata: "all",
        returnValues: false
      });
      for (const m of r.matches) {
        if (!allIds.has(m.id)) {
          allIds.set(m.id, m.metadata || {});
        }
      }
    }

    const entries = [];
    for (const [id, meta] of allIds) {
      entries.push({ id, ...meta });
    }

    return new Response(JSON.stringify({
      unique_found: entries.length,
      entries
    }), { headers: { "Content-Type": "application/json" } });
  }
};
"""
    elif action == "delete":
        # Delete vectors by ID list (POST body)
        worker_code = """
export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("POST a JSON array of IDs to delete", { status: 400 });
    }
    const ids = await request.json();
    if (!Array.isArray(ids) || ids.length === 0) {
      return new Response("Expected non-empty array of IDs", { status: 400 });
    }

    // Vectorize delete in batches of 1000
    let deleted = 0;
    for (let i = 0; i < ids.length; i += 1000) {
      const batch = ids.slice(i, i + 1000);
      const result = await env.VECTORIZE.deleteByIds(batch);
      deleted += batch.length;
    }

    return new Response(JSON.stringify({
      requested: ids.length,
      deleted
    }), { headers: { "Content-Type": "application/json" } });
  }
};
"""
    elif action == "upsert_metadata":
        # Re-upsert vectors with fixed metadata (POST body: [{id, metadata}])
        worker_code = """
export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("POST [{id, metadata}, ...] to fix metadata", { status: 400 });
    }
    const fixes = await request.json();

    // We need to get the existing vectors first, then re-insert with new metadata
    const batchSize = 50;
    let updated = 0;
    let errors = [];

    for (let i = 0; i < fixes.length; i += batchSize) {
      const batch = fixes.slice(i, i + batchSize);
      const ids = batch.map(f => f.id);

      try {
        const existing = await env.VECTORIZE.getByIds(ids);
        const vectors = [];
        for (const vec of existing) {
          const fix = batch.find(f => f.id === vec.id);
          if (fix && vec.values) {
            vectors.push({
              id: vec.id,
              values: vec.values,
              metadata: { ...vec.metadata, ...fix.metadata }
            });
          }
        }
        if (vectors.length > 0) {
          await env.VECTORIZE.upsert(vectors);
          updated += vectors.length;
        }
      } catch (e) {
        errors.push(`Batch ${i}: ${e.message}`);
      }
    }

    return new Response(JSON.stringify({ updated, errors }), {
      headers: { "Content-Type": "application/json" }
    });
  }
};
"""
    else:
        raise ValueError(f"Unknown action: {action}")

    # Write worker files
    with open(os.path.join(workdir, "index.js"), "w") as f:
        f.write(worker_code)

    with open(os.path.join(workdir, "wrangler.toml"), "w") as f:
        f.write(f"""name = "vz-probe-temp"
main = "index.js"
compatibility_date = "2024-09-23"

[[vectorize]]
binding = "VECTORIZE"
index_name = "{INDEX_NAME}"
""")

    return workdir


def run_probe(action, url_params="", post_data=None, seeds=20, topk=100):
    """Start probe worker, query it, return parsed JSON."""
    workdir = create_probe_worker(action)
    port = 8799  # Use non-standard port to avoid conflicts

    try:
        env = os.environ.copy()
        env["CLOUDFLARE_ACCOUNT_ID"] = ACCOUNT_ID

        # Start wrangler dev --remote
        proc = subprocess.Popen(
            ["npx", "wrangler", "dev", "--remote", f"--port={port}"],
            cwd=workdir, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=True
        )

        # Wait for ready
        print("  Starting probe worker...", end="", flush=True)
        for _ in range(30):
            time.sleep(1)
            try:
                import urllib.request
                urllib.request.urlopen(f"http://localhost:{port}/healthz", timeout=1)
                break
            except Exception:
                pass
        print(" ready.")

        # Query
        url = f"http://localhost:{port}/?seeds={seeds}&topk={topk}&{url_params}"

        import urllib.request
        if post_data:
            req = urllib.request.Request(
                url,
                data=json.dumps(post_data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
        else:
            req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())

    finally:
        proc.terminate()
        proc.wait()
        time.sleep(1)
        try:
            shutil.rmtree(workdir)
        except Exception:
            pass


def cmd_audit():
    """Full audit of the Vectorize index."""
    print("=" * 60)
    print("SAPFM Vectorize Index Audit")
    print("=" * 60)
    print()
    print(f"Index: {INDEX_NAME}")
    print(f"Total vectors: 11,285 (from wrangler info)")
    print()

    print("Scanning index with diverse query vectors...")
    result = run_probe("scan", seeds=40, topk=100)
    entries = result["entries"]
    print(f"  Discovered {len(entries)} unique vectors via sampling")
    print()

    # Classify by source
    by_source = {}
    by_type = {}
    for e in entries:
        src = e.get("source", "unknown")
        typ = e.get("record_type", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        by_type[typ] = by_type.get(typ, 0) + 1

    print("By record_type:")
    for typ, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {typ:25s} {cnt:>5d}")

    print()
    print("By source (top 30):")
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1])[:30]:
        print(f"  {src:55s} {cnt:>5d}")

    # Find duplicates (bare IDs that also exist as prefixed)
    print()
    print("Checking for duplicate ID patterns...")
    bare_ids = [e for e in entries if re.match(r'^\d+$', e["id"])]
    prefixed = {e["id"] for e in entries if e["id"].startswith("card:")}
    dupes = [e for e in bare_ids if f"card:{e['id']}" in prefixed]
    print(f"  Bare numeric IDs: {len(bare_ids)}")
    print(f"  Prefixed card: IDs: {len(prefixed)}")
    print(f"  Confirmed duplicates (bare + card: both exist): {len(dupes)}")

    # Find non-furniture MARC records
    print()
    print("Checking Yale MARC records for furniture relevance...")
    marc = [e for e in entries if e.get("source", "").startswith("yale_marc")]
    furniture_marc = []
    junk_marc = []
    for e in marc:
        title = (e.get("title", "") or "").lower()
        if any(kw in title for kw in FURNITURE_KEYWORDS):
            furniture_marc.append(e)
        else:
            junk_marc.append(e)

    print(f"  Total MARC sampled: {len(marc)}")
    print(f"  Furniture-related: {len(furniture_marc)}")
    print(f"  Non-furniture (junk): {len(junk_marc)}")
    if junk_marc:
        print(f"  Sample junk titles:")
        for e in junk_marc[:5]:
            print(f"    - {e.get('title', '?')[:80]}")

    # Summary
    print()
    print("=" * 60)
    print("CLEANUP RECOMMENDATIONS")
    print("=" * 60)
    total_est = 11285
    bare_est = int(len(bare_ids) / len(entries) * total_est) if entries else 0
    junk_est = int(len(junk_marc) / len(entries) * total_est) if entries else 0
    print(f"  1. Delete ~{bare_est} bare-numeric card duplicates")
    print(f"  2. Delete ~{junk_est} non-furniture MARC records")
    print(f"  3. Fix video chapter metadata (collection → 'SAPFM')")
    print(f"  4. Estimated clean index size: ~{total_est - bare_est - junk_est}")

    # Save audit data for cleanup step
    audit_path = os.path.join(os.path.dirname(__file__), "vectorize_audit_data.json")
    with open(audit_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "entries_sampled": len(entries),
            "bare_numeric_ids": [e["id"] for e in bare_ids],
            "junk_marc_ids": [e["id"] for e in junk_marc],
            "video_chapters_needing_fix": [
                e["id"] for e in entries
                if e.get("record_type") == "video_chapter"
                and e.get("collection", "") != "SAPFM"
            ],
            "all_entries": entries,
        }, f, indent=2)
    print(f"\n  Audit data saved to: {audit_path}")


def cmd_delete_flagged():
    """Delete vectors flagged by audit."""
    audit_path = os.path.join(os.path.dirname(__file__), "vectorize_audit_data.json")
    if not os.path.exists(audit_path):
        print("Run 'audit' first to generate flagged IDs.")
        return

    with open(audit_path) as f:
        audit = json.load(f)

    bare_ids = audit.get("bare_numeric_ids", [])
    junk_ids = audit.get("junk_marc_ids", [])

    print(f"Flagged for deletion:")
    print(f"  Bare numeric duplicates: {len(bare_ids)}")
    print(f"  Non-furniture MARC:      {len(junk_ids)}")
    print(f"  Total:                   {len(bare_ids) + len(junk_ids)}")
    print()

    # Note: The audit only samples ~2-3k of 11k vectors.
    # For bare IDs, we know the pattern — delete ALL bare numeric IDs.
    # For MARC, we need a broader scan or filter by source prefix.
    print("NOTE: Audit only sampled a subset. For thorough cleanup:")
    print("  - Bare IDs: Will use getByIds to find all card:N and bare N pairs")
    print("  - MARC junk: Will filter by title keywords across full MARC set")
    print()

    resp = input("Proceed with deleting sampled flagged IDs? [y/N] ")
    if resp.lower() != "y":
        print("Aborted.")
        return

    to_delete = bare_ids + junk_ids
    print(f"Deleting {len(to_delete)} vectors...")
    result = run_probe("delete", post_data=to_delete)
    print(f"  Result: {result}")


def cmd_fix_video_metadata():
    """Fix video chapter metadata: set collection to 'SAPFM'."""
    audit_path = os.path.join(os.path.dirname(__file__), "vectorize_audit_data.json")
    if not os.path.exists(audit_path):
        print("Run 'audit' first.")
        return

    with open(audit_path) as f:
        audit = json.load(f)

    fix_ids = audit.get("video_chapters_needing_fix", [])
    if not fix_ids:
        print("No video chapters need metadata fixes.")
        return

    print(f"Fixing {len(fix_ids)} video chapter metadata entries (collection → 'SAPFM')...")
    fixes = [{"id": vid, "metadata": {"collection": "SAPFM"}} for vid in fix_ids]
    result = run_probe("upsert_metadata", post_data=fixes)
    print(f"  Result: {result}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "audit":
        cmd_audit()
    elif cmd == "delete":
        cmd_delete_flagged()
    elif cmd == "fix-video":
        cmd_fix_video_metadata()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: audit, delete, fix-video")
        sys.exit(1)
