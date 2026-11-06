import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "harness"), str(ROOT / "submission")]

from knowledge import KnowledgeSystem  # noqa: E402
from run_eval import load_snapshots  # noqa: E402

FINGERPRINTS = Path(__file__).with_name("answer_fingerprints.json")
SNAPSHOTS = ROOT / "snapshots"
SNAPSHOT_ZIPS = ROOT / "snapshots_zip"
EVALS = sorted((ROOT / "eval").glob("*.jsonl"))
RECORD_FLAG = "--record"


def fingerprint(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def fingerprint_of_answer(answer) -> str:
    sources = [(source.url, source.snapshot_id, source.quote) for source in answer.sources]
    return fingerprint(answer.text, answer.confident, answer.conflict_note, sources)


def fingerprint_of_conflict(conflict) -> str:
    sources = [(source.url, source.snapshot_id, source.quote) for source in conflict.sources]
    return fingerprint(conflict.topic, conflict.values, conflict.resolution, conflict.reason, sources)


def current_fingerprints() -> dict[str, str]:
    system = KnowledgeSystem()
    for snapshot in load_snapshots(SNAPSHOTS):
        system.ingest(snapshot)
    found = {"conflicts": fingerprint([fingerprint_of_conflict(conflict) for conflict in system.conflicts()])}
    for eval_file in EVALS:
        for line in eval_file.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            key = f"{item['question']} | {item.get('as_of')}"
            found[key] = fingerprint_of_answer(system.answer(item["question"], item.get("as_of")))
    return found


@unittest.skipUnless(
    any(SNAPSHOTS.glob("*/manifest.json")) or any(SNAPSHOT_ZIPS.glob("*.zip")),
    "needs the snapshot zips, which are not committed",
)
class AnswersStayTheSame(unittest.TestCase):
    def test_every_rules_only_answer_and_conflict_matches_its_recorded_fingerprint(self):
        recorded = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
        current = current_fingerprints()
        changed = [key for key in sorted(recorded.keys() | current.keys()) if recorded.get(key) != current.get(key)]
        self.assertEqual(changed, [])


if __name__ == "__main__" and RECORD_FLAG in sys.argv:
    FINGERPRINTS.write_text(json.dumps(current_fingerprints(), indent=0, sort_keys=True) + "\n", encoding="utf-8")
