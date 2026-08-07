# Public records

Documents the chronicle cites that are **public records published by the body
that issued them** — a UN communication, a court filing, a government response.
They are kept here so the evidence travels with the repository rather than
depending on somebody else's server staying up.

Populate the folder from the repo root:

```bash
bash scripts/fetch-documents.sh
```

The script skips anything already downloaded, so it is safe to re-run. If a
host blocks automated requests it says so and prints the URL to save by hand.

`.gitignore` excludes PDFs everywhere else in this repository on purpose — a
private course reading pack was committed by accident once. This folder is the
single exception, and only for documents that are already public.

| File | Document |
|---|---|
| `ohchr-joint-communication-canada-2026.pdf` | Joint communication from five UN special rapporteurs to the Government of Canada on threats to the life of Moninder Singh, June 2026, released August 2026. [OHCHR communications database](https://spcommreports.ohchr.org/TMResultsBase/DownLoadPublicCommunicationFile?gId=31021) |
