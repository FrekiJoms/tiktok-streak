import sys

from dotenv import load_dotenv

from utils import auto_send_message, init_browser, login_tiktok, validate_environment

load_dotenv()


if __name__ == "__main__":
    try:
        username, password = validate_environment()
        browser, wait = init_browser()
        login_tiktok(browser, wait, username, password)
        auto_send_message(browser, wait)
    except Exception as exc:
        print(f"Startup failed: {exc}")
        sys.exit(1)
