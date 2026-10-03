# Solo-maintainer change control

SZL Platform has one human maintainer. A second approval and a DCO sign-off are
not prerequisites for ordinary changes. The repository instead requires a pull
request, a verified commit signature, successful CI on the current PR head,
resolved review threads, and a protected merge. A passing check proves only
the checks it actually ran; it does not certify a live deployment or an
external provider.

The active [main ruleset](https://github.com/szl-holdings/szl-platform/rules/24403330)
requires signed commits, a pull request with zero required approving reviews,
resolved review threads, and strict GitHub Actions checks. It allows squash
merges and blocks direct deletion and force pushes. It has no bypass actors.
The required checks are:

| Workflow | Required GitHub Actions context |
|---|---|
| `ci.yml` | `test (3.11)` |
| `ci.yml` | `test (3.12)` |
| `codeql.yml` | `analyze / Analyze (python)` |
| `codeql.yml` | `analyze / Analyze (javascript-typescript)` |

For each merge, verify the current main rules with the GitHub branch-rules API,
the PR's actual head SHA and checks, unresolved review threads, and the
post-merge main SHA and signature. Keep source CI, a protected merge,
publication, and live runtime evidence separate. A missing check or an
unreadable rules API is not a passing control.

The ruleset is GitHub configuration, not generated from this document. Changes
to its check names, required signatures, review-thread setting, or bypass list
must be read back from GitHub and exercised by a fresh PR before being described
as operational. The older classic protection and organization branch-integrity
rule may add restrictions; neither replaces the rules listed above.
