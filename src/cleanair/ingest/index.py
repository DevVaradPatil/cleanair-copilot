"""Load chunks + embeddings into a Qdrant collection named <chunk_set>__<embedder> (blue-green by name).

- named vectors: "dense" (cosine, 1024-d) and "sparse" (BGE-M3 lexical weights)
- payload = the whole chunk record; keyword/bool indexes on the fields filters use
- collection metadata records the embedder model + revision (SPEC §6.1: version the model with the index)
Re-running with an existing, complete collection is a no-op; --recreate rebuilds it.

Run: uv run python -m cleanair.ingest.index --config configs/ablations/naive.yaml
"""

import argparse
import hashlib
import json
import uuid
from pathlib import Path

from qdrant_client import QdrantClient, models

from cleanair.config import load_config
from cleanair.ingest.embed import load
from cleanair.settings import Settings

PAYLOAD_INDEXES = {
    "doc_id": models.PayloadSchemaType.KEYWORD,
    "doc_type": models.PayloadSchemaType.KEYWORD,
    "jurisdiction": models.PayloadSchemaType.KEYWORD,
    "cities": models.PayloadSchemaType.KEYWORD,
    "language": models.PayloadSchemaType.KEYWORD,
    "is_current": models.PayloadSchemaType.BOOL,
}


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))  # stable, so re-upserts overwrite, never duplicate


def build_index(
    client: QdrantClient, collection: str, chunks: list[dict], emb_dir: Path, recreate: bool = False
) -> str:
    ids, dense, sparse, meta = load(emb_dir)
    if ids != [c["chunk_id"] for c in chunks]:
        raise ValueError(f"{emb_dir} was embedded from a different chunk set; re-run embed")
    # Fingerprint of exactly what we'd upload: a re-embed or re-chunk with the same point count must not be skipped.
    fingerprint = hashlib.sha256(
        (emb_dir / "dense.npy").read_bytes() + (emb_dir / "sparse.jsonl").read_bytes()
    ).hexdigest()[:16]
    if client.collection_exists(collection):
        stored = client.get_collection(collection).config.metadata or {}
        if not recreate and stored.get("fingerprint") == fingerprint and client.count(collection).count == len(chunks):
            return "exists"
        client.delete_collection(collection)

    client.create_collection(
        collection,
        vectors_config={"dense": models.VectorParams(size=dense.shape[1], distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
        metadata={
            "embedder": meta["model"],
            "revision": meta["revision"],
            "chunks_file": meta["chunks_file"],
            "fingerprint": fingerprint,
        },
    )
    for field, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(collection, field, schema)
    points = [
        models.PointStruct(
            id=point_id(c["chunk_id"]),
            vector={
                "dense": d.tolist(),
                "sparse": models.SparseVector(indices=list(s), values=list(s.values())),
            },
            payload=c,
        )
        for c, d, s in zip(chunks, dense, sparse, strict=True)
    ]
    client.upload_points(collection, points, batch_size=128, wait=True)
    return "created"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Index a config's chunk set + embeddings into Qdrant.")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--chunks-dir", type=Path, default=Path("data/processed/chunks"))
    p.add_argument("--emb-root", type=Path, default=Path("data/processed/embeddings"))
    p.add_argument("--recreate", action="store_true")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    s = Settings()
    client = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key.get_secret_value() if s.qdrant_api_key else None)
    chunks_file = args.chunks_dir / f"{cfg.chunk_set}.jsonl"
    chunks = [json.loads(line) for line in chunks_file.read_text(encoding="utf-8").splitlines()]
    status = build_index(client, cfg.collection, chunks, args.emb_root / cfg.collection, args.recreate)
    print(f"{cfg.collection}: {status}, {client.count(cfg.collection).count} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
