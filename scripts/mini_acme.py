#!/usr/bin/env python3
"""Mini ACME v2 client for one DNS-01 cert, split-network style:
- Let's Encrypt calls go DIRECT (sandbox egress allows it when not proxied).
- Cloudflare calls go through the credential-injecting proxy (requests, trust_env=True).
Usage: python3 mini_acme.py <domain> <zone_id> <outdir>
"""
import base64, hashlib, json, subprocess, sys, time

import httpx
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DOMAIN, ZONE_ID, OUTDIR = sys.argv[1], sys.argv[2], sys.argv[3]
LE = "https://acme-v02.api.letsencrypt.org"

b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()

acct_key = ec.generate_private_key(ec.SECP256R1())
acct_key_bytes = acct_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)

direct = httpx.Client(trust_env=False, timeout=30.0)

directory = direct.get(f"{LE}/directory").json()
print("directory ok:", sorted(directory.keys()))

def nonce():
    return direct.head(directory["newNonce"]).headers["Replay-Nonce"]

def jws(payload, url, kid=None, with_jwk=False):
    protected = {"alg": "ES256", "nonce": nonce(), "url": url}
    if with_jwk:
        pn = acct_key.public_key().public_numbers()
        protected["jwk"] = {
            "kty": "EC", "crv": "P-256",
            "x": b64u(pn.x.to_bytes(32, "big")),
            "y": b64u(pn.y.to_bytes(32, "big")),
        }
    else:
        protected["kid"] = kid
    p64 = b64u(json.dumps(protected).encode())
    pay64 = b64u(json.dumps(payload).encode()) if payload is not None else ""
    sig = acct_key.sign(f"{p64}.{pay64}".encode(), ec.ECDSA(hashes.SHA256()))
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    r, s = decode_dss_signature(sig)
    body = {"protected": p64, "payload": pay64, "signature": b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))}
    r_ = direct.post(url, json=body, headers={"Content-Type": "application/jose+json"})
    if r_.status_code >= 400:
        raise RuntimeError(f"ACME {url} -> {r_.status_code}: {r_.text[:300]}")
    return r_

# 1. account
acc = jws({"termsOfServiceAgreed": True, "contact": ["mailto:eng@szlholdings.com"]},
          directory["newAccount"], with_jwk=True)
KID = acc.headers["Location"]
print("account:", KID.split("/")[-1])

# 2. order
order = jws({"identifiers": [{"type": "dns", "value": DOMAIN}]}, directory["newOrder"], kid=KID)
order_url = order.headers["Location"]
authz_url = order.json()["authorizations"][0]
print("order:", order_url.split("/")[-1])

# 3. dns-01 challenge
authz = direct.get(authz_url).json()
chal = next(c for c in authz["challenges"] if c["type"] == "dns-01")
def jwk_thumbprint():
    pn = acct_key.public_key().public_numbers()
    jwk = {"crv": "P-256", "kty": "EC",
           "x": b64u(pn.x.to_bytes(32, "big")), "y": b64u(pn.y.to_bytes(32, "big"))}
    canon = json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()
    return b64u(hashlib.sha256(canon).digest())

key_auth = f"{chal['token']}.{jwk_thumbprint()}"
txt_value = b64u(hashlib.sha256(key_auth.encode()).digest())
fqdn = f"_acme-challenge.{DOMAIN}"
print("TXT:", fqdn, "=", txt_value)

# 4. create TXT via Cloudflare (curl subprocess: the proxy CA is wired for curl)
def cf_curl(method, url, payload=None):
    cmd = ["curl", "-sf", "--max-time", "30", "-X", method,
           "-H", "Content-Type: application/json", url]
    if payload is not None:
        cmd += ["--data-binary", json.dumps(payload)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"cf_curl {method} {url} failed: {out.stderr[:200]} {out.stdout[:200]}")
    return json.loads(out.stdout or "{}")

cf = cf_curl("POST", f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records",
             {"type": "TXT", "name": fqdn, "content": txt_value, "ttl": 60})
TXT_ID = cf["result"]["id"]
print("cf txt created:", TXT_ID[:8])

# 5. wait for public visibility (query the authoritative path directly; local caches lie)
visible = False
for i in range(45):
    for resolver in ("@1.1.1.1", "@8.8.8.8", ""):
        out = subprocess.run(["dig", "+short", "TXT", fqdn] + ([resolver] if resolver else []),
                             capture_output=True, text=True).stdout.strip().strip('"')
        if txt_value in out:
            visible = True; break
    if visible:
        print("txt visible after", i); break
    time.sleep(6)
if not visible:
    raise RuntimeError("TXT never became visible")

# 6. accept challenge, poll
jws({}, chal["url"], kid=KID)
for i in range(30):
    st = direct.get(chal["url"]).json()
    if st["status"] in ("valid", "invalid"):
        break
    time.sleep(3)
if st["status"] != "valid":
    raise RuntimeError(f"challenge failed: {json.dumps(st)[:300]}")
print("challenge valid")

# 7. finalize with CSR (certificate key MUST differ from the account key)
cert_key = ec.generate_private_key(ec.SECP256R1())
cert_key_bytes = cert_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
csr = (
    x509.CertificateSigningRequestBuilder()
    .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, DOMAIN)]))
    .add_extension(x509.SubjectAlternativeName([x509.DNSName(DOMAIN)]), critical=False)
    .sign(cert_key, hashes.SHA256())
)
csr_der = csr.public_bytes(serialization.Encoding.DER)
fin_url = order.json()["finalize"]
fin = jws({"csr": b64u(csr_der)}, fin_url, kid=KID)
cert_url = None
for i in range(30):
    o = direct.post_as_json if False else None
    o = jws(None, order_url, kid=KID)  # POST-as-GET
    oj = o.json()
    if oj["status"] == "valid":
        cert_url = oj["certificate"]; break
    if oj["status"] == "invalid":
        raise RuntimeError("order invalid")
    time.sleep(3)
if not cert_url:
    raise RuntimeError("order never finalized")

# 8. download cert
cert = jws(None, cert_url, kid=KID).text
import os
os.makedirs(OUTDIR, exist_ok=True)
open(f"{OUTDIR}/{DOMAIN}.crt", "w").write(cert)
open(f"{OUTDIR}/{DOMAIN}.key", "wb").write(cert_key_bytes)
print("CERT SAVED:", f"{OUTDIR}/{DOMAIN}.crt")

# 9. cleanup TXT
cf_curl("DELETE", f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{TXT_ID}")
print("txt cleaned up")
