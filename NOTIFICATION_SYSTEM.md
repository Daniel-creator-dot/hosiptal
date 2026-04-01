# Lab Result Notification System

## What it does
When a **lab test is marked complete** (Laboratory → update result status to "Complete"):
- **Doctors** (ordering doctor + all doctors), **nurses**, and **front desk** (receptionists) receive an **in-app notification**.
- A **popup card** appears (top-right) with title, message, and **View result** button.
- The **topbar bell** shows unread count; clicking it opens a dropdown with recent notifications and **Mark all read** / **View all notifications**.

## For users
- **Bell icon** (top bar): Click to see recent notifications and mark all read.
- **Popup**: Click **View result** to open the lab result (and mark that notification read), or dismiss with X.
- **View all**: Opens `/hms/notifications/` for full history.

## Technical summary
- **Backend:** `hospital/signals.py` – `handle_lab_result_ready` creates `Notification` records for doctors, nurses, receptionists when `LabResult.status` becomes `completed`.
- **API:** `GET /hms/api/notifications/` – returns `unread_count` and recent notifications (with `link` for lab/imaging).
- **Mark read:** `POST /hms/notifications/<id>/read/` (single), `POST /hms/notifications/mark-all-read/` (all).
- **UI:** `hospital/templates/hospital/base.html` – tray, cards, bell, dropdown; styles in `hospital/static/hospital/css/common_styles.css` (`.hms-notification-*`).
- **Polling:** Every 40 seconds; first run 1.5 s after page load.

## Docker
- Code is live via volume mount (`.:/app`). After pulling changes, run **`DOCKER_APPLY_CHANGES.bat`** (or `docker compose restart web`) to apply.
- For a full image rebuild, use **`UPDATE_DOCKER_AND_DATABASE.bat`**.
