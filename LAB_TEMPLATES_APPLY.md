# Lab result template changes – how to see them

The lab result form (FBC, LFT, Prolactin/single, etc.) is chosen from the **ordered test** in `hospital/utils_lab_templates.py`. For the updated logic to run, the app must load the new code.

## If you run with **Docker** (docker-compose)

Restart the web service so Gunicorn reloads:

```bash
docker-compose restart web
```

If you added or changed Python files (e.g. `utils_lab_templates.py`), rebuild and start:

```bash
docker-compose up -d --build web
```

## If you run with **python manage.py runserver**

Stop the server (Ctrl+C) and start it again:

```bash
python manage.py runserver
```

## After restart

1. Hard-refresh the browser (Ctrl+F5 or Cmd+Shift+R) so the updated lab report page is loaded.
2. Open **Enter Results** for a test (e.g. Prolactin for Nana Acheampong).
3. The page subtitle should show **Form: single** (or fbc, lft, etc.) and the correct form (single value for Prolactin, FBC grid for FBC, etc.).

If you still see the wrong form, check the line under the title: it shows **Form: &lt;test_type&gt;** so you can confirm what the server sent.
