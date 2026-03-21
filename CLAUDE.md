# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Tests
python manage.py test

# Custom management commands
python manage.py link_clients          # Link Django users to WfClient records
python manage.py update_overdue_status # Update overdue order statuses
python manage.py limpar_status_erp     # Clear ERP status records
```

## Environment

Requires a `.env` file with:
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- MySQL: `MYSQLDATABASE`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLHOST`, `MYSQLPORT`
- Production uses `DATABASE_URL` (Railway, auto-detected via dj-database-url)

## Architecture

**B2B e-commerce platform** for wholesale ordering with multi-state pricing (SP/ES), ERP integration, and order management.

### Apps & Key Files
- `app/` — Django project config (settings, URLs, WSGI)
- `wefixhub/` — Single main app with all business logic
  - `models.py` — All data models
  - `views.py` — All views (~2000+ lines, function-based)
  - `utils.py` — Utilities: dashboards, Excel/PDF generation, ERP processing
  - `forms.py` — Django forms for clients, addresses, orders
  - `admin_urls.py` — Admin-specific URL routes
  - `templatetags/` — Custom tags: `format_tags.py`, `carrinho_extras.py`
- `templates/` — Root-level HTML templates
- `static/` — CSS, JS, images

### Core Models
- `WfClient` — Business clients (linked 1:1 to Django `User`); has `client_state` (SP/ES) which drives pricing
- `Product` — Products with `product_value_sp` and `product_value_es` for state-specific pricing
- `Pedido` — Orders with statuses: `RASCUNHO → PENDENTE → FINALIZADO → ENTREGUE`
- `ItemPedido` — Order line items
- `Carrinho` / `ItemCarrinho` — Shopping cart (newer feature)
- `VendaReal` — Real sales data imported from ERP
- `StatusPedidoERP` — ERP order status tracking
- `ItemPedidoIgnorado` — Failed order items (stock issues); triggers wishlist alerts
- `SugestaoCompraERP` — Purchase suggestions derived from ERP data

### Key Patterns
- **Auth:** `@login_required` / `@staff_member_required`; `is_staff` separates admin from client users
- **State pricing:** `cliente.client_state.uf_name` determines whether SP or ES price is shown
- **HTMX:** Used for dynamic interactions via `django-htmx` middleware
- **File processing:** pandas + openpyxl for Excel import/export; pdfplumber for PDF parsing; fpdf2 for PDF generation
- **ERP integration:** Bulk uploads via CSV/Excel; `VendaReal` and `StatusPedidoERP` models sync data
- **Deployment:** Gunicorn + WhiteNoise on Railway
