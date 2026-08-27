# 🛒 E-Commerce System Design with Django & Python
## 📖 Official Companion Codebase for the Book: *E-Commerce System Design*

Welcome to the companion source code repository for the book **E-Commerce System Design: Architecting Resilient, Concurrency-Safe Backends with Django REST Framework and Python**.

---

## 🗺️ Chapter Navigation & Git Branches

This repository is tagged chapter-by-chapter so you can follow along with the exact state of the project as you read:

| Branch / Tag | Chapter | Description |
| :--- | :--- | :--- |
| **`chapter-01`** | **Chapter 1** | **Monolithic Backend Architecture & Django Project Design** |
| `chapter-02` | Chapter 2 | Security Hardening, Throttling & Caching Infrastructure |
| `chapter-03` | Chapter 3 | Production Deployment & Server Infrastructure Setup |
| `chapter-04` | Chapter 4 | Custom User Model Engineering |
| `...` | `...` | *(Subsequent chapters)* |

---

## 🏗️ Chapter 1 Architecture Overview

In Chapter 1, we scaffold our **Modular Monolith** backend, establishing clean domain boundaries inside a single Django project:

```text
ecommerce-system-design-django/
├── core/                     # Project Configuration (settings, urls, wsgi, asgi)
├── users/                    # Customer Accounts & Auth Domain
├── catalog/                  # Products, Categories & Reviews Domain
├── orders/                   # Carts, Checkout & Fulfillment Domain
├── home/                     # Dynamic Landing Page & Site Settings Domain
├── manage.py                 # Command-line administrative runner
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variables template
```

---

## ⚡ Quick Start & Local Setup

### 1. Clone the Repository & Checkout Chapter 1
```bash
git clone https://github.com/your-username/ecommerce-system-design-django.git
cd ecommerce-system-design-django
git checkout chapter-01
```

### 2. Set Up Python Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
venv\Scripts\Activate.ps1
# On Windows (CMD):
venv\Scripts\activate.bat
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
# On Linux/macOS:
cp .env.example .env

# On Windows:
copy .env.example .env
```

### 5. Run Initial Database Migrations
```bash
python manage.py makemigrations users
python manage.py migrate
```

### 6. Create a Superuser & Run the Development Server
```bash
python manage.py createsuperuser
python manage.py runserver
```

Open your browser and navigate to:
* **Admin Dashboard**: `http://127.0.0.1:8000/admin/`
* **API Root**: `http://127.0.0.1:8000/api/`

---

## 📘 About the Book
*E-Commerce System Design* is a practical, engineering masterclass that moves beyond basic tutorials. It guides you step-by-step through building a battle-tested, failure-resilient backend handling atomic inventory locks (`select_for_update`), double-entry credit ledgers, dynamic GST invoicing, payment webhooks, and third-party logistics integrations.
