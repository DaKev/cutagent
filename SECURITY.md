# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in CutAgent, please report it responsibly.

**Do not open a public issue.**

Instead, please email the maintainers at the address listed in the repository or use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) feature.

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Scope

CutAgent is a local CLI tool that shells out to FFmpeg. Security concerns include:

- **Command injection** via untrusted file paths or EDL content passed to subprocess calls
- **Path traversal** in output file paths specified in EDLs
- **Denial of service** through crafted media files that cause FFmpeg to hang or consume excessive resources

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | Yes                |
