# 🛒 E-Commerce System Design with Django & Python
## 📖 Official Companion Codebase for the Book: *E-Commerce System Design*

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-092E20.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15%2B-red.svg)](https://www.django-rest-framework.org/)
[![Celery](https://img.shields.io/badge/Celery-5.4%2B-green.svg)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-In--Memory-DC382D.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Welcome to the official companion source code repository for **E-Commerce System Design: Architecting Resilient, Concurrency-Safe Backends with Django REST Framework and Python** (Volume 1).

This repository contains the complete, production-grade backend engineered throughout the book. Every chapter is tagged with an isolated Git branch and tag so you can follow along with the exact state of the project as you read.

---

## 📚 Get the Book

| Edition | Direct Store Link |
| :--- | :--- |
| 📕 **Paperback Edition** | [Buy on Amazon](https://amzn.in/d/01ufcEz6) |
| 📱 **Kindle E-Book** | [Buy on Amazon](https://amzn.in/d/01ufcEz6) |

> 💡 *This codebase is free to use, clone, and explore. The book provides the architectural blueprints, mathematical invariants, security failure modes, and step-by-step reasoning behind every line of code.*

---

## 🏛️ System Capabilities & Architectural Invariants

* **Modular Monolith Architecture**: Domain-driven boundaries (`users`, `catalog`, `orders`, `home`, `core`) with high cohesion and low coupling.
* **Concurrency-Safe Financial Ledgers**: Double-entry bookkeeping for store credits with immutable transaction rows and pessimistic row locking (`select_for_update`).
* **FIFO Inventory Allocation**: First-In, First-Out batch cost tracking and strict over-allocation defenses under high-frequency checkout races.
* **Variant Matrix & Dynamic Pricing**: Flexible SKU-level pricing, attribute combinations, and real-time subtotal resolution.
* **Automated WebP Image Pipeline**: Lossless/lossy image optimization, dynamic thumbnailing, and physical cascade storage pruning.
* **Persistent Cart Management**: Guest session carts, authenticated customer synchronization, and collision-free guest-to-user merges.
* **Singleton Dynamic Configuration**: Real-time store settings, zone-based shipping rules, free-shipping thresholds, and COD deposits.
* **Asynchronous Recovery Engine**: Celery + Redis periodic task scheduling, multipart HTML/text email pipelines, and tamper-proof cryptographic recovery deep links.

---

## 🗺️ Chapter Navigation & Git Branches

Switch to any chapter's exact codebase snapshot using `git checkout <branch-name>`:

| Part | Branch / Tag | Chapter | Core Focus |
| :--- | :--- | :--- | :--- |
| **Part I** | `chapter-01` | **Chapter 1** | Monolithic Backend Architecture & Django Project Design |
| | `chapter-02` | **Chapter 2** | Security Hardening, Throttling & Caching Infrastructure |
| | `chapter-03` | **Chapter 3** | Production Deployment & Server Infrastructure Setup (Nginx + Gunicorn) |
| **Part II** | `chapter-04` | **Chapter 4** | Custom User Model Engineering & PBKDF2 Password Hashing |
| | `chapter-05` | **Chapter 5** | Cryptographic 6-Digit OTP Email Verification & Activation |
| | `chapter-06` | **Chapter 6** | Cryptographic Password Reset Architecture (Stateless Tokens) |
| | `chapter-07` | **Chapter 7** | Shipping Address Subsystem & Customer Default Logic |
| **Part III** | `chapter-08` | **Chapter 8** | Double-Entry Financial Ledger & Immutable Wallet Mechanics |
| | `chapter-09` | **Chapter 9** | FIFO Inventory Ledger & Batch Cost Accounting |
| | `chapter-10` | **Chapter 10** | Concurrency Control, Deadlock Prevention & Row-Level Locking |
| **Part IV** | `chapter-11` | **Chapter 11** | High-Performance Product Catalog & Dynamic Filtering |
| | `chapter-12` | **Chapter 12** | Product Variant Architecture (Matrix vs. SKU-Level Tracking) |
| | `chapter-13` | **Chapter 13** | Database Denormalization & Real-Time Stock Synchronization |
| | `chapter-14` | **Chapter 14** | Automated WebP Image Compression & Storage Optimization |
| | `chapter-15` | **Chapter 15** | Verified Product Reviews, Rating Aggregations & Customer Wishlists |
| **Part V** | `chapter-16` | **Chapter 16** | Persistent Cart Management & Guest-to-User Merging Logic |
| | `chapter-17` | **Chapter 17** | Singleton Configuration & Zone-Based Shipping Logic |
| | `chapter-18` | **Chapter 18** | Automated Abandoned Cart Recovery & Celery Background Tasks |

---

## 🏗️ Project Structure

```text
ecommerce-system-design-django/
├── core/                     # Project Configuration (settings, urls, celery, wsgi)
├── users/                    # Customer Accounts, Auth, Addresses & Wallet Ledgers
├── catalog/                  # Products, Variants, Categories, Reviews & Wishlists
├── orders/                   # Shopping Carts, Shipping Rates, Celery Tasks & Recovery
├── home/                     # Dynamic Landing Page & Singleton Site Settings
├── media/                    # Local media assets (WebP optimized catalog images)
├── manage.py                 # Django administrative runner
├── requirements.txt          # Production dependencies
└── .env.example              # Environment variables template
```

---

## ⚡ Quick Start & Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/SamwitAdhikary/Ecommerce-System-Design-Django.git
cd Ecommerce-System-Design-Django
```

### 2. Set Up Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
venv\Scripts\Activate.ps1
# On Windows (CMD):
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
# On Linux/macOS:
cp .env.example .env
# On Windows:
copy .env.example .env
```

### 4. Run Migrations & Start Local Development
```bash
python manage.py makemigrations users catalog orders home
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open your browser at:
* **Admin Dashboard**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
* **REST API Root**: [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)

---

## 📘 About the Author & Support

If this repository helps you build more resilient Django systems, please consider:
* ⭐ **Starring the repository** on GitHub
* 📖 Leaving an honest review on [Amazon](https://amzn.in/d/01ufcEz6)
