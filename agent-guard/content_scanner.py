#!/usr/bin/env python3
"""
content_scanner.py — Hazmat suit for autonomous scanning.

Scans text content, URLs, and repo metadata for threats before Claude
processes or acts on them. This is the safety layer that must pass
before any autonomous scanning (MT-9) reads, evaluates, or builds
from external content.

Nine threat categories (matching MT-9 safety protections):
1. Executable downloads/installs
2. Credential harvesting
3. System modifications
4. Financial threats
5. Outbound data exfiltration
6. Prompt injection
7. Scam signals in repos
8. Low-quality/suspicious repos
9. Malicious URLs

Usage:
    python3 content_scanner.py text "some content to scan"
    python3 content_scanner.py url "https://example.com"
    python3 content_scanner.py repo --stars 5 --age 3 --description "free api"

Stdlib only. No external dependencies.
"""

import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


class ThreatLevel(Enum):
    CLEAN = 0
    SUSPICIOUS = 1
    DANGEROUS = 2
    CRITICAL = 3


@dataclass
class ScanResult:
    has_threats: bool = False
    threat_level: ThreatLevel = ThreatLevel.CLEAN
    threat_types: list = field(default_factory=list)
    details: list = field(default_factory=list)

    def add_threat(self, threat_type: str, description: str, level: ThreatLevel):
        self.has_threats = True
        if threat_type not in self.threat_types:
            self.threat_types.append(threat_type)
        self.details.append({"type": threat_type, "description": description, "level": level.name})
        if level.value > self.threat_level.value:
            self.threat_level = level


# ── Text Content Scanning ────────────────────────────────────────────────────

# Pattern: (regex, threat_type, description, level)
_TEXT_PATTERNS = [
    # --- Executable install/download commands ---
    (r"\bpip\s+install\s+\S+", "executable_install",
     "pip install command — never install packages from external posts", ThreatLevel.CRITICAL),
    (r"\bnpm\s+install\s+(?:-[gG]\s+)?\S+", "executable_install",
     "npm install command — never install packages from external posts", ThreatLevel.CRITICAL),
    (r"\bcargo\s+install\s+\S+", "executable_install",
     "cargo install command — never install packages from external posts", ThreatLevel.CRITICAL),
    (r"\bbrew\s+install\s+\S+", "executable_install",
     "brew install command — never install packages from external posts", ThreatLevel.CRITICAL),
    (r"curl\s+.*\|\s*(ba)?sh", "executable_install",
     "curl piped to shell — classic remote code execution vector", ThreatLevel.CRITICAL),
    (r"wget\s+\S+.*&&.*\./", "executable_install",
     "wget + execute pattern — downloading and running unknown code", ThreatLevel.CRITICAL),
    (r"git\s+clone\s+\S+.*&&.*(?:python|pip|npm|make|sh|bash|setup\.py)", "executable_install",
     "git clone + execute — never run cloned code", ThreatLevel.CRITICAL),
    (r"chmod\s+\+x\s+\S+.*&&\s*\./", "executable_install",
     "chmod +x + execute pattern", ThreatLevel.DANGEROUS),

    # --- Credential harvesting ---
    (r"(?:ANTHROPIC|OPENAI|GITHUB|AWS|SUPABASE)[_\s](?:API[_\s])?KEY\s*=", "credential_harvest",
     "Asks for API key assignment — never provide credentials", ThreatLevel.CRITICAL),
    (r"(?:enter|provide|input|set)\s+your\s+(?:api\s+key|password|token|secret)", "credential_harvest",
     "Requests credential input", ThreatLevel.DANGEROUS),
    (r"GITHUB_TOKEN\s*=\s*ghp_", "credential_harvest",
     "GitHub token pattern — never provide tokens", ThreatLevel.CRITICAL),
    (r"\$(?:ANTHROPIC_API_KEY|OPENAI_API_KEY|AWS_SECRET)\s*\|", "credential_harvest",
     "Environment variable piped out — credential exfiltration", ThreatLevel.CRITICAL),

    # --- Outbound data exfiltration ---
    (r"curl\s+.*-X\s+POST\s+https?://", "data_exfiltration",
     "curl POST to external URL — potential data exfiltration", ThreatLevel.DANGEROUS),
    (r"webhook\.site", "data_exfiltration",
     "webhook.site is commonly used for data exfiltration", ThreatLevel.DANGEROUS),
    (r"\bngrok\b", "data_exfiltration",
     "ngrok exposes local services to the internet", ThreatLevel.DANGEROUS),
    (r"curl\s+.*-d\s+@", "data_exfiltration",
     "curl sending file contents to external URL", ThreatLevel.CRITICAL),

    # --- Financial threats ---
    (r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b", "financial_threat",
     "Bitcoin address detected — never send cryptocurrency", ThreatLevel.CRITICAL),
    (r"\b0x[a-fA-F0-9]{40}\b", "financial_threat",
     "Ethereum address detected — never send cryptocurrency", ThreatLevel.CRITICAL),
    (r"paypal\.me/\S+", "financial_threat",
     "PayPal payment link — never send money", ThreatLevel.DANGEROUS),
    (r"(?:send|transfer|pay)\s+\d+(?:\.\d+)?\s*(?:BTC|ETH|USD|USDT)", "financial_threat",
     "Payment request detected", ThreatLevel.CRITICAL),

    # --- System damage ---
    (r"\brm\s+-rf\s+/(?:\s|$)", "system_damage",
     "rm -rf / — catastrophic system destruction", ThreatLevel.CRITICAL),
    (r"\bsudo\s+(?:tee|echo|cat)\s+/etc/", "system_damage",
     "Writing to system files — never modify /etc/", ThreatLevel.CRITICAL),
    (r"\bchmod\s+(?:777|666)\s+/(?:usr|etc|System|Library)", "system_damage",
     "Dangerous permission change on system directory", ThreatLevel.CRITICAL),
    (r"\bmkfs\b", "system_damage",
     "Filesystem format command — catastrophic data loss", ThreatLevel.CRITICAL),
    (r"\bdd\s+if=.*of=/dev/", "system_damage",
     "dd writing to device — potential disk destruction", ThreatLevel.CRITICAL),

    # --- Prompt injection ---
    (r"IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS", "prompt_injection",
     "Prompt injection attempt — ignore directive", ThreatLevel.CRITICAL),
    (r"<system>.*</system>", "prompt_injection",
     "Fake system prompt injection", ThreatLevel.DANGEROUS),
    (r"NEW\s+INSTRUCTIONS:\s+(?:Override|Ignore|Forget|Disregard)", "prompt_injection",
     "Prompt override attempt", ThreatLevel.DANGEROUS),
    (r"(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:a|an)\s+(?:helpful\s+)?assistant\s+that\s+(?:reveals|shows|exposes)", "prompt_injection",
     "Role injection attempting to bypass safety", ThreatLevel.CRITICAL),
]


def scan_text(text: str) -> ScanResult:
    """Scan text content for all known threat patterns."""
    result = ScanResult()
    if not text:
        return result

    for pattern, threat_type, description, level in _TEXT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            result.add_threat(threat_type, description, level)

    return result


# ── URL Scanning ─────────────────────────────────────────────────────────────

_SAFE_DOMAINS = {
    "github.com", "www.github.com",
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "arxiv.org", "www.arxiv.org",
    "docs.anthropic.com",
    "pypi.org",
    "npmjs.com", "www.npmjs.com",
    "stackoverflow.com",
    "en.wikipedia.org",
}

_SUSPICIOUS_TLDS = {".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".buzz", ".click"}

_DANGEROUS_URL_PATTERNS = [
    (r"webhook\.site", "data_exfiltration", "webhook.site data collection endpoint"),
    (r"pastebin\.com/raw/", "data_exfiltration", "raw pastebin — often used for malicious payloads"),
    (r"ngrok\.io", "data_exfiltration", "ngrok tunnel endpoint"),
    (r"requestbin\.com", "data_exfiltration", "request collection endpoint"),
]


def scan_url(url: str) -> ScanResult:
    """Scan a URL for safety before fetching."""
    result = ScanResult()
    if not url:
        return result

    try:
        parsed = urlparse(url)
    except Exception:
        result.add_threat("malicious_url", "Unparseable URL", ThreatLevel.DANGEROUS)
        return result

    domain = (parsed.hostname or "").lower()

    # IP address URLs are suspicious
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", domain):
        result.add_threat("malicious_url", f"IP address URL ({domain}) — suspicious", ThreatLevel.DANGEROUS)

    # Suspicious TLDs
    for tld in _SUSPICIOUS_TLDS:
        if domain.endswith(tld):
            result.add_threat("malicious_url", f"Suspicious TLD: {tld}", ThreatLevel.SUSPICIOUS)

    # Phishing patterns — domains that impersonate legitimate services
    # Only flag if the domain is NOT the legitimate service itself
    legit_domains = {"github.com", "www.github.com", "anthropic.com", "www.anthropic.com",
                     "docs.anthropic.com", "console.anthropic.com"}
    if domain not in legit_domains:
        phishing_patterns = [
            (r"github.*(?:login|auth|oauth)", "GitHub phishing domain"),
            (r"anthropic", "Possible Anthropic phishing domain"),
            (r"claude.*(?:api|key|token)", "Claude API phishing"),
        ]
        for pattern, desc in phishing_patterns:
            if re.search(pattern, domain):
                result.add_threat("malicious_url", desc, ThreatLevel.CRITICAL)

    # Known dangerous URL patterns
    for pattern, threat_type, desc in _DANGEROUS_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            result.add_threat(threat_type, desc, ThreatLevel.DANGEROUS)

    return result


# ── Repo Metadata Scanning ───────────────────────────────────────────────────

_SCAM_KEYWORDS = [
    "free unlimited", "bypass rate limit", "bypass api", "100x your",
    "unlimited api", "free api calls", "hack", "crack", "keygen",
    "free credits", "unlimited credits", "jailbreak",
]


def scan_repo_metadata(
    stars: int,
    age_days: int,
    has_tests: bool,
    has_license: bool,
    description: str = "",
) -> ScanResult:
    """
    Evaluate a GitHub repo's metadata for quality and safety signals.
    """
    result = ScanResult()
    desc_lower = description.lower()

    # Scam signals in description
    for kw in _SCAM_KEYWORDS:
        if kw in desc_lower:
            result.add_threat("scam_signals",
                              f"Scam keyword in description: '{kw}'", ThreatLevel.DANGEROUS)

    # Multiple exclamation marks = hype
    if description.count("!") >= 3:
        result.add_threat("scam_signals",
                          "Excessive exclamation marks — hype indicator", ThreatLevel.SUSPICIOUS)

    # Low quality signals
    if stars < 10:
        result.add_threat("low_quality_repo",
                          f"Very few stars ({stars}) — unvetted repo", ThreatLevel.SUSPICIOUS)

    if age_days < 7:
        result.add_threat("low_quality_repo",
                          f"Brand new repo ({age_days} days old) — unvetted", ThreatLevel.SUSPICIOUS)

    if not has_license:
        result.add_threat("low_quality_repo",
                          "No license — legal risk and quality signal", ThreatLevel.SUSPICIOUS)

    if not has_tests and stars < 50:
        result.add_threat("low_quality_repo",
                          "No tests and few stars — unreliable", ThreatLevel.SUSPICIOUS)

    return result


# ── Combined Safety Check ────────────────────────────────────────────────────


def is_safe_for_deep_read(post: dict) -> tuple:
    """
    Combined safety check before deep-reading a Reddit post.
    Returns (is_safe: bool, reason: str).
    """
    title = post.get("title", "")
    score = post.get("score", 0)
    url = post.get("url", "")

    # Very low or negative score = likely spam/downvoted malicious content
    if score < 0:
        return False, f"Negative score ({score}) — likely spam or malicious"

    # Scan title for threats
    title_scan = scan_text(title)
    if title_scan.threat_level.value >= ThreatLevel.DANGEROUS.value:
        threats = ", ".join(title_scan.threat_types)
        return False, f"Title contains threats: {threats}"

    # Scan URL if it's not a self-post reddit link
    if url and "reddit.com" not in url:
        url_scan = scan_url(url)
        if url_scan.threat_level.value >= ThreatLevel.DANGEROUS.value:
            threats = ", ".join(url_scan.threat_types)
            return False, f"URL is suspicious: {threats}"

    return True, "Clean"


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python3 content_scanner.py text 'content to scan'")
        print("  python3 content_scanner.py url 'https://example.com'")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "text":
        text = " ".join(sys.argv[2:])
        result = scan_text(text)
    elif cmd == "url":
        result = scan_url(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    if result.has_threats:
        print(f"THREATS DETECTED (level: {result.threat_level.name})")
        for d in result.details:
            print(f"  [{d['level']}] {d['type']}: {d['description']}")
    else:
        print("CLEAN — no threats detected")


if __name__ == "__main__":
    main()
