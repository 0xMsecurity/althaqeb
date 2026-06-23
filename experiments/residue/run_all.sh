#!/usr/bin/env bash
# One-command, tiered reproduction of the vector-DB deletion-residue study.
# Deterministic (fixed seeds), offline after first model download, CPU-only.
#
# Tiers (run only what your environment supports):
#   ./run_all.sh cpu       phases needing only python (chroma/faiss/qdrant-local/milvus-lite)
#   ./run_all.sh postgres  + phase4/phase8 (needs PG18 binaries + built pgvector)
#   ./run_all.sh docker    + phase9/10/11/12 (needs `sudo docker`)
#   ./run_all.sh all       everything available
#   ./run_all.sh verify    just check the artifact manifest
#
# Env: ./.venv/bin/python (see requirements.lock.txt). HF models cached in hf_cache/.
set -u
cd "$(dirname "$0")"
PY="./.venv/bin/python"
export HF_HOME="$PWD/hf_cache" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
mkdir -p logs results
run(){ echo "=== $* ==="; "$@"; }

cpu(){
  run $PY scripts/phase1_chroma_residue_inversion.py 0
  for s in 0 1 2 3 4; do run $PY scripts/phase2_persistence_destruction.py $s; done
  run $PY scripts/phase3_cross_backend.py
  run $PY scripts/phase5_quantization_inversion.py
  run $PY scripts/phase6_blind_deletemark.py
  run $PY scripts/phase7_audit_validation.py
  run $PY scripts/phase12_chroma_highratio_control.py 2>/dev/null || true
}
postgres(){
  run $PY scripts/phase4_postgres_heap.py
  run $PY scripts/phase8_pgvector_hnsw.py
}
docker_tier(){
  run $PY scripts/phase9_qdrant_server.py
  run bash scripts/phase10_weaviate.py 2>/dev/null || run $PY scripts/phase10_weaviate.py
  run bash scripts/phase11_milvus_standalone.sh
  run bash scripts/phase11_milvus_standalone.sh scripts/phase12_milvus_highratio_scan.py
}
case "${1:-cpu}" in
  cpu) cpu;;
  postgres) cpu; postgres;;
  docker) cpu; docker_tier;;
  all) cpu; postgres; docker_tier;;
  verify) bash verify_manifest.sh;;
  *) echo "usage: $0 {cpu|postgres|docker|all|verify}"; exit 1;;
esac
echo "[done] results/ and logs/ updated. Compare against committed results/*.json."
