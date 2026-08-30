# ACTIVATE — NEXUS-AI-CORE (Vault-native)

This repo uses the **shared Garcar Vault** plane defined in `autonomous-butler-core`.

## Required

1. Same Vault instance as butler-core
2. GitHub secret: `VAULT_ADDR` only
3. JWT role `garcar-github-actions` already includes this repo

## Secrets paths used

```
secret/data/garcar/ai
secret/data/garcar/stripe
secret/data/garcar/github
secret/data/garcar/slack
secret/data/garcar/supabase
secret/data/garcar/enrichment
secret/data/garcar/infra
```

Bootstrap and path creation are done once from `autonomous-butler-core`:

```bash
cd autonomous-butler-core
./vault/automater/automate-all.sh
```

Then add `VAULT_ADDR` to **this** repo's Actions secrets.
