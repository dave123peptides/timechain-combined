# Combined site: launch runbook (for David)

## Status, 2026-10-22 evening

Steps 0 to 5 below are DONE (run from the CLI in David's session):

- GitHub: `dave123peptides/timechain-combined`, branch `combined-site`.
- Neon: project `timechain-combined` (id `raspy-water-53643716`,
  aws-us-east-1, Postgres 18) in David's own Neon org. Its connection
  string lives only on Vercel as the API's `DATABASE_URL`.
- Vercel `timechain-combined-api`: Root Directory `services/api`,
  production at https://timechain-combined-api.vercel.app. Build ran all
  migrations, both seeds (35+6 products, 52 pens + 48 vials) and the COA
  sync. Env set: DATABASE_URL, PUBLIC_SITE_URL, API_CORS_ORIGINS (www +
  the web alias), ADMIN_BASIC_AUTH_USER, FULFILLMENT_MODE, CHECKOUT_ENABLED.
- Vercel `timechain-combined-web`: Root Directory `apps/web`, Next.js,
  production at https://timechain-combined-web.vercel.app. Env set:
  NEXT_PUBLIC_API_BASE_URL, API_INTERNAL_BASE_URL, ADMIN_BASIC_AUTH_USER.
- Both projects deploy from the CLI (`vercel deploy --prod --yes
  --project <name>` from the repo root; the root `.vercel/` link may point
  at either, the flag wins). Neither is connected to GitHub yet, so a
  push alone changes nothing live.

Redesign deployed the same evening (commits 11e00dd, 4c45eae): the B2B
look, no prices, and the order request flow. Two more API settings exist,
both unset in production so far: `CATALOG_PRICES_PUBLIC` (keep off until
the wholesale sheet; the web's `NEXT_PUBLIC_PRICING_VISIBLE` is its
twin) and `ORDER_REQUEST_WEBHOOK_URL` (a GHL inbound webhook; until set,
requests are stored only and read at /admin/requests, which needs the
admin password below).

Still David's:

1. Review at https://timechain-combined-web.vercel.app. The gate is on
   with the code default password (`health123`) because
   `SITE_ACCESS_PASSWORD` is unset; set your own or remove the gate in
   the web project's env before launch (needs a redeploy).
2. `ADMIN_BASIC_AUTH_PASSWORD` on BOTH projects (same value) if you want
   /admin; unset, admin is simply locked.
3. `NEXT_PUBLIC_BOOKING_URL` on the web project when the scheduling link
   exists, then redeploy the web project. DONE 2026-10-23 with
   https://cal.com/timechain/30min. Booking is the site's primary action:
   every Book a meeting button goes to `/book`, which embeds a cal.com
   link through Cal.com's own inline script (CalEmbed.tsx, light theme
   via the embed config; a bare frame follows the visitor's system theme)
   and also links out to it. Any other provider gets a plain frame. If the provider
   refuses to load in a frame, add `NEXT_PUBLIC_BOOKING_EMBED=false` and
   the page links out only. Until the link is set, `/book` offers email.
   To set it from the CLI:

   ```sh
   vercel env add NEXT_PUBLIC_BOOKING_URL production --project timechain-combined-web --value "<the link>" --yes
   vercel deploy --prod --yes --project timechain-combined-web
   ```
4. Step 6: move the domain (below).
5. Team plan: still Hobby.

---


Everything below needs the Vercel, Neon and GitHub accounts, so it is
yours to run. The code side is done on branch `combined-site`.

## 0. Clean the fork's Vercel links first

The fork carried the pens site's link files, so a `vercel` command run
in here right now would deploy to the LIVE `tcp-api` project. Before
anything else:

```sh
cd ~/Desktop/timechain-combined
rm -rf .vercel services/api/.vercel .vercel-project-api.json
```

## 1. GitHub

Create an empty private repo `dave123peptides/timechain-combined`, then:

```sh
git push -u origin combined-site      # origin is already git@github.com:dave123peptides/timechain-combined.git
```

(Commit author is david@timechainpeptides.com via ~/.gitconfig; Vercel
blocks deploys from commits without a real author email.)

## 2. Neon

Create a new project (your own Neon account, like the other two sites;
suggested name `timechain-combined`). Copy its connection string. Do not
reuse the vial site's or the pens site's database.

## 3. Vercel API project

Suggested name `timechain-combined-api`, Root Directory `services/api`.
The `vercel.json` there runs migrations, both catalog seeds and the COA
manifest sync inside the build. Environment variables (Production):

```
DATABASE_URL=<Neon connection string>
ENVIRONMENT=production
PUBLIC_SITE_URL=https://www.timechainpeptides.com
API_CORS_ORIGINS=https://www.timechainpeptides.com
ADMIN_BASIC_AUTH_USER=<pick>
ADMIN_BASIC_AUTH_PASSWORD=<pick>
FULFILLMENT_MODE=manual
CHECKOUT_ENABLED=true          # yes, true: false blanks the catalog. ORDERING_ENABLED stays unset (off).
```

Not needed on this site: payment keys (OpenNode, Whop, PayPal), Google
Sheets, GHL. Leave them unset.

```sh
cd ~/Desktop/timechain-combined/services/api
vercel link            # create a NEW project when asked
vercel --prod --yes
curl -s https://<api-domain>/shop/filter-options     # {"categories":[...],"formats":["lyophilized","pen"]}
curl -s 'https://<api-domain>/shop/products?format=pen' | head -c 300
```

## 4. Vercel web project

Suggested name `timechain-combined-web`, Root Directory `apps/web`,
framework Next.js (link from the repo root, as the vial site is).
Environment variables:

```
NEXT_PUBLIC_API_BASE_URL=https://<api-domain>
API_INTERNAL_BASE_URL=https://<api-domain>
ADMIN_BASIC_AUTH_USER=<same as the API>
ADMIN_BASIC_AUTH_PASSWORD=<same as the API>
SITE_ACCESS_PASSWORD=<set while you review; remove to open the site>
NEXT_PUBLIC_BOOKING_URL=<the scheduling link, once you have it>
```

`NEXT_PUBLIC_ORDERING_ENABLED` stays unset. A `NEXT_PUBLIC_*` change
needs a redeploy to take effect.

```sh
cd ~/Desktop/timechain-combined
vercel link            # NEW project, root directory apps/web
vercel --prod --yes
```

## 5. Check before the domain moves

On the `<web>.vercel.app` URL: pass the gate, confirm the Pens | Vials
toggle, a dual product page (bpc-157: Format row with Pen and Vial),
`/contact` (Email us to book a meeting, or Book a meeting once the link
is set), and that `/cart` and `/checkout` land on `/contact`.

```sh
curl -sD - -o /dev/null -H "Origin: https://www.timechainpeptides.com" https://<api-domain>/shop/products | grep -i access-control-allow-origin
```

## 6. Move the domain

www.timechainpeptides.com and the apex currently sit on the vial site's
`timechain-storefront` project (DNS already points at Vercel, so the
registrar is untouched). In the Vercel dashboard, remove both domains
from `timechain-storefront` and add them to `timechain-combined-web`;
Vercel moves them within the team. The vial projects stay as they are,
so rollback is adding the domains back.

## 7. Afterwards

- Set `NEXT_PUBLIC_BOOKING_URL` and redeploy the web project when the
  scheduling link exists.
- The team was on the Hobby plan on 2026-09-08 (no commercial use);
  check it before launch.
- buytcp.com and the vial repo are untouched by this project; decide
  separately whether the pens site stays up.
