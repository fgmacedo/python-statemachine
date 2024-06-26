from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = True

ROOT_URLCONF = "app"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "workflow",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "TEST": {
            "NAME": "testdb.sqlite3",
        },
    }
}

WSGI_APPLICATION = "core.wsgi.application"
