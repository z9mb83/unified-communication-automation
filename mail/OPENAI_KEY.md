# OpenAI API key (AI email drafts)

The sender writes each email draft with OpenAI (model `gpt-5-mini`, set by env `OPENAI_MODEL`).
The key is **never** in the sheet or in git: it lives in Google Secret Manager and the Cloud Run job
`email-sender-master` reads it as the environment variable `OPENAI_API_KEY`.

**Cost:** OpenAI has no free API tier - the account needs a little prepaid credit. One draft is about
1,000-1,500 tokens, i.e. roughly **$0.001 (under ₹0.10) per email** with `gpt-5-mini`; 1,000 drafts ≈ $1.
Set a monthly budget limit in OpenAI (step 1) so it can never cost more than you choose.

## 1. Get a key (openai.com)
1. Go to <https://platform.openai.com> and sign in (the same account that already pays for the key, if you have one).
2. **Settings → Billing**: check there is credit (add $5 if it is 0 - that lasts thousands of emails).
   **Settings → Limits**: set a monthly budget (e.g. $5).
3. **API keys** (<https://platform.openai.com/api-keys>) → **Create new secret key** → name it `email-sender`,
   permissions *All* (or *Restricted* with **Responses: Write**) → **Create** → **Copy**.
   The key starts with `sk-` and is shown only once. Do not paste it into the sheet, a chat or an email.

## 2. Check which secret the job uses (Cloud Shell)
```bash
gcloud run jobs describe email-sender-master --region us-central1 --format=yaml | grep -B1 -A4 OPENAI_API_KEY
```
You will see `secretKeyRef` with `name: openai-api-key` (the secret) and `key: latest` (the version).

## 3. Save the key as a new secret version (Cloud Shell)
```bash
read -rs -p "Paste the OpenAI key and press Enter: " KEY; echo
printf '%s' "$KEY" | gcloud secrets versions add openai-api-key --data-file=-
unset KEY
```
(`read -s` keeps the key off the screen and out of the shell history.)
If step 2 showed a number instead of `latest`, point the job at the new version:
`gcloud run jobs update email-sender-master --region us-central1 --update-secrets OPENAI_API_KEY=openai-api-key:latest`

## 4. Test it (no email is sent)
```bash
bash go_master.sh sender     # or just wait for the next 5-minute run
```
Then in the sheet: a lead row with Email filled and Subject/Draft empty gets a new draft (status *Generated*).
If a draft fails, column **Error** shows `OpenAI generation error: ...`:

| Error text | Meaning |
|---|---|
| `401` / `invalid_api_key` | wrong or deleted key - repeat step 3 |
| `429` / `insufficient_quota` | no credit left or budget limit reached - add credit / raise the limit |
| `OPENAI_API_KEY is missing` | the job has no key - steps 2-3 |
| `Draft kept spam-risk wording ...` | the AI used a spam-trigger word twice; the row is retried on the next run (normal, rare) |

## 5. Old key
After the new key works, delete the old key on <https://platform.openai.com/api-keys> (optional; only you can do this).

## How drafts avoid spam (for reference - `app/email_generator.py`)
- Each draft gets a random brief: opening style, angle (per brand), call to action, greeting, length (60-110 words)
  and opt-out wording - so no two emails look alike.
- Rules for the AI: plain personal tone, 2-6 word lowercase subject (never "quick question"), no links, no
  exclamation marks, no bullets, no spam words (free, guarantee, discount, act now, ...), personalised from **Details**.
- Every draft is checked; if it breaks a rule it is rewritten once. The signature has no website link
  (links in a first cold email hurt delivery).
- Before sending, the lead's email domain is checked (can it receive mail?). If not, the row is
  **Skipped – would bounce** instead of sending. Bounces found by the 10 AM / 6 PM reports mark the lead
  **Bounced** and add it to **Do Not Contact**.
