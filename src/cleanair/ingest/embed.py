"""Embed chunks with BGE-M3 (dense + sparse) -> data/processed/embeddings/<collection>/.

BGE-M3 in ~30 lines of plain transformers (no FlagEmbedding), so every step is visible:
- dense  = L2-normalised [CLS] hidden state (1024-d)
- sparse = relu(sparse_linear(hidden state)) per token; one weight per vocabulary id (max over repeats),
           special tokens dropped -- a learned, multilingual stand-in for BM25 term weights
Output: dense.npy (float16), sparse.jsonl ([[ids], [weights]] per chunk), ids.json, meta.json.
Runs anywhere: the KSS H100 (cluster/job_embed.sh), the laptop 4060, or CPU (slow).

Run: uv run python -m cleanair.ingest.embed --chunks data/processed/chunks/fixed-500-50.jsonl
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModel, AutoTokenizer


class BGEM3:
    def __init__(self, model_name: str = "BAAI/bge-m3", max_length: int = 1024, device: str | None = None):
        if "bge-m3" not in model_name.lower():
            raise NotImplementedError(f"only BGE-M3 is wired up so far (A6 adds e5), got {model_name}")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name, dtype=dtype).to(self.device).eval()
        self.sparse_linear = torch.nn.Linear(self.model.config.hidden_size, 1)
        sparse_path = Path(hf_hub_download(model_name, "sparse_linear.pt"))
        self.sparse_linear.load_state_dict(torch.load(sparse_path, map_location="cpu"))
        self.sparse_linear.to(self.device, dtype)
        self.max_length = max_length
        self.special_ids = set(self.tok.all_special_ids)
        self.revision = sparse_path.parent.name  # HF cache: .../snapshots/<commit sha>/sparse_linear.pt
        self.truncated = 0

    @torch.inference_mode()
    def encode(self, texts: list[str], batch_size: int = 32) -> tuple[np.ndarray, list[dict[int, float]]]:
        """Returns (dense [n, 1024] float32, sparse [{token_id: weight}]) in input order."""
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]), reverse=True)  # similar lengths batch well
        dense = np.zeros((len(texts), self.model.config.hidden_size), dtype=np.float32)
        sparse: list[dict[int, float]] = [{} for _ in texts]
        for s in range(0, len(order), batch_size):
            idx = order[s : s + batch_size]
            enc = self.tok(
                [texts[i] for i in idx],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)
            self.truncated += int((enc["attention_mask"].sum(1) == self.max_length).sum())
            hidden = self.model(**enc).last_hidden_state
            cls = torch.nn.functional.normalize(hidden[:, 0].float(), dim=-1)
            weights = torch.relu(self.sparse_linear(hidden)).squeeze(-1).float()
            for row, i in enumerate(idx):
                dense[i] = cls[row].cpu().numpy()
                vec: dict[int, float] = {}
                for tid, w in zip(enc["input_ids"][row].tolist(), weights[row].tolist(), strict=True):
                    if w > 0 and tid not in self.special_ids:
                        vec[tid] = max(vec.get(tid, 0.0), w)
                sparse[i] = vec
        return dense, sparse


def save(out_dir: Path, ids: list[str], dense: np.ndarray, sparse: list[dict[int, float]], meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "dense.npy", dense.astype(np.float16))
    with open(out_dir / "sparse.jsonl", "w", encoding="utf-8") as f:
        for vec in sparse:
            f.write(json.dumps([list(vec), [round(w, 4) for w in vec.values()]]) + "\n")
    (out_dir / "ids.json").write_text(json.dumps(ids), encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def load(emb_dir: Path) -> tuple[list[str], np.ndarray, list[dict[int, float]], dict]:
    ids = json.loads((emb_dir / "ids.json").read_text(encoding="utf-8"))
    dense = np.load(emb_dir / "dense.npy").astype(np.float32)
    sparse = []
    for line in (emb_dir / "sparse.jsonl").read_text(encoding="utf-8").splitlines():
        keys, values = json.loads(line)
        sparse.append(dict(zip(keys, values, strict=True)))
    return ids, dense, sparse, json.loads((emb_dir / "meta.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Embed a chunk set with BGE-M3 (dense + sparse).")
    p.add_argument("--chunks", type=Path, required=True)
    p.add_argument("--model", default="BAAI/bge-m3")
    p.add_argument("--max-length", type=int, default=1024)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--out-root", type=Path, default=Path("data/processed/embeddings"))
    args = p.parse_args(argv)

    chunks = [json.loads(line) for line in args.chunks.read_text(encoding="utf-8").splitlines()]
    collection = f"{args.chunks.stem}__{args.model.split('/')[-1].lower()}"
    t0 = time.time()
    emb = BGEM3(args.model, args.max_length)
    print(f"device={emb.device} model={args.model}@{emb.revision} chunks={len(chunks)}", flush=True)
    dense, sparse = emb.encode([c["embed_text"] for c in chunks], args.batch_size)
    meta = {
        "model": args.model,
        "revision": emb.revision,
        "max_length": args.max_length,
        "n": len(chunks),
        "truncated": emb.truncated,
        "device": emb.device,
        "seconds": round(time.time() - t0, 1),
        "chunks_file": args.chunks.name,
    }
    save(args.out_root / collection, [c["chunk_id"] for c in chunks], dense, sparse, meta)
    print(json.dumps(meta), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
