"""
الثاقب — Althaqeb: Basic Scan Example

Demonstrates how to run an injection scan programmatically.
Replace the URL with your target AI API endpoint.
"""

from althaqeb.core.engine import Engine

engine = Engine(verbose=True)

# Profile the target first
print("Profiling target...")
profile = engine.profile_target("http://localhost:8000", api_key="your-api-key")
print(f"  Reachable:  {profile['reachable']}")
print(f"  API Type:   {profile['api_type']}")
print(f"  Model:      {profile['model_name']}")

# Run a prompt injection scan
print("\nRunning injection module...")
session = engine.run_scan(
    "http://localhost:8000",
    module="injection",
    api_key="your-api-key",
)

print(f"\nScan complete — {len(session.findings)} findings")
for f in session.findings:
    print(f"  [{f['severity']:8s}] {f['technique']}: {f['aivss_score']:.1f}")
