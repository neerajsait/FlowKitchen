# FlowKitchen

> A full-stack food-service platform with storefront, POS, kitchen, and admin workflows.

## Overview

This repository contains a Flask backend and separate customer and admin frontends, with Docker Compose for local orchestration. Its README and source tree describe an ordering and operations system for food businesses.

## What’s in this repo

- Customer ordering, cart, checkout, and order-status flows
- POS and kitchen display workflows
- Administrative and security features

## Stack

Flask, React, MySQL or SQLite, Redis, Docker Compose.

## Getting started

1. Copy `.env.example` to `.env` and fill in local settings without committing secrets.
2. Start the bundled services from the repository root with `docker compose up --build`.
3. For manual development, use the setup instructions in `backend/`, `frontend-admin/`, and `frontend-customer/`.

## Notes

Payment and production integrations need provider credentials and a reviewed deployment configuration. Check the current code and environment example before using this outside local development.
