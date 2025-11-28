## PayDemo – Razorpay sandbox ecommerce demo

PayDemo is a production-style Django project that demonstrates a full ecommerce checkout flow with Google OAuth login, Razorpay sandbox payments, webhook inspection, TailwindCSS UI, and developer tooling to replay webhook payloads.

### Highlights
- Django 5 + SQLite for quick local setup
- Email/password + Google OAuth via `django-allauth`
- Product catalog, cart, Razorpay checkout, and verification webhook
- User dashboard with orders + transactions
- Admin tools plus staff-only webhook inspector and developer config panel
- TailwindCSS build pipeline (Tailwind CLI + PostCSS)
- Demo data loader (`loaddemo`) and helper management command for Razorpay orders

### Prerequisites
- Python 3.13+
- Node 18+ (for Tailwind build)
- Razorpay sandbox account + keys
- Google Cloud OAuth client (Web application)

### Quick start
```bash
git clone <repo> paydemo
cd paydemo
python -m venv .venv && .venv\Scripts\activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py loaddemo
python manage.py runserver
```

### Environment variables (`.env`)
| Key | Description |
| --- | --- |
| `SECRET_KEY` | Django secret |
| `DEBUG` | `True/False` |
| `DATABASE_URL` | Defaults to SQLite |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Sandbox keys |
| `WEBHOOK_SECRET` | Razorpay webhook secret |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth |
| `CSRF_TRUSTED_ORIGINS` | comma separated origins |

Set Razorpay + webhook keys either in `.env` or via the staff Developer Config page (`/webhooks/developer/config/`).

### Google OAuth setup
1. Visit [Google Cloud Console](https://console.cloud.google.com/).
2. Create OAuth client (type Web).
3. Authorized redirect URI: `http://localhost:8000/accounts/google/login/callback/`.
4. Copy client ID/secret into `.env`.
5. Runserver, visit `/accounts/login/`, choose `Sign in with Google`.

### Razorpay sandbox flow
1. Create orders via checkout UI (server creates Razorpay order via SDK).
2. Use Razorpay sandbox test card (4111 1111 1111 1111, CVV 111, expiry any future, OTP 123456).
3. Payment success triggers `/payments/verify/`.
4. Razorpay webhook `POST /webhooks/razorpay/` (set url in Razorpay dashboard) stores payloads and reconciles status.

### Tailwind build
```bash
npm install
npm run build:css   # writes static/css/styles.css
npm run watch:css   # dev mode
```
Templates live under `templates/` and include Tailwind utility classes. Inspiration images referenced inside the UI + docs:
- `/mnt/data/95988b23-b88a-4f22-af7b-0206247ebd74.png`
- `/mnt/data/62fd698b-b7af-4e7e-8f54-fb97384b68dc.png`
- `/mnt/data/54f38e86-3711-4c80-9ae5-e7a3978a0273.png`

### Demo data
`python manage.py loaddemo`
- Creates staff user `admin@example.com` (password `adminpass`)
- Adds “Demo Product – ₹499” with image placeholder

### Developer utilities
- `python manage.py create_razorpay_order --order=<uuid>`: creates/refreshes Razorpay order id for an existing order (helpful if manual testing).
- Webhook inspector `/webhooks/inspector/` (staff). View payloads, verify signature, replay events.
- Developer config `/webhooks/developer/config/` (staff). Persist Razorpay + webhook secrets in DB.

### Tests
```bash
python manage.py test
```
Coverage includes:
- Order total + signature helper
- Checkout view hitting Razorpay mock
- Razorpay webhook ingestion + log creation

### Useful commands
```
python manage.py runserver
python manage.py loaddemo
python manage.py create_razorpay_order --order=<uuid>
npm run build:css
```

### Folder structure
```
paydemo/
├── manage.py
├── paydemo/            # project settings/urls
├── store/              # ecommerce app (models, views, utils, commands)
├── webhooks/           # webhook log + inspector
├── templates/          # base + store + webhook templates
├── static/             # Tailwind sources + compiled css
├── requirements.txt
├── README.md
└── .env.example
```

### Notes
- Email backend uses console output to simulate notifications.
- Transactions + webhooks are stored for audit + troubleshooting.
- Replay functionality is limited to staff accounts and increments a replay counter for visibility.

