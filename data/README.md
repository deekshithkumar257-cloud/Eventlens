# Synthetic sample data

All records here are **fictional**. Usernames and hostnames are invented, and
external addresses use documentation-only ranges (RFC 5737: `192.0.2.0/24`,
`198.51.100.0/24`, `203.0.113.0/24`). Nothing here represents a real organization,
system, or person.

| File | Format | Purpose |
|---|---|---|
| `sample_logs.json` | JSON (`{"events": [...]}`) | Full demo dataset loaded by **Load sample logs**. 50 events. |
| `auth_logs.csv` | CSV | The 40 login events from the sample, for CSV upload testing. |
| `network_logs.csv` | CSV | The 10 network connection events from the sample. |

The CSV files contain exactly the same events as the JSON sample. Uploading them
after the sample reports them as duplicates, which demonstrates duplicate handling.

The sample is designed to show:

- Normal successful logins from internal workstations and one VPN user.
- Six failed logins for one account, with no success (Rule 1, Medium).
- Four failures followed by a success, below the threshold (no alert).
- Seven failures from one external IP, then a success from that IP (Rule 2, High).
- Eleven failed attempts across accounts from one IP (Rule 1, High via escalation).
- A successful login outside the 10-minute window, which does not trigger Rule 2.

`eventlens.db` is created here at runtime and is ignored by Git.
