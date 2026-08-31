// Test fixture: byte-level reproduction of the live org's
// szl-command-lab/src/lib/publish.ts forbidden-domain finding: two TRUE
// violations (the FOREIGN origin's host + href lines), surrounded by
// legitimate prohibition/guard contexts that must NOT be flagged.
//
// Expected verdict: exactly 2 true violations in this file, at lines 37/41,
// matching the live audit. The two publish-map.json copies live under
// src/data/ and public/data/.

type PublishOrigin = {
  role: string;
  status: "NOT_PUBLISHED" | "FOREIGN";
  claim: "DEMO" | "MEASURED";
  href: string;
  note: string;
};

export const ORIGINS: readonly (PublishOrigin & { host: string })[] = [
  {
    host: "a-11-oy.com",
    role: "Product",
    status: "NOT_PUBLISHED",
    claim: "DEMO" as const,
    href: "https://a-11-oy.com",
    note: "Canonical product surface.",
  },
  {
    host: "a11oy.net",
    role: "Proof",
    status: "NOT_PUBLISHED",
    claim: "DEMO" as const,
    href: "https://a11oy.net",
    note: "Canonical proof surface.",
  },
  {
    role: "Not SZL",
    host: "a11oy.com",
    status: "FOREIGN",
    claim: "MEASURED" as const,
    note: "Cloudways storefront titled Alloy Home and Garden. Doctrine: never a11oy.com as canonical; do not point product or proof here.",
    href: "https://a11oy.com",
  },
] as const;

export const RECOMMENDATION = {
  verdict: "Keep Product | Proof. Fold MEASURED inventory into a11oy.net.",
  never: [
    "Never use a11oy.com as canonical.",
  ],
} as const;
