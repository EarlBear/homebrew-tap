# Setup Shopify

> **Context:** This skill walks through the entire Shopify setup — from creating a Partners account and development store, to generating an Admin API access token and configuring credentials in `.env` so the `ebshop` CLI can interact with the Shopify Admin API.

## When to trigger

User says things like:
- "setup shopify", "connect to shopify"
- "configure shopify credentials", "add shopify integration"
- "I want to use shopify with claude", "setup ebshop"
- "create a shopify store", "get started with shopify"

## What it provides

Once configured, the `ebshop` CLI (13 command groups, ~60 commands) can:
- Read/write products, orders, customers, collections, inventory
- Analyze store sales and top products/customers
- Manage themes, pages, blogs, discounts, metafields, webhooks

## Workflow

### Step 1: Check existing setup

Check if Shopify credentials are already configured:

```bash
grep '^SHOPIFY_' .env 2>/dev/null
```

If credentials exist, test connectivity:

```bash
./bin/ebshop shop health
```

If healthy, ask the user if they want to reconfigure or if they're done.

### Step 2: Do you have a Shopify store?

Ask the user:

> Do you already have a Shopify store, or do we need to create one?
>
> - **I have a store** — skip to Step 4
> - **I need a store** — continue to Step 3 (free development store, no credit card)

### Step 3: Create a Shopify Partners account + development store

This is a **manual step** — the user must complete it in their browser.

> You need a free Shopify Partners account and a development store. Here's how:
>
> **3a. Create a Partners account** (skip if you already have one)
>
> 1. Go to https://partners.shopify.com/signup
> 2. Fill in your email, name, and business info
> 3. Verify your email
> 4. Complete your profile
>
> This is completely free. No credit card required.
>
> **3b. Create a development store**
>
> 1. Go to https://dev.shopify.com/dashboard/ (or Partners Dashboard > Stores)
> 2. Click **Create store**
> 3. Enter a store name (e.g., `earlbear-dev`)
> 4. Select a plan — any works for development (you won't be charged)
> 5. Click **Create store**
>
> Your store URL will be `https://earlbear-dev.myshopify.com`.
>
> **3c. (Optional) Add sample data**
>
> Development stores start empty. To test the CLI with real data:
> 1. In Shopify Admin, go to **Settings > Plan** and check if there's a "Populate with sample data" option
> 2. Or manually: **Products > Add product** — create 2-3 test products
> 3. Or: use the Shopify CLI to seed data: `shopify app dev` (optional, requires Node.js)
>
> Let me know when your store is ready and what the `.myshopify.com` URL is.

**Wait for the user to confirm** before proceeding. Use AskUserQuestion.

### Step 4: Get the store URL

Ask the user:

> What's your Shopify store URL? It looks like `https://your-store.myshopify.com`.
>
> You can find it in Shopify Admin at the top of any page, or in Settings > Domains.

Validate the format — must be `https://xxx.myshopify.com` (no trailing slash).

### Step 5: Create a Custom App

This is a **manual step** — the user must complete it in their browser.

> You need a Custom App to generate an Admin API access token. Here's how:
>
> 1. Go to your Shopify Admin: **Settings > Apps and sales channels**
> 2. Click **Develop apps** (top right)
> 3. If prompted, click **Allow custom app development**
> 4. Click **Create an app**
> 5. Name it `EarlBear CLI` and click **Create app**
>
> Official docs: https://help.shopify.com/en/manual/apps/app-types/custom-apps
>
> Let me know when the app is created.

**Wait for the user to confirm** before proceeding. Use AskUserQuestion.

### Step 6: Configure API scopes

This is a **manual step** — the user must complete it in their browser.

> Now configure the API access scopes:
>
> 1. In your new app, click **Configure Admin API scopes**
> 2. Select these scopes (search for each one):
>
> | Scope | Purpose |
> |-------|---------|
> | `read_products` | List and view products |
> | `write_products` | Create, update, delete products |
> | `read_orders` | List and view orders |
> | `write_orders` | Fulfill, cancel orders |
> | `read_customers` | List and view customers |
> | `write_customers` | Create, update customers |
> | `read_inventory` | View inventory levels |
> | `write_inventory` | Adjust inventory quantities |
> | `read_content` | View pages and blogs |
> | `write_content` | Create/edit pages and blog articles |
> | `read_themes` | View and list themes |
> | `read_reports` | View store reports |
> | `read_price_rules` | View discounts |
> | `write_price_rules` | Create/delete discounts |
> | `read_discounts` | View automatic discounts |
> | `write_discounts` | Create/delete automatic discounts |
>
> 3. Click **Save** at the top
>
> Official docs: https://shopify.dev/docs/api/usage/access-scopes
>
> Let me know when scopes are saved.

**Wait for the user to confirm** before proceeding. Use AskUserQuestion.

### Step 7: Save client credentials to .env

Save the Client ID and Client Secret from the Dev Dashboard Settings page to `.env`. **Never echo secrets to the terminal** — write directly to the file.

```bash
# Only add keys that are missing — don't duplicate
grep -q '^SHOPIFY_STORE_URL=' .env 2>/dev/null || echo 'SHOPIFY_STORE_URL=' >> .env
grep -q '^SHOPIFY_CLIENT_ID=' .env 2>/dev/null || echo 'SHOPIFY_CLIENT_ID=' >> .env
grep -q '^SHOPIFY_CLIENT_SECRET=' .env 2>/dev/null || echo 'SHOPIFY_CLIENT_SECRET=' >> .env
grep -q '^SHOPIFY_ACCESS_TOKEN=' .env 2>/dev/null || echo 'SHOPIFY_ACCESS_TOKEN=' >> .env
grep -q '^SHOPIFY_API_VERSION=' .env 2>/dev/null || echo 'SHOPIFY_API_VERSION=2026-01' >> .env
```

Use the Edit tool to set:
- `SHOPIFY_STORE_URL` = the URL from Step 4
- `SHOPIFY_CLIENT_ID` = from Dev Dashboard > Settings > Credentials
- `SHOPIFY_CLIENT_SECRET` = from Dev Dashboard > Settings > Credentials
- `SHOPIFY_API_VERSION` = `2026-01`

### Step 8: Install the app and get the access token

The Dev Dashboard flow uses OAuth to generate the access token. Run the login command in a **separate terminal** (not inside Claude Code — it needs browser access):

```bash
make shopify-cli-login
```

Or equivalently:
```bash
./bin/ebshop auth login
```

This will:
1. Open your browser to the Shopify authorization page
2. You approve the app on your store
3. Shopify redirects to localhost where the CLI captures the auth code
4. The CLI exchanges the code for an access token
5. The token is printed — save it to `.env` as `SHOPIFY_ACCESS_TOKEN`

**IMPORTANT:** Run this in a **SEPARATE TERMINAL**, not inside Claude Code. The flow needs a browser to open.

**Wait for the user to provide the token.** Use AskUserQuestion.

After getting the token, use the Edit tool to set `SHOPIFY_ACCESS_TOKEN` in `.env`.

### Step 9: Build the Docker image

```bash
make shopify-cli-build
```

If the image already exists, this is a no-op (the `bin/ebshop` wrapper auto-builds on first run anyway).

### Step 10: Verify connectivity

Test connectivity:

```bash
./bin/ebshop shop health
```

Expected output:
```json
{
  "status": "ok",
  "store": "Your Store Name",
  "domain": "your-store.myshopify.com",
  "plan": "Developer",
  "api_version": "2026-01"
}
```

If it fails, jump to the Troubleshooting section.

### Step 11: Smoke test

Run a few commands to prove the full CLI works:

```bash
./bin/ebshop shop info                    # Store details
./bin/ebshop product list --limit 5       # Products (may be empty on new dev store)
./bin/ebshop customer list --limit 5      # Customers
./bin/ebshop theme list                   # Themes (every store has at least one)
./bin/ebshop inventory locations          # Fulfillment locations
```

### Step 12: Run secret scan

```bash
make harness-secrets
```

Verify no Shopify tokens leaked into tracked files.

### Step 13: Done

Tell the user:

> Shopify is configured! You can now use the ebshop CLI. Try:
>
> - `./bin/ebshop product list` — list products
> - `./bin/ebshop order list` — recent orders
> - `./bin/ebshop analytics summary` — store revenue summary
> - `./bin/ebshop --help` — see all 13 command groups
> - `/leveraging-shopify-cli` — full command reference
>
> If your dev store is empty, create a few test products in Shopify Admin to have data to work with.

## Key URLs

| Resource | URL |
|----------|-----|
| Partners signup (free) | https://partners.shopify.com/signup |
| Dev Dashboard (create stores) | https://dev.shopify.com/dashboard/ |
| Custom Apps docs | https://help.shopify.com/en/manual/apps/app-types/custom-apps |
| Access tokens guide | https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/generate-app-access-tokens-admin |
| API scopes reference | https://shopify.dev/docs/api/usage/access-scopes |
| Development stores docs | https://shopify.dev/docs/apps/build/dev-dashboard/stores/development-stores |
| GraphQL Admin API reference | https://shopify.dev/docs/api/admin-graphql |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `CONFIG_MISSING` error | Check `.env` has `SHOPIFY_STORE_URL` and `SHOPIFY_ACCESS_TOKEN` set |
| `401 Unauthorized` | Token is invalid or revoked — regenerate in Shopify Admin (uninstall + reinstall the Custom App) |
| `403 Forbidden` | Token is missing required scopes — go to app settings and add missing scopes, then reinstall |
| Store URL wrong | Must be `https://xxx.myshopify.com` with no trailing slash |
| Docker build fails | Run `make shopify-cli-clean` then `make shopify-cli-rebuild` |
| `SHOPIFY_API_VERSION` error | Use `2026-01` (latest stable). Check available versions at https://shopify.dev/docs/api/usage/versioning |
| "Custom app development" not available | In Shopify Admin > Settings > Apps > Develop apps, click "Allow custom app development" first |
| Token starts blank / not `shpat_` | You may have copied the API key instead of the access token — the token is revealed only once after clicking "Install" |
| Empty product/order lists | New dev stores have no data — create test products in Shopify Admin first |
| OAuth redirect fails silently | App URL must be exactly `http://localhost:19456` and Redirect URL `http://localhost:19456/callback`. Uncheck "Embed app in Shopify admin". No trailing slash, no https. |
| OAuth login hangs / browser can't connect | Run `make shopify-cli-login` on the host (not `./bin/ebshop auth login` in Docker). OAuth needs the host's localhost, not the container's. |
| `npm init @shopify/app@latest` prompt | You do NOT need the Shopify app scaffold. Close it. We only need Dev Dashboard app registration + OAuth token. |
| GraphQL rate limit / throttled | Shopify uses cost-based limits (50 pts/sec standard). Reduce `--limit` values or add delays between large queries. |
| Fields returning `null` unexpectedly | API `2026-01` renamed several fields (`totalCount` -> `totalVariants`, `ordersCount` -> `numberOfOrders`, `totalSpentV2` -> `amountSpent`). Rebuild the CLI: `make shopify-cli-rebuild`. |

## Security Notes

- **Credentials live in `.env`** which is gitignored. Never commit them.
- **Custom App tokens never expire** unless you uninstall the app or revoke access.
- **Scope is store-specific** — the token only works for the store it was created on.
- **Rotate by reinstalling**: To rotate the token, uninstall the app in Shopify Admin, then reinstall. A new token is generated.
- To **revoke access entirely**: Uninstall the Custom App from Settings > Apps.
- **Dev stores are free** — no charges, no credit card, no expiration.

## Syncing Credentials to the Agent Repo

The cloud agent (Earl) at `../earlbear-claude-agent/` needs the same Shopify credentials. After configuring `.env` in this repo, copy the Shopify vars to the agent repo's `.env`:

```bash
# Copy Shopify credentials to agent repo
grep '^SHOPIFY_' .env >> ../earlbear-claude-agent/.env
```

Or if the keys already exist in the agent `.env`, update them manually with the Edit tool. Both `.env` files are gitignored — credentials never enter version control.

The agent's `setup-script.sh` installs ebshop via `pip install -e shopify-cli/` and adds `*.myshopify.com,*.shopify.com` to `NO_PROXY`.
