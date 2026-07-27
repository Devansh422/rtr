# PRD, #RightToRecall Movement Website

## Problem Statement
A vibrant, Gen-Z, mobile-first movement website for the #RightToRecall Movement, a NON-PARTISAN civic movement. Educates visitors in under 3 minutes and converts them into supporters, volunteers, and digital ambassadors. Primary conversion: "Join the RightToRecall Movement."

## Tech / Architecture
- Frontend: React 19 + Tailwind + shadcn/ui, framer-motion (scroll reveals, masked hero, parallax), lenis (smooth scroll), react-fast-marquee.
- Backend: FastAPI + MongoDB. Content served from JSON files at `/app/backend/content/*.json` via `/api/content/*`. Form submissions persisted to MongoDB.
- Design system: "Optimistic Civic Blueprint", Volt Yellow (#D4FF00) + Cobalt Blue, Clash Display + Satoshi fonts, rounded-3xl cards, pill buttons, light + dark mode.

## Personas
- First-time / young voter wanting to understand recall quickly.
- Would-be volunteer / ambassador ready to act.
- Journalist / partner exploring the movement.

## Core Requirements (static)
- Pages: Home, About, Campaigns, Blog/News, Volunteer, Resources, Contact.
- Features: dark/light mode, JSON-powered content, blog search + category filter, FAQ accordion, newsletter signup, share buttons, scroll progress bar, sticky navbar, back-to-top, floating Join CTA, SEO/OG/Twitter meta, robots.txt, sitemap.xml.
- Tone: hopeful, non-partisan, fact-based, action-oriented.

## Implemented (2026-07-27)
- Full 7-page site with kinetic masked hero, parallax hero image, editorial marquee, numbered manifesto chapters, animated timeline.
- Backend content endpoints (campaigns, blogs, faq, news, testimonials, resources) + stats.
- Working forms: Join (dialog), Volunteer, Contact, Newsletter, Supporters, all persist to MongoDB.
- Dark/light theme (next-themes), scroll widgets, share buttons.
- SEO meta, OG/Twitter cards, robots.txt, sitemap.xml.
- Tested end-to-end: backend 100% (13 pytest), frontend 100%.
- Fixed: scroll-reveal stagger animation (cards were stuck at opacity 0), refactored to self-triggering whileInView with index delay.

## Content editing (no code)
Edit JSON files in `/app/backend/content/` (campaigns.json, blogs.json, faq.json, news.json, testimonials.json, resources.json). Changes appear on refresh, no rebuild needed.

## Backlog / Next
- P1: Newsletter/volunteer email delivery via Resend or SendGrid.
- P1: Individual blog article detail page (backend endpoint exists).
- P2: Admin dashboard to view volunteer/contact submissions.
- P2: Real downloadable PDF assets for Resources.
- P2: Multi-language (Hindi + regional) support.

## Update (2026-07-27), Campaign Flow + Knowledge Hub
- Campaign Flow (/join): 4 steps, 30s animated explainer -> pledge -> details (name/state/city/email/mobile optional) -> thank-you. Generates Movement ID (RTR-YYYY-XXXXXX), downloadable digital certificate (html-to-image), verified badge, auto-newsletter subscribe, WhatsApp/X/Facebook/Instagram share. All "Join" CTAs now route to /join.
- Knowledge Hub (/knowledge): What is RTR, recall across jurisdictions, Myth vs Fact, FAQ, research articles, downloads.
- New backend: POST /api/supporters (movement_id + city/mobile/pledge + auto-newsletter), GET /api/content/jurisdictions, GET /api/content/myths.
- Removed all fabricated numbers (hero stats, campaign progress bars, invented news/blog counts).
- Logo => "RightToRecall / MOVEMENT" top-left. Real socials + email socialservant@gmail.com.
- Tested: backend 100% (16 pytest), frontend 100% (iteration_2).
