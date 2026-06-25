# Project spec: Smart Restaurant Ordering & Loyalty System

## Goal
3-day school MVP. One restaurant, table QR ordering, 4 staff dashboards, simple loyalty points.

## Core entities
Restaurant, Table (qr_token, server_name), MenuItem (category: food/drink/dessert, is_featured, image_url),
Customer (phone, loyalty_points, total_spent), Order (server_name snapshot), OrderItem (status: NEW/PREPARING/READY/SERVED),
HelpAlert, Review (food_rating, service_rating, overall_rating, problem_item)

## Customer flow
1. Scan QR -> menu page for that table: GET /api/menu/?table=<qr_token>
2. Add items to cart (client-side state)
3. Submit order: POST /api/orders/
4. Track status, polling every 5-8s: GET /api/orders/<id>/
5. Leave a review after order is served: POST /api/reviews/

## Staff flow
- Login: POST /api/staff/login/
- Kitchen/Drinks/Dessert: GET /api/staff/order-items/?station=<x>&status=<y>
- Update status: PATCH /api/staff/order-items/<id>/
- Admin: GET /api/admin/stats/ (incl. per-serveur performance), all orders, reviews
- Menu management: CRUD /api/admin/menu-items/
- Table management: CRUD /api/admin/tables/ (assign server_name per table)
- Help alerts: POST /api/orders/<id>/help/, resolve via /api/staff/help-alerts/<id>/resolve/

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