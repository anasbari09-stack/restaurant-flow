# Smart Restaurant Ordering & Loyalty System

## Stack
- Backend: Django + Django REST Framework (DRF)
- DB: SQLite
- Frontend: Vanilla JS + HTML + Tailwind CSS via CDN (no npm, no build step)
- Real-time updates: polling every 5-8s, NOT WebSockets
- No React in this project — explicitly out of scope for now

## Architecture decisions
- Status (New/Preparing/Ready/Served) lives on OrderItem, not Order
- Order.status is a computed property derived from its items, not a stored DB column
- Customers identified by phone number only — no login/password for customers
- Staff have simple login (admin/kitchen/drinks/dessert roles)
- Serveurs are a Server model (name, passcode, is_active) with their own passcode login
  (session server_id) — kept simple, no password hashing for v1
- Tables are assigned to a Server (Table.server FK), not free text
- Order.server (FK, SET_NULL) is the stable serveur identity for analytics; Order.server_name
  remains an immutable snapshot/display fallback for null-FK or legacy orders
- Assisted ordering reuses OrderCreateSerializer; the serveur endpoint injects the acting Server
  so the order is attributed to them. The public customer order path stays untouched.
- Admin stats aggregate per-serveur performance by the Order.server FK (name as fallback)

## Frontend conventions
- Tailwind via CDN: <script src="https://cdn.tailwindcss.com"></script>
- One JS file per page, vanilla fetch() for API calls, simple state object (no framework)
- Build each page against the real API from day one — never hardcode fake JSON

## Out of scope (v1) — do not build unless I explicitly ask
- Online payment integration
- WebSockets / push notifications
- Customer accounts with passwords
- Image upload pipeline (use static image URLs)
- Multi-restaurant onboarding UI
- Reservations, inventory, kitchen printers
- Loyalty tiers/redemption — just simple point accumulation
- React or any frontend framework

## Workflow rules
- Always show me a plan before writing code for a new feature. Wait for my approval.
- Run `python manage.py makemigrations && python manage.py migrate` after any model change
- After every new endpoint, show me how to test it (curl command or Django admin steps)
- Never expand scope beyond SPEC.md without asking me first
- Do not commit db.sqlite3, __pycache__, or .pyc files (see .gitignore) — source + migrations only