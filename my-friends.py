import sys

from dotenv import load_dotenv

from utils import get_all_friends, init_browser, login_tiktok, validate_environment

load_dotenv()


if __name__ == "__main__":
    try:
        username, password = validate_environment()
        browser, wait = init_browser()
        login_tiktok(browser, wait, username, password)
        get_all_friends(browser, wait)
    except Exception as exc:
        print(f"Startup failed: {exc}")
        sys.exit(1)
