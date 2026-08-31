"""Gate unit tests: every forbidden regex, the compound proxied-apex rule,
banned claims (plain + proximity), and line-numbered findings."""

from __future__ import annotations

from conftest import lint_text

from szl_payload import gates


def _rules(name: str) -> list[str]:
    rules = [
        line.strip()
        for line in lint_text(name).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return rules


def scan(text: str, name: str = "forbidden.txt") -> list[str]:
    """Gate findings for *text* against every rule in the lint file."""
    rules = _rules(name)
    if name == "banned_claims.txt":
        regexes, _prox = gates.split_banned_claims(rules)
        import re

        findings = gates.check_regexes(
            text, "doc.md", regexes, "banned_claims", flags=re.IGNORECASE
        )
    else:
        findings = gates.check_regexes(text, "doc.md", rules, "forbidden")
    return [finding.render() for finding in findings]


class TestNameHashRegex:
    RULE = "sha256\\(\\s*[\"'][A-Za-z0-9_/-]+[\"']\\s*\\.encode\\(\\)\\s*\\)"

    def test_name_hashing_matches(self):
        assert scan('digest = sha256("SZLHOLDINGS/SZL-1".encode())'), "name-hash must be caught"
        assert scan("sha256('subdir/file'.encode())")

    def test_real_byte_digest_does_not_match(self):
        assert scan("digest = sha256_file(path)") == []
        assert scan("digest = hashlib.sha256(chunk).hexdigest()") == []
        assert scan('sha256_bytes(text.encode("utf-8"))') == []


class TestEmptySigRegex:
    def test_empty_sig_matches(self):
        assert scan('"sig": ""')
        assert scan('{ "sig":"" }')

    def test_populated_sig_does_not_match(self):
        assert scan('"sig": "MEUCIQD..."') == []


class TestPendingKeyidRegex:
    def test_pending_keyid_matches(self):
        assert scan('"keyid": "PENDING-SIGSTORE-01"')

    def test_real_keyid_does_not_match(self):
        assert scan('"keyid": "sha256:9f86d0"') == []


class TestSpecVersionRegex:
    def test_hardcoded_16_matches(self):
        assert scan('"specVersion": "1.6"')
        assert scan('"specVersion":"1.6"')

    def test_newer_version_does_not_match(self):
        assert scan('"specVersion": "1.7"') == []


class TestCollectionsAuthorRegex:
    def test_author_query_matches(self):
        assert scan("GET https://huggingface.co/api/collections?author=SZLHOLDINGS")

    def test_owner_query_does_not_match(self):
        assert scan("GET https://huggingface.co/api/collections?owner=SZLHOLDINGS") == []


class TestSecretLoggingRegex:
    RULE = "print\\([^)]*(TOKEN|SECRET|API_KEY|PAT)\\b"

    def test_printing_secret_matches(self):
        assert scan('print("credential:", CLOUDFLARE_TOKEN)')
        assert scan("print(f'{API_KEY=}')")
        assert scan('print("pat:", GITHUB_PAT)')

    def test_printing_public_data_does_not_match(self):
        assert scan('print("status: active")') == []
        # A variable that merely contains the substring is not a credential.
        assert scan('print("transport:", transport)') == []


class TestForbiddenDomainRegex:
    RULE = r"(?<!-)a11oy\.com"

    def test_bare_domain_matches(self):
        assert scan("see a11oy.com for details"), "bare forbidden domain must be caught"
        assert scan("https://a11oy.com/path")

    def test_hyphen_prefixed_canonical_forms_do_not_match(self):
        # The negative lookbehind protects a-11oy.com and a-11-oy.com.
        assert scan("canonical: a-11oy.com and a-11-oy.com") == []

    def test_defanged_form_does_not_match(self):
        assert scan("a11oy[.]com is never linked") == []


class TestProxiedPagesApex:
    """Compound rule, enforced in code: proxied flag NEAR a Pages apex address."""

    APEX = "185.199.108.153"

    def test_proxied_true_near_apex_fails(self):
        text = (
            "records:\n"
            f'  - {{ type: A, name: "@", content: {self.APEX}, proxied: true }}\n'
        )
        findings = gates.check_proxied_pages_apex(text, "dns.yml")
        assert findings, "proxied:true near 185.199.* is the orange-cloud-on-apex bug"
        assert findings[0].gate == "proxied_pages_apex"

    def test_json_form_matches(self):
        # JSON form with a quoted key must also fire.
        text = '{"content": "' + self.APEX + '", "proxied": true}'
        assert gates.check_proxied_pages_apex(text, "zone.json")

    def test_grey_cloud_apex_passes(self):
        text = f'- {{ type: A, content: {self.APEX}, proxied: false }}'
        assert gates.check_proxied_pages_apex(text, "dns.yml") == []

    def test_proxied_true_far_from_apex_passes(self):
        text = "proxied: true\n" + ("filler line of ordinary dns doctrine prose\n" * 20)
        text += f"apex fallback address {self.APEX}\n"
        assert gates.check_proxied_pages_apex(text, "doc.md") == []

    def test_apex_alone_passes(self):
        assert gates.check_proxied_pages_apex(f"A record {self.APEX}", "doc.md") == []


class TestBannedClaims:
    def test_plain_banned_claims_match_case_insensitively(self):
        assert scan("the First Governance Kernel ships today", "banned_claims.txt")
        assert scan("achieving state of the art results", "banned_claims.txt")
        assert scan("a production-ready release", "banned_claims.txt")
        assert scan("world-first governance", "banned_claims.txt")
        assert scan("world first governance kernel", "banned_claims.txt")

    def test_unrelated_text_passes(self):
        assert scan("the kernel passes its gate suite", "banned_claims.txt") == []

    def test_proximity_rule_split(self):
        regexes, proximity = gates.split_banned_claims(_rules("banned_claims.txt"))
        assert proximity == 200
        assert all("within" not in rule for rule in regexes)


class TestSignedUnsignedProximity:
    """'signed' within 200 chars of unsigned.json fails; farther apart passes."""

    def check(self, text: str) -> list[gates.Finding]:
        return gates.check_signed_unsigned_proximity(text, "doc.md", 200)

    def test_close_pair_fails(self):
        # 'signed' 50 chars before 'unsigned.json' is inside the 200-char window.
        text = "signed" + ("-" * 43) + " unsigned.json"
        assert self.check(text), "'signed' 50 chars before unsigned.json must fail"

    def test_distant_pair_passes(self):
        # 300 chars apart is outside the window: passes.
        text = "signed " + ("-" * 293) + " unsigned.json"
        assert self.check(text) == []

    def test_unsigned_word_inside_unsigned_json_is_not_signed(self):
        # \bsigned\b must not match inside "unsigned.json" itself.
        text = "the export_manifest.unsigned.json file"
        assert self.check(text) == []


class TestLineNumberedFindings:
    def test_finding_reports_exact_line(self):
        text = "line one\nline two\nsee a11oy.com here\nline four\n"
        findings = gates.check_regexes(text, "doc.md", [r"(?<!-)a11oy\.com"], "forbidden")
        assert len(findings) == 1
        assert findings[0].location == "doc.md:3"

    def test_multiple_matches_report_each_line(self):
        text = "a11oy.com\nclean\na11oy.com\n"
        findings = gates.check_regexes(text, "doc.md", [r"(?<!-)a11oy\.com"], "forbidden")
        assert [f.location for f in findings] == ["doc.md:1", "doc.md:3"]
