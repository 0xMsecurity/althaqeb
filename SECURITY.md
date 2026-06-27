# Security Policy — الثاقب (Althaqeb)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✓ Current |

## Responsible Disclosure

If you discover a security vulnerability in Althaqeb itself, please report it responsibly:

**Email:** msecuritybh@gmail.com  
**GitHub:** Open a private security advisory at https://github.com/0xMsecurity/althaqeb/security/advisories/new

Please **do not** open a public issue for security vulnerabilities.

## What to Report

- Vulnerabilities in Althaqeb's own codebase (the `vdbresidue` auditor and the registry/standard tooling)
- Any bug that makes the auditor write to or mutate a target store — it must stay strictly read-only
- Integrity-gate bypasses (a published claim passing without its committed evidence file)
- Dependencies with known CVEs

## Out of Scope

- The documented erasure-durability behaviour of third-party engines — that is the research
  finding, handled via coordinated disclosure (see below), not a bug in this repo
- Vulnerabilities in third-party dependencies not yet patched upstream

## Findings about third-party engines

This project documents erasure-durability behaviour in third-party vector databases. Per-vendor
advisories are **withheld from this repository pending coordinated disclosure** through each
vendor's security channel. The research finding itself is described in the paper and the VEDC
standard; the ready-to-send vendor packets are not published here.

## Acknowledgements

With thanks to researchers who practice responsible disclosure.

---

**Note:** `vdbresidue` is a read-only forensic auditor. Run it only against data stores you own
or are explicitly authorized to audit. It does not modify target systems. See the README.
