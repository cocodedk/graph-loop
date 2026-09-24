# Security Policy

## Reporting a Vulnerability

Do **not** open a public GitHub issue for security vulnerabilities.

To report a vulnerability:
- Use the **"Report a vulnerability"** button on the Security tab of this repository (GitHub private advisory)
- Or email: babak@cocode.dk

We will acknowledge within 5 business days and aim to release a fix within 30 days of
confirmation.

## What this tool does with your credentials

It does not handle them. The loop shells out to command-line agents that are already
logged in on the machine running it, and it never reads, stores or forwards their
credentials. It writes a campaign log containing every prompt sent and answer received —
treat that log as sensitive if your task contracts are.

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | ✅ |
| older   | ❌ |
