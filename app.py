from pathlib import Path

# Make this module behave like a package so `app.main` resolves on Vercel.
__path__ = [str(Path(__file__).resolve().parent / "app")]

from app.main import app
