# FoodPilot

> A full-stack food-service platform for ordering, point of sale, kitchen operations, and administration.

## Overview

FoodPilot brings a customer storefront together with POS and kitchen workflows and an admin interface. The repository includes separate backend and frontend applications plus a Docker Compose setup.

## What’s in this repo

- Menu browsing, cart and checkout, order tracking, and customer features
- POS and kitchen order workflows
- Admin tools and authentication/security controls

## Stack

Flask, React, MySQL or local SQLite, Redis, Docker Compose; see the app directories for their package and dependency files.

## Getting started

1. Copy `.env.example` to `.env` and set local development values; never commit real secrets.
2. From the repository root, run `docker compose up --build` for the Compose setup.
3. For manual development, follow the backend and frontend instructions in their respective folders.

## Notes

Payment and production integrations require valid provider configuration. Review the environment file and security guidance before exposing the app publicly.
