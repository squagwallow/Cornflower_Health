# samples/

This directory stores real Health Auto Export (HAE) JSON payload samples. These samples are used to verify field names, nesting structure, and unit values.

## Naming Convention

```
hae_sample_YYYY-MM-DD.json
```

Use the date the sample was captured (not the health date it represents).

## Before Saving a Sample

- Remove any PII if present
- Do not include device identifiers, account tokens, or webhook URLs
- Note the HAE app version and iOS version in a comment at the top of the file (or in this README below)

## Captured Samples

| Filename | Date Captured | HAE Version | iOS Version | Notes |
|---|---|---|---|---|
| *(none yet)* | — | — | — | — |

## How to Capture

1. Go to webhook.site (or similar request logger)
2. Copy the unique URL
3. In HAE, temporarily set the webhook destination to that URL
4. Trigger a manual export
5. Copy the raw request body from the logger
6. Save to this directory following the naming convention above
7. Restore the original webhook URL in HAE
