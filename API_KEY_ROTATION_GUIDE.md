# 🔑 CRITICAL: API Key Rotation Guide

## ⚠️ URGENT ACTION REQUIRED

The following API keys were **EXPOSED in git history** and have now been removed. However, they **MUST BE ROTATED** immediately before pushing to GitHub.

---

## 📋 Keys That Were Exposed

### 1️⃣ OpenAI API Key
**Exposed**: `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`

**Action Required**:
1. Go to: https://platform.openai.com/api-keys
2. Delete the exposed key
3. Create a new API key
4. Update `.env` with new key: `OPENAI_API_KEY=sk-new-key-here`

---

### 2️⃣ Airtable Personal Access Token
**Exposed**: `patASeCbFCje0QWQA.3778291b115ac191884d2f9c4c830e6dd69e1d0e4bd7220a9b2c04f5418d2ffe`

**Action Required**:
1. Go to: https://airtable.com/create/tokens
2. Revoke the exposed token
3. Create a new Personal Access Token
4. Update `.env` with new token: `AIRTABLE_TOKEN=pat-new-token-here`

---

### 3️⃣ Twitter/X API Credentials

**Exposed Keys**:
- Consumer Key: `DPuSP2IuMvoKjLsHO7ABbovld`
- Consumer Secret: `UHtv9yBsrsvtLqjVNrTyF2czki0tqSYdf7scbaw1EWVckzXzrg`
- Access Token: `16196634-GUaLnjg3EbgkiyqPH99c9jFeRt52hme2wSXM7DoLx`
- Access Token Secret: `vkZL6SU5Uljw9H7hbryOPpkBuIOXAVrdFSGkNtR1p6QEP`

**Action Required**:
1. Go to: https://developer.twitter.com/en/portal/dashboard
2. Navigate to your app
3. Go to "Keys and tokens" tab
4. Regenerate all keys:
   - Regenerate Consumer Keys
   - Regenerate Access Token & Secret
5. Update `.env` with new credentials:
   ```
   TWITTER_API_KEY=new-consumer-key
   TWITTER_API_SECRET=new-consumer-secret
   TWITTER_ACCESS_TOKEN=new-access-token
   TWITTER_ACCESS_TOKEN_SECRET=new-access-secret
   ```

---

### 4️⃣ Twitter OAuth 2.0 Client Credentials

**Exposed**:
- Client ID: `YkZmOUZ3NVpoMWw5U2t6enp6XzA6MTpjaQ`
- Client Secret: `siYjgEolQMMJRhSj0-Y0CPFRTGAIjm3qUYRvJoNlf7I5UPFB54`

**Action Required**:
1. Go to: https://developer.twitter.com/en/portal/dashboard
2. Navigate to your app settings
3. Regenerate OAuth 2.0 Client Secret
4. Update `.env`:
   ```
   CLIENT_ID=new-client-id
   CLIENT_SECRET=new-client-secret
   ```

---

### 5️⃣ Notion Integration Token
**Exposed**: `secret_oCsiBagzIl5lXgSqBdwH8fXZ3HKjwoLJ0K5LOpZHtQV`

**Action Required**:
1. Go to: https://www.notion.so/my-integrations
2. Find your integration
3. Generate a new Internal Integration Token
4. Update `.env`: `NOTION_TOKEN=secret_new-token-here`

---

## ✅ Verification Checklist

After rotating all keys:

- [ ] OpenAI API Key rotated and updated in `.env`
- [ ] Airtable Token rotated and updated in `.env`
- [ ] Twitter Consumer Keys rotated and updated in `.env`
- [ ] Twitter Access Tokens rotated and updated in `.env`
- [ ] Twitter OAuth Client Secret rotated and updated in `.env`
- [ ] Notion Token rotated and updated in `.env`
- [ ] Test application with new keys
- [ ] Confirm old keys are revoked/deleted
- [ ] `.env` file is in `.gitignore` (✅ already done)
- [ ] Ready to push to GitHub

---

## 🔒 Security Status After Rotation

Once all keys are rotated:

✅ Old exposed keys are INVALID  
✅ New keys are SECURE  
✅ Git history is CLEAN  
✅ Repository is SAFE for GitHub  

---

## ⚠️ Important Notes

1. **Do NOT skip any keys** - All exposed keys must be rotated
2. **Delete old keys** - Don't just create new ones, revoke the old ones
3. **Test thoroughly** - Make sure the application works with new keys
4. **Never commit .env** - It's already gitignored, keep it that way

---

**Generated**: 2025-10-07  
**Status**: 🔴 KEYS NOT YET ROTATED  
**Next Action**: ROTATE ALL KEYS IMMEDIATELY
