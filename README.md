# Frame: Django image gallery with authentication

Users sign up, log in, and see a masonry image gallery with a lightbox viewer.
Logged-in users can upload photos and delete their own. Anonymous visitors are
redirected to the login page.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Pages

| URL            | Purpose                                   |
|----------------|-------------------------------------------|
| `/signup/`     | Create an account (auto-login afterwards) |
| `/login/`      | Log in                                    |
| `/`            | Gallery (login required)                  |
| `/upload/`     | Add a photo (login required)              |
| `/admin/`      | Django admin                              |

## Production notes

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` and `DJANGO_ALLOWED_HOSTS`.
Serve `/media/` with your web server or cloud storage, and run
`python manage.py collectstatic`.
