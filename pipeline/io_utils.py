"""
IO utilities: reading the input CSVs, resolving image paths on disk,
loading user history / evidence requirements lookups.
"""
import base64
import csv
import mimetypes
import os
from typing import Dict, List, Optional


def read_csv_rows(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: str, rows: List[dict], columns: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def load_user_history(dataset_dir: str) -> Dict[str, dict]:
    """user_id -> history dict. Returns {} if the file isn't present (degraded mode)."""
    path = os.path.join(dataset_dir, "user_history.csv")
    rows = read_csv_rows(path)
    return {r["user_id"]: r for r in rows if r.get("user_id")}


def load_evidence_requirements(dataset_dir: str) -> List[dict]:
    """List of requirement rows. Returns [] if the file isn't present (degraded mode)."""
    path = os.path.join(dataset_dir, "evidence_requirements.csv")
    return read_csv_rows(path)


def find_requirement(requirements: List[dict], claim_object: str, issue_family_hint: str) -> Optional[dict]:
    """
    Best-effort lookup into evidence_requirements.csv.
    Matches claim_object exactly or against the 'all' wildcard row, then prefers a row
    whose applies_to overlaps words with the issue_family_hint (e.g. issue_type or claim text).
    """
    candidates = [r for r in requirements if r.get("claim_object") in (claim_object, "all")]
    if not candidates:
        return None
    hint_words = set(issue_family_hint.lower().replace("_", " ").split())
    best, best_score = None, -1
    for r in candidates:
        applies = r.get("applies_to", "").lower()
        score = sum(1 for w in hint_words if w in applies)
        # Prefer exact object match over "all" wildcard on ties
        if r.get("claim_object") == claim_object:
            score += 0.5
        if score > best_score:
            best, best_score = r, score
    return best


def resolve_image_paths(dataset_dir: str, image_paths_field: str) -> List[dict]:
    """
    Splits the semicolon-separated image_paths field and resolves each against
    dataset_dir. Returns a list of dicts: {id, rel_path, abs_path, exists}.
    """
    out = []
    if not image_paths_field:
        return out
    for rel in image_paths_field.split(";"):
        rel = rel.strip()
        if not rel:
            continue
        img_id = os.path.splitext(os.path.basename(rel))[0]
        abs_path = os.path.join(dataset_dir, rel)
        out.append({
            "id": img_id,
            "rel_path": rel,
            "abs_path": abs_path,
            "exists": os.path.isfile(abs_path),
        })
    return out


def image_to_base64(abs_path: str) -> Optional[dict]:
    """Returns {'media_type':..., 'data':...} for a local image, or None if unreadable."""
    if not os.path.isfile(abs_path):
        return None
    media_type, _ = mimetypes.guess_type(abs_path)
    if media_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        media_type = "image/jpeg"
    with open(abs_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {"media_type": media_type, "data": data}
