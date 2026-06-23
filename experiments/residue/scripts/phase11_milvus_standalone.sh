#!/usr/bin/env bash
# Phase 11: REAL Milvus standalone (etcd + MinIO + Milvus). milvus-lite's compact() was a
# no-op; this tests whether real segment-merge compaction + GC purge deleted vectors from
# the MinIO object store (where the segment binlogs live).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NET=milvus-net
MINIO_DATA="$ROOT/db/milvus_minio"
D="sudo -n docker"

echo "[*] cleanup any prior run"
$D rm -f milvus-standalone milvus-minio milvus-etcd >/dev/null 2>&1
$D network rm $NET >/dev/null 2>&1
$D network create $NET >/dev/null 2>&1
sudo -n rm -rf "$MINIO_DATA" "$ROOT/db/milvus_etcd"; mkdir -p "$MINIO_DATA"; sudo -n chmod 777 "$MINIO_DATA"

echo "[*] start etcd"
$D run -d --name milvus-etcd --network $NET \
  quay.io/coreos/etcd:v3.5.16 etcd -advertise-client-urls=http://127.0.0.1:2379 \
  -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd >/dev/null

echo "[*] start minio (data mounted to host for forensic scan)"
$D run -d --name milvus-minio --network $NET \
  -e MINIO_ACCESS_KEY=minioadmin -e MINIO_SECRET_KEY=minioadmin \
  -v "$MINIO_DATA":/data minio/minio:RELEASE.2024-05-28T17-19-04Z server /data >/dev/null

echo "[*] start milvus standalone (aggressive GC so purge is observable)"
$D run -d --name milvus-standalone --network $NET -p 19530:19530 -p 9091:9091 \
  -e ETCD_ENDPOINTS=milvus-etcd:2379 -e MINIO_ADDRESS=milvus-minio:9000 \
  -e DATACOORD_GC_INTERVAL=30 -e DATACOORD_GC_MISSINGTOLERANCE=30 -e DATACOORD_GC_DROPTOLERANCE=30 \
  -e COMMON_STORAGETYPE=minio \
  milvusdb/milvus:v2.5.10 milvus run standalone >/dev/null

echo "[*] waiting for milvus health..."
for i in $(seq 1 120); do
  if curl -sf http://localhost:9091/healthz >/dev/null 2>&1; then echo "   healthy after ${i}s"; break; fi
  sleep 1
done
curl -sf http://localhost:9091/healthz >/dev/null 2>&1 || { echo "milvus NOT healthy"; $D logs milvus-standalone 2>&1 | tail -15; exit 1; }
sleep 5

INNER="${1:-$ROOT/scripts/phase11_milvus_scan.py}"
echo "[*] inner script: $INNER"
"$ROOT/.venv/bin/python" -u "$INNER"
RC=$?

echo "[*] cleanup containers"
$D rm -f milvus-standalone milvus-minio milvus-etcd >/dev/null 2>&1
$D network rm $NET >/dev/null 2>&1
exit $RC
