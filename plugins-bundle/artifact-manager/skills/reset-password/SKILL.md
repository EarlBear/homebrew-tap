# Reset StatiCrypt Password

> **Context:** This skill rotates the StatiCrypt password used to encrypt `dist/public/` content. Password rotation is a **destructive operation** — all previously shared links will stop working until recipients are given the new password.

## When to trigger

User says things like:
- "reset the password", "rotate the password"
- "change the staticrypt password"
- "new password for the site"
- "regenerate the encryption password"

## DANGER: Read before proceeding

Rotating the password has these consequences:

1. **All existing users are locked out.** Anyone who previously accessed the site will be prompted for the new password. The "Remember me" localStorage cache uses salted hashes — a new password invalidates all cached sessions.
2. **You must notify all recipients.** There is no recovery mechanism. If someone has the old password and you rotate, they cannot access any content until they receive the new password.
3. **Full rebuild + republish required.** After rotation you must run `make dist` and `make publish` to re-encrypt and redeploy everything.
4. **Old password cannot be recovered.** The `.env` file is gitignored and not backed up. Once overwritten, the old password is gone.

## Workflow

### Step 1: Confirm intent

Before doing anything, clearly warn the user:

> Rotating the StatiCrypt password will **lock out all current users**. You will need to share the new password with everyone who needs access. Are you sure you want to proceed?

**Do not proceed without explicit confirmation.**

### Step 2: Show current state

```bash
grep STATICRYPT_PASSWORD .env | cut -c1-30
```

Show a truncated preview so the user knows a password exists (don't show the full password unless asked).

### Step 3: Generate and write new password

Use the password generator script (encodes all security best practices):

```bash
./scripts/generate-password.sh --write
```

This will:
- Generate a cryptographically secure 36-character base64 password (~216 bits entropy)
- Back up the current `.env` to `.env.bak`
- Write the new password to `.env`
- Print next steps

For a custom length (minimum 16 per StatiCrypt recommendation):

```bash
./scripts/generate-password.sh --write 48
```

To check the current password strength without changing it:

```bash
./scripts/generate-password.sh --check
```

See `scripts/generate-password.sh --help` for full usage and security rationale.

### Step 5: Rebuild and republish

```bash
rm -rf dist/
make dist
make dist-validate
make dist-preview
```

Wait for user to confirm preview looks good, then:

```bash
make publish
```

Or tell the user to run `! make publish` for interactive confirmation.

### Step 6: Distribute the new password

Remind the user to:
1. **Share the new password** with all authorized recipients via a secure channel (not email — use a password manager sharing feature, Signal, or similar)
2. **Delete the .env.bak** file once confirmed: `rm .env.bak`
3. **Update any password manager entries** where the old password was stored
4. **Never commit the password** to git, Slack messages, emails, or any logged system

### Step 7: Verify

After publishing with the new password:
1. Open the site in an incognito/private browser window
2. Confirm the old password does NOT work
3. Confirm the new password DOES work
4. Check "Remember me" works on subsequent page loads

## Password sharing best practices

- Use a **password manager** (Bitwarden, 1Password) to share credentials — never plaintext channels
- If sharing verbally, break into 4-char groups: `tydA 6+PW uEdg 8B8g +XHL AQ9q qbg4 DOAR Mk4V`
- Consider creating a **short memorable passphrase** as an alternative if the audience is non-technical (e.g., `correct-horse-battery-staple-espresso-bear`) — but note this trades some entropy for usability
- StatiCrypt's "Remember me" checkbox stores the salted+hashed password in localStorage, so users only need to enter it once per browser

## Security notes

- The password is the **only** protection. There is no second factor, no user accounts, no rate limiting on the client-side decryption.
- StatiCrypt uses AES-256-CBC with 600k PBKDF2-SHA256 iterations for key derivation. This is strong but the full ciphertext is publicly accessible.
- A 36-char base64 password provides ~214 bits of entropy — infeasible to brute-force even with the ciphertext available.
- **Never** store the password in git, CI/CD logs, Slack, email, or any system that retains history.
