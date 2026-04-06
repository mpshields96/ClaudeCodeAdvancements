#!/usr/bin/env python3
"""
confidence_calibrator.py — Verbal confidence calibration for LLM outputs.

Methodology adapted from ConfTuner (Li et al., 2025, arXiv):
"Training Large Language Models to Express Their Confidence Verbally"

Key insight: LLMs express confidence verbally but are poorly calibrated.
ConfTuner fine-tunes models to align verbal confidence with actual accuracy.
Since we can't fine-tune Claude, we adapt the methodology:
1. Extract confidence from LLM responses (verbal -> numeric)
2. Log predictions with confidence levels
3. Track outcomes and compute calibration metrics (ECE)
4. Adjust future confidence based on historical accuracy per source

This enables calibrated confidence scores on senior dev reviews,
paper scoring, and any other LLM-powered analysis.

CLI:
    python3 confidence_calibrator.py extract "I am 85% confident..."
    python3 confidence_calibrator.py metrics [log_path]
    python3 confidence_calibrator.py adjust <source> <raw_confidence> [log_path]

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path


# === Confidence Extraction ===

# Patterns ordered by specificity (most specific first)
_PERCENT_PATTERN = re.compile(r"(\d{1,3})\s*%\s*confident", re.IGNORECASE)
_CONFIDENCE_PERCENT = re.compile(r"[Cc]onfidence[:\s]+(\d{1,3})\s*%")
_CONFIDENCE_DECIMAL = re.compile(r"[Cc]onfidence[:\s]+(0\.\d+)")
_CONFIDENCE_FRACTION = re.compile(r"[Cc]onfidence[:\s]+(\d+)\s*/\s*(\d+)")
_CONFIDENCE_OUT_OF = re.compile(r"[Cc]onfidence\s+level[:\s]+(\d+)\s+out\s+of\s+(\d+)")
_CONFIDENCE_LABEL = re.compile(
    r"\[?\s*[Cc]onfidence[:\s]*(HIGH|MEDIUM|MODERATE|LOW|VERY\s*HIGH|VERY\s*LOW)\s*\]?",
    re.IGNORECASE,
)

_VERBAL_HIGH = re.compile(r"\b(highly\s+confident|very\s+confident|strong\s+confidence)\b", re.IGNORECASE)
_VERBAL_MODERATE = re.compile(r"\b(moderately\s+confident|moderate\s+confidence|somewhat\s+confident)\b", re.IGNORECASE)
_VERBAL_LOW = re.compile(r"\b(low\s+confidence|not\s+very\s+confident|uncertain|unsure)\b", re.IGNORECASE)

_LABEL_MAP = {
    "very high": 0.95,
    "high": 0.85,
    "moderate": 0.55,
    "medium": 0.55,
    "low": 0.30,
    "very low": 0.15,
}


def extract_confidence(text: str) -> float | None:
    """Extract a confidence score (0.0-1.0) from LLM text output.

    Supports multiple formats:
    - "85% confident" -> 0.85
    - "Confidence: 7/10" -> 0.70
    - "Confidence: 0.92" -> 0.92
    - "[Confidence: HIGH]" -> 0.85
    - "highly confident" -> 0.85
    - "moderately confident" -> 0.55
    - "low confidence" -> 0.30

    Returns None if no confidence signal found.
    """
    # Try percentage: "85% confident"
    m = _PERCENT_PATTERN.search(text)
    if m:
        return min(int(m.group(1)) / 100.0, 1.0)

    # Try "Confidence: 85%"
    m = _CONFIDENCE_PERCENT.search(text)
    if m:
        return min(int(m.group(1)) / 100.0, 1.0)

    # Try "Confidence: 0.92"
    m = _CONFIDENCE_DECIMAL.search(text)
    if m:
        return float(m.group(1))

    # Try "Confidence: 7/10"
    m = _CONFIDENCE_FRACTION.search(text)
    if m:
        num, denom = int(m.group(1)), int(m.group(2))
        if denom > 0:
            return min(num / denom, 1.0)

    # Try "Confidence level: 65 out of 100"
    m = _CONFIDENCE_OUT_OF.search(text)
    if m:
        num, denom = int(m.group(1)), int(m.group(2))
        if denom > 0:
            return min(num / denom, 1.0)

    # Try label: "[Confidence: HIGH]"
    m = _CONFIDENCE_LABEL.search(text)
    if m:
        label = m.group(1).lower().strip()
        return _LABEL_MAP.get(label, 0.55)

    # Try verbal: "highly confident", "moderately confident", "low confidence"
    if _VERBAL_HIGH.search(text):
        return 0.85
    if _VERBAL_MODERATE.search(text):
        return 0.55
    if _VERBAL_LOW.search(text):
        return 0.30

    return None


# === Prediction Logging ===

def _generate_prediction_id() -> str:
    """Generate a unique prediction ID."""
    ts = int(time.time() * 1000)
    rand = os.urandom(4).hex()
    return f"pred_{ts}_{rand}"


class PredictionLog:
    """Log predictions with confidence for calibration tracking.

    Each prediction is a JSONL entry with:
    - prediction_id, source, prediction, confidence, timestamp, context
    Outcomes are logged as separate entries linked by prediction_id.
    """

    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self._known_ids: set[str] = set()
        self._load_known_ids()

    def _load_known_ids(self):
        """Load known prediction IDs from existing log."""
        if self.log_path.exists():
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            pid = entry.get("prediction_id")
                            if pid:
                                self._known_ids.add(pid)
                        except json.JSONDecodeError:
                            continue

    def log_prediction(
        self,
        source: str,
        prediction: str,
        confidence: float,
        context: dict | None = None,
    ) -> str:
        """Log a prediction with confidence score. Returns prediction_id."""
        pid = _generate_prediction_id()
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

        entry = {
            "type": "prediction",
            "prediction_id": pid,
            "source": source,
            "prediction": prediction,
            "confidence": confidence,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if context:
            entry["context"] = context

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        self._known_ids.add(pid)
        return pid

    def record_outcome(
        self,
        prediction_id: str,
        correct: bool,
        notes: str = "",
    ):
        """Record the outcome of a prediction for calibration."""
        if prediction_id not in self._known_ids:
            raise ValueError(f"Unknown prediction_id: {prediction_id}")

        entry = {
            "type": "outcome",
            "prediction_id": prediction_id,
            "correct": correct,
            "notes": notes,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


# === Calibration Metrics ===

class CalibrationMetrics:
    """Compute Expected Calibration Error (ECE) and related metrics.

    ECE measures the gap between confidence and accuracy across bins.
    A perfectly calibrated model has ECE = 0: when it says 80% confident,
    it's correct 80% of the time.
    """

    def __init__(self, log_path: Path, n_bins: int = 10):
        self.log_path = Path(log_path)
        self.n_bins = n_bins

    def _load_paired_data(self, source: str | None = None) -> list[tuple[float, bool]]:
        """Load (confidence, correct) pairs from log."""
        predictions = {}
        outcomes = {}

        if not self.log_path.exists():
            return []

        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") == "prediction":
                    pid = entry["prediction_id"]
                    if source is None or entry.get("source") == source:
                        predictions[pid] = entry["confidence"]
                elif entry.get("type") == "outcome":
                    pid = entry["prediction_id"]
                    outcomes[pid] = entry["correct"]

        # Pair predictions with outcomes
        paired = []
        for pid, conf in predictions.items():
            if pid in outcomes:
                paired.append((conf, outcomes[pid]))

        return paired

    def compute(self, source: str | None = None) -> dict:
        """Compute calibration metrics.

        Returns dict with:
        - ece: Expected Calibration Error (0 = perfect, 1 = worst)
        - bias: "overconfident", "underconfident", or "calibrated"
        - total_predictions: count of paired predictions
        - accuracy: overall accuracy
        - avg_confidence: mean confidence
        - bins: list of bin data
        """
        paired = self._load_paired_data(source)

        if not paired:
            return {"total_predictions": 0, "ece": 0, "bias": "unknown"}

        total = len(paired)
        overall_correct = sum(1 for _, c in paired if c)
        accuracy = overall_correct / total
        avg_confidence = sum(conf for conf, _ in paired) / total

        # Bin-based ECE
        bin_width = 1.0 / self.n_bins
        bins = []
        weighted_error = 0.0

        for i in range(self.n_bins):
            lo = i * bin_width
            hi = (i + 1) * bin_width
            bin_items = [(conf, correct) for conf, correct in paired if lo <= conf < hi]

            if not bin_items:
                continue

            bin_conf = sum(c for c, _ in bin_items) / len(bin_items)
            bin_acc = sum(1 for _, c in bin_items if c) / len(bin_items)
            bin_error = abs(bin_conf - bin_acc)
            weight = len(bin_items) / total

            bins.append({
                "range": f"{lo:.1f}-{hi:.1f}",
                "count": len(bin_items),
                "avg_confidence": round(bin_conf, 3),
                "accuracy": round(bin_acc, 3),
                "error": round(bin_error, 3),
            })

            weighted_error += weight * bin_error

        # Determine bias
        if avg_confidence - accuracy > 0.05:
            bias = "overconfident"
        elif accuracy - avg_confidence > 0.05:
            bias = "underconfident"
        else:
            bias = "calibrated"

        return {
            "total_predictions": total,
            "ece": round(weighted_error, 4),
            "bias": bias,
            "accuracy": round(accuracy, 4),
            "avg_confidence": round(avg_confidence, 4),
            "bins": bins,
        }

    def compute_by_source(self) -> dict[str, dict]:
        """Compute calibration metrics broken down by source."""
        # First, collect all sources
        sources = set()
        if self.log_path.exists():
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            if entry.get("type") == "prediction":
                                sources.add(entry.get("source", "unknown"))
                        except json.JSONDecodeError:
                            continue

        return {source: self.compute(source=source) for source in sources}


# === Confidence Adjuster ===

class ConfidenceAdjuster:
    """Adjust raw confidence scores based on historical calibration.

    Uses a simple linear correction: if a source says 90% but is only
    50% accurate at that confidence level, future 90% predictions get
    adjusted downward.
    """

    def __init__(self, log_path: Path, min_samples: int = 5):
        self.log_path = Path(log_path)
        self.min_samples = min_samples
        self._metrics = CalibrationMetrics(log_path)

    def adjust(self, source: str, raw_confidence: float) -> float:
        """Adjust a confidence score based on historical calibration.

        If insufficient data for the source, returns raw_confidence unchanged.
        """
        paired = self._metrics._load_paired_data(source=source)

        if len(paired) < self.min_samples:
            return raw_confidence

        # Simple calibration: compute actual accuracy for this confidence range
        # Use a window around the raw confidence
        window = 0.15
        lo = max(0, raw_confidence - window)
        hi = min(1, raw_confidence + window)

        nearby = [(conf, correct) for conf, correct in paired if lo <= conf <= hi]

        if len(nearby) < 3:
            # Not enough data in this confidence range, use global correction
            avg_conf = sum(c for c, _ in paired) / len(paired)
            avg_acc = sum(1 for _, c in paired if c) / len(paired)
            if avg_conf > 0:
                correction_ratio = avg_acc / avg_conf
                return max(0.0, min(1.0, raw_confidence * correction_ratio))
            return raw_confidence

        actual_acc = sum(1 for _, c in nearby if c) / len(nearby)
        avg_stated = sum(c for c, _ in nearby) / len(nearby)

        if avg_stated > 0:
            correction_ratio = actual_acc / avg_stated
            adjusted = raw_confidence * correction_ratio
            return max(0.0, min(1.0, round(adjusted, 4)))

        return raw_confidence


# === CLI ===

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: confidence_calibrator.py [extract|metrics|adjust] [args]")
        print("  extract <text>     — Extract confidence from text")
        print("  metrics [path]     — Compute calibration metrics")
        print("  adjust <src> <raw> — Adjust confidence for source")
        sys.exit(1)

    cmd = args[0]

    if cmd == "extract":
        if len(args) < 2:
            print("Usage: extract <text>")
            sys.exit(1)
        text = " ".join(args[1:])
        conf = extract_confidence(text)
        if conf is not None:
            print(f"Confidence: {conf:.2f} ({conf * 100:.0f}%)")
        else:
            print("No confidence signal found.")

    elif cmd == "metrics":
        log_path = Path(args[1]) if len(args) > 1 else Path(".cca-confidence-log.jsonl")
        if not log_path.exists():
            print(f"No log file at {log_path}")
            sys.exit(1)
        metrics = CalibrationMetrics(log_path)
        result = metrics.compute()
        print(f"Calibration Metrics ({result['total_predictions']} predictions):")
        print(f"  ECE: {result['ece']:.4f}")
        print(f"  Bias: {result['bias']}")
        print(f"  Accuracy: {result.get('accuracy', 'N/A')}")
        print(f"  Avg confidence: {result.get('avg_confidence', 'N/A')}")

        by_source = metrics.compute_by_source()
        if by_source:
            print("\nBy source:")
            for src, data in by_source.items():
                print(f"  {src}: ECE={data['ece']:.4f}, bias={data['bias']}, n={data['total_predictions']}")

    elif cmd == "adjust":
        if len(args) < 3:
            print("Usage: adjust <source> <raw_confidence> [log_path]")
            sys.exit(1)
        source = args[1]
        raw = float(args[2])
        log_path = Path(args[3]) if len(args) > 3 else Path(".cca-confidence-log.jsonl")
        adjuster = ConfidenceAdjuster(log_path)
        adjusted = adjuster.adjust(source, raw)
        print(f"Raw: {raw:.2f} -> Adjusted: {adjusted:.2f}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
