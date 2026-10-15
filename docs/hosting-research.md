# PO Agent — hosting research (CEO decision 3), updated 13 Oct 2026

> **14 Oct 2026 update:** the trial now runs on an **Anthropic cloud routine** running the script (ADR-002 Option C, with gates H2 and H5 waived for the trial only; `docs/decisions.md`). Production is still CEO decision 3, pending; Joey expects the **Sydney cloud VM** row below to be the most likely outcome. The figures below are unchanged.

Deep-research run (22 sources, adversarially verified) plus Anthropic pricing checked directly. Prices are list prices read on 13 Oct 2026 and converted at the RBA rate of 1 USD = 1.433 AUD; AUD figures include 10% GST. **Decision 3 is pending with the CEO.**

## Options

| Option | Monthly running cost (AUD) | Setup effort (one Python dev) | Ongoing upkeep | Main risk | Verdict |
|---|---|---|---|---|---|
| VM provided by IT | ~0 extra | ~1 day once provided | IT patches; ~1 h/month agent updates | IT lead time; must not run on the old server | **First choice** |
| Small Linux cloud VM, Sydney, 2 GB (Vultr US$10–12, DigitalOcean US$12, Lightsail US$12) | ~16–19 (~35 Windows on Lightsail) | ~1 day | ~1 h/month (auto OS updates, monthly Playwright update) | MySys may block/flag cloud IPs (test first) | **Fallback** (most likely production host, 14 Oct) |
| Azure B1ms VM, Australia East | ~32–35 | ~1 day | Same as above | About twice the price | Only if the company is already on Azure |
| Dedicated office mini PC | 400–900 one-off + ~3–5 power (unverified) | ~1 day + buying it | Joey patches it | Office power/internet outages; physical security | If MySys blocks cloud IPs |
| Existing company server | ~0 | ~1 day | — | Very old hardware; failure stops the agent | Not recommended |
| PO admin's PC | None | Ready now | — | Off when the admin is off; others can reach the logins | Trial only (superseded by the cloud routine) |
| Anthropic cloud routine running the script | ~0 hosting; draws down plan usage | 2–4 days | Transcript checks; research preview | Secrets readable by the session; no state between runs; personal account | **Trial only** (14 Oct), H2/H5 waived |
| Serverless container job (Azure Container Apps Jobs / Cloud Run Jobs / Fargate) | ~0–10 | 3–5 days (Docker, registry, identity, UTC-only cron on Azure) | Image rebuilds; harder debugging | Complexity for one developer | Not worth it |
| GitHub Actions schedule | ~0 | Low | Low | Delayed/dropped runs at the top of the hour; shared, changing IPs; region can't be chosen | Rejected |
| External IT provider (MSP) | ~50–200+ (unverified) | Provider | Provider | Cost; a third party sees PO data | Only if a contract already covers it |

## Claude API (per PO = 1–2 page PDF, ~10k input + ~0.5k output tokens worst case)

Pricing from platform.claude.com/docs/en/about-claude/pricing (13 Oct 2026). PDF pages use 1,500–3,000 text tokens each, plus image tokens.

| Model | USD per million tokens (input / output) | Per PO | Per month (~217 POs) |
|---|---|---|---|
| Haiku 5.5 | $0.10 / $0.50 | ~US$0.001 | < A$1 |
| Sonnet 5.5 | $2 / $10 | ~US$0.025 | ~A$8–9 |
| Opus 5.5 | $4 / $20 | ~US$0.05 | ~A$16 |

Measure real usage in the trial (the API's usage field). Test the smaller model against the decision-seam fixtures.

## Recommendation (13 Oct 2026; production)

1. Ask IT for a VM that does **not** run on the existing (very old) server. A request with requirements has been drafted: Ubuntu 24.04 LTS (or Windows Server); 2 vCPU, 4 GB RAM, 40 GB disk; always on 07:00–18:00 Perth weekdays; outbound HTTPS only to the MySys sites, `api.anthropic.com`, PyPI and Playwright's browser download; non-admin service account; secret store; patching owner; backups; a second admin.
2. Otherwise, use one 2 GB Linux VM in Sydney on a company account with a second admin. Run with cron or a systemd timer (TZ=Australia/Perth); keep secrets in a root-only credentials file; add a free dead-man ping to alert on missed runs. The same machine can host the next 5–7 automations.
3. Before committing, spend 10 minutes logging into the MySys test site from that machine. If cloud IPs are blocked, use an office mini PC.

**Total:** about A$1–9/month on an IT VM, or about A$20–28/month on a cloud VM (including Claude).

Hosting in Sydney doesn't keep PDF content in Australia, because the Claude call still leaves the country. That's CEO decision 2.

Sources: vultr.com/pricing, digitalocean.com/pricing/droplets, aws.amazon.com/lightsail/pricing, Azure retail prices API (australiaeast B1ms), learn.microsoft.com container-apps billing and jobs, cloud.google.com/run/pricing, aws.amazon.com/fargate/pricing, docs.github.com (events that trigger workflows; GitHub-hosted runners), playwright.dev/docs/docker, rba.gov.au exchange rates, platform.claude.com pricing and PDF support; code.claude.com/docs/en/routines and /cloud-environments (14 Oct 2026).
