# Independent Market Intelligence content
Public content site: https://notwins.github.io/market-intelligence-content/
Existing Hub UI: https://notwins.github.io/market-intelligence-hub/

This repository has its own GitHub Pages build, artifact and deployment. Its workflow never checks out or deploys the UI repository. UI rollback cannot replace this site's artifact.

## Publish a complete report
Prepare a private complete V3 report and metadata. Run:
`python scripts/prepare_research_bundle.py --channel earnings --report-dir <private-public-files> --metadata <private-metadata.json> --output <new-private-bundle>`
Channels: earnings, credit, policy, or standalone with --slug. Optional matching --brief. Review completeness, facts, privacy, rights and accessibility, then bind the private review receipt to the canonical record hash.
Run submit_research.py against THIS repository on latest main. Add only site/research/<dated-id>/* and site/data/research-records/<dated-id>.json. The immutable full report is never replaced by an extract. Same edition retries are no-ops; corrections use an explicit revision.
Run research_feed.py, the tests, and content_release.py with a NEW staging path outside the repository before a guarded non-force write. Wait for content.yml and verify the report, feed, link and runtime search in the Hub.

## Reuters
Use import_hourly_news.py with reviewed public-only input outside the repository. The frozen baseline preserves existing public history and version identities. Existing hourly archives and all older full reports remain at their ORIGINAL Hub URLs; no old research files are moved here. Do not rearchive baseline editions. New editions require hashed source identity and no private conversation URL.

## Owned paths and rollback
Research: site/research/<dated-id>/* plus site/data/research-records/<dated-id>.json.
News: site/data/hourly-news.json plus new site/data/hourly-archive/*.json.
Build code, pinned public standards and fallback card renderer are content-infrastructure changes, separate from ordinary publication commits.
Correct failed code by restoring explicit code paths on current main. Never roll content back to an earlier whole-site snapshot. A failed build leaves the last successful Pages artifact live. Append-only guards reject deletion or alteration of published research and prior news versions.
UI changes use the Hub repository and its deployment only. A UI release must retain the content-source reader contract; it must never overwrite, rebuild or roll back this content site.

## Baseline
Cutover source: Hub commit 3ed568866a968ef0c6d08f4387381f9fc4c46c68.
Only already-public news metadata and publication identities are retained as a validation baseline. Private material, credentials and review receipts are excluded.
The content site is compatible with feed schema 1. Its pinned validators and renderer were taken from the reviewed Hub cutover; adopting future schema changes requires explicit compatibility tests. No runtime build dependency on the UI main branch exists.

