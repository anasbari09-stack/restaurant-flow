# Project spec: Smart Restaurant Ordering & Loyalty System

## Goal
3-day school MVP. One restaurant, table QR ordering, 4 staff dashboards, simple loyalty points.

## Core entities
Restaurant, Server (name, passcode, is_active), Table (qr_token, server FK), MenuItem (category: food/drink/dessert, is_featured, image_url),
Customer (phone, loyalty_points, total_spent), Order (server FK + server_name snapshot), OrderItem (status: NEW/PREPARING/READY/SERVED),
HelpAlert (kind: call/cancel), Review (food_rating, service_rating, overall_rating, problem_item)

Server identity rule: Order.server (FK) is the stable "who" and survives renames/deactivation
(SET_NULL); Order.server_name is the immutable label at order time and the display fallback when
the FK is null (legacy or customer self-orders).

## Customer flow
1. Scan QR -> Table Hub for that table: GET /?table=<qr_token> (data: GET /api/table/?table=<qr_token>)
   From the hub: browse menu, track/add to active order, call serveur, review when served, check loyalty.
2. Browse menu -> GET /api/menu/?table=<qr_token>; add items to cart (client-side state)
3. Submit order: POST /api/orders/
4. Track status, polling every 5-8s: GET /api/orders/<id>/
5. Leave a review after order is served: POST /api/reviews/

## Staff flow
- Login: POST /api/staff/login/
- Kitchen/Drinks/Dessert: GET /api/staff/order-items/?station=<x>&status=<y>
- Update status: PATCH /api/staff/order-items/<id>/
- Admin: GET /api/admin/stats/ (per-serveur performance: ratings, orders handled, revenue — grouped by Order.server FK), all orders, reviews
- Menu management: CRUD /api/admin/menu-items/
- Table management: CRUD /api/admin/tables/ (assign Server per table via dropdown; the
  Server FK is canonical and the view keeps server_name in sync).
- Serveur management (page /staff/admin/servers/): GET /api/admin/servers/ (active only;
  ?include_inactive=1 for all), POST create, PATCH /api/admin/servers/<id>/ (name/passcode/is_active).
  No hard delete — deactivate to preserve history; deactivated serveurs can't log in and are
  excluded from the table dropdown. A table still linked to a now-inactive serveur stays shown.
- Help alerts: POST /api/orders/<id>/help/, resolve via /api/staff/help-alerts/<id>/resolve/

## Serveur flow
- Login by passcode: POST /api/serveur/login/  (stores server_id in session), logout: POST /api/serveur/logout/
- Dashboard: GET /api/serveur/dashboard/ — my tables, active orders, ready-to-serve items, open requests
- Assisted ordering: POST /api/serveur/orders/ — reuses OrderCreateSerializer; attributes the order
  to the acting serveur (server FK + server_name snapshot). For customers who can't scan, have no phone,
  or prefer ordering directly. Phone optional; loyalty still accrues if a phone is given.
- Mark served: PATCH /api/serveur/order-items/<id>/serve/ (READY→SERVED, scoped to own tables)
- Resolve request: PATCH /api/serveur/help-alerts/<id>/resolve/ (scoped to own tables)
- Pages: /serveur/login/ and /serveur/ (dashboard). Assisted ordering reuses the customer
  menu page via /menu/?table=<token>&assisted=1.

## Table sessions (visits)
- A TableSession represents one party's visit; Order.session FK groups a visit's orders (nullable=legacy).
- Automated lazy lifecycle (no background jobs), evaluated on access:
  - Scan (GET /api/table/?table=<token>) auto-opens or joins the table's open session and binds it to
    the browser via the Django session cookie (visit_session_id). Hub shows only that session's orders.
  - Auto-close: finished/empty session idle > 30 min, or hard cap 6 h; a finished session scanned by a
    different/cookieless browser is handed off to a new party. Live (NEW/PREPARING/READY) sessions never idle-close.
  - Manual override: POST /api/tables/<id>/close/ (serveur own tables, or admin) — buttons on the serveur
    dashboard and admin tables page.
- Customer writes (create/append order, help, cancel) require the browser to hold the table's current open
  session, else HTTP 409 "session ended — scan again". Reads survive a close: track old order, review, loyalty.
- Honest limit: a static public QR can't prove presence, so within the idle window a departed link could
  still order; staff Close + the handoff heuristic minimize it. Full prevention is postponed (see below).

## Customer Table Hub
- QR target is a per-table hub (page GET /?table=<token>; data GET /api/table/?table=<token>) with:
  browse menu / order, track current order, add more items, call serveur, leave review (when an order
  is SERVED with no review), view loyalty (GET /api/customer/?phone=).
- Call serveur works before any order exists: POST /api/table/help/ creates a table-level HelpAlert.
  HelpAlert.order is nullable and HelpAlert.table is set for table-level alerts; serveur dashboard and
  admin stats derive the table from order.table or table.
- Order tracking page has a "Back to Table Home" link and a prominent "Leave a review" CTA when SERVED.
- Cancellation policy (tiered, keyed on computed Order.status at request time):
  - NEW  -> auto-cancel immediately (POST /api/orders/<id>/help/ kind=cancel returns cancel_state=canceled).
  - PREPARING -> pending serveur/admin decision (cancel_state=pending).
  - READY/SERVED -> not allowed from the UI.
  Decision: POST /api/orders/<id>/cancel-decision/ {decision: approve|reject} (serveur for own tables, or admin).
  Approve cancels all not-yet-served items; reject leaves the order running. Execution guard refuses if
  any item is already SERVED (never mix served+canceled).
- Cancellation execution = OrderItem.status 'CANCELED'. Order.status is computed over non-canceled items;
  all-canceled -> CANCELED. total_amount excludes canceled, so revenue/loyalty stay correct. Canceled
  items drop out of kitchen station lists automatically.
- Customer sees durable state via OrderDetail.cancel_state (none/pending/canceled/declined): tracking page
  shows pending/declined/canceled clearly; hub offers cancellation only at NEW/PREPARING and shows a
  pending pill otherwise. HelpAlert.kind still distinguishes call vs cancel for staff.
- Postponed: per-item/partial cancellation, cancellation after SERVED, refunds, undo, cancellation analytics.

## Day 1 target (vertical slice)
- Models + Django admin registration
- GET /api/menu/?table=<qr_token>
- POST /api/orders/
- Menu page (HTML + Tailwind CDN + vanilla JS) using the real API, not fake data

## Day 2 target
- Order tracking page (polling)
- Staff dashboards with filtering + status update
- Loyalty point calculation when an order is served

## Day 3 target
- Reviews + admin stats page
- Menu management UI (or Django admin as fallback)
- End-to-end test run + bug fixing

## Phase 1 — shipped (stable baseline)
- Customer menu + cart + order creation, order-append flow
- Order tracking page with polling (auto-stops on SERVED) + UX polish
- Loyalty points awarded once when an order is served
- Staff dashboards (kitchen/drinks/dessert) with status advance
- Admin dashboard: stats + per-serveur performance analytics
- Menu management UI (CRUD, availability, featured, image URL)
- Table management UI (CRUD, per-table server_name assignment)
- server_name snapshot stored on each Order at creation time
- Help-alert flow (customer calls server; staff resolves)
- Test-data cleanup management command

## Phase 2 — new direction (in progress)
Goal: make the workflow feel like a real restaurant product, not a pile of features.
1. Server profile model + passcode login (replaces free-text table assignment).
2. Serveur dashboard: assigned tables, active/ready orders, open service requests.
3. Assisted ordering from the serveur dashboard (reuses order-creation logic).
4. Customer Table Hub landing page after QR scan.
5. Unified service requests (call serveur / cancellation) via HelpAlert.kind.
Order.server FK keeps serveur analytics stable across renames/deactivation.

Postponed: live order reassignment, serveur shift management, item edit/removal after submit,
cancellation execution (CANCELED status — request+acknowledge only for now), password hashing,
multi-restaurant.

## Documentation plan
Keep docs minimal for now (SPEC.md + CLAUDE.md). Add later, not yet:
- README.md — human/project overview and setup
- DECISIONS.md — key technical/product decisions and their rationale