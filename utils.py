import csv
import importlib
import importlib.util
import os
import re
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

FRIENDS_CSV = "friends.csv"
SELENIUM_CACHE_DIR = os.path.join(".selenium")
REQUIRED_ENV_VARS = (
    "TIKTOK_USERNAME",
    "TIKTOK_PASSWORD",
    "MESSAGE",
)


def get_captcha_solver():
    if importlib.util.find_spec("ocacaptcha") is None:
        return None

    module = importlib.import_module("ocacaptcha")
    return getattr(module, "oca_solve_captcha", None)


def validate_environment():
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {joined}")

    return os.getenv("TIKTOK_USERNAME"), os.getenv("TIKTOK_PASSWORD")


def is_headless_enabled():
    return os.getenv("HEADLESS", "true").strip().lower() not in {"0", "false", "no"}


def get_login_wait_seconds():
    return int(os.getenv("LOGIN_WAIT_SECONDS", "180"))


def has_working_captcha_key():
    api_key = os.getenv("CAPTCHA_API_KEY", "").strip()
    return bool(api_key) and api_key != "api_key_ocacaptcha"


def get_chrome_user_data_dir():
    return os.getenv("CHROME_USER_DATA_DIR", "").strip()


def get_chrome_profile_directory():
    return os.getenv("CHROME_PROFILE_DIRECTORY", "").strip()


def get_default_chrome_user_data_dir():
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    if not local_appdata:
        return ""
    return os.path.join(local_appdata, "Google", "Chrome", "User Data")


def should_use_existing_session():
    return os.getenv("USE_EXISTING_SESSION", "false").strip().lower() in {"1", "true", "yes"}


def is_logged_in(browser):
    current_url = browser.current_url.lower()
    return "tiktok.com" in current_url and "/login" not in current_url and "/challenge" not in current_url


def load_friends():
    if not os.path.exists(FRIENDS_CSV):
        return []

    with open(FRIENDS_CSV, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [row["Username"] for row in reader if row.get("Username")]


def append_friend(username):
    if username in set(load_friends()):
        return False

    file_exists = os.path.exists(FRIENDS_CSV)
    with open(FRIENDS_CSV, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists or file.tell() == 0:
            writer.writerow(["Username"])
        writer.writerow([username])
    return True


def init_browser():
    os.makedirs(SELENIUM_CACHE_DIR, exist_ok=True)
    os.environ.setdefault("SE_CACHE_PATH", os.path.abspath(SELENIUM_CACHE_DIR))

    chrome_options = Options()
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    if is_headless_enabled():
        chrome_options.add_argument("--headless=new")

    user_data_dir = get_chrome_user_data_dir()
    profile_directory = get_chrome_profile_directory()

    if profile_directory and not user_data_dir:
        default_user_data_dir = get_default_chrome_user_data_dir()
        if default_user_data_dir:
            user_data_dir = default_user_data_dir

    if user_data_dir:
        if not os.path.isdir(user_data_dir):
            raise RuntimeError(f"Chrome user data directory does not exist: {user_data_dir}")
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    if profile_directory:
        profile_path = os.path.join(user_data_dir, profile_directory) if user_data_dir else profile_directory
        if user_data_dir and not os.path.isdir(profile_path):
            raise RuntimeError(
                f"Chrome profile directory does not exist: {profile_directory}. "
                f"Use a real folder name like 'Default' or 'Profile 1'."
            )
        chrome_options.add_argument(f"--profile-directory={profile_directory}")
    try:
        browser = webdriver.Chrome(options=chrome_options)
    except WebDriverException as exc:
        raise RuntimeError(
            "Chrome WebDriver could not start. Install Google Chrome and ensure Selenium can access a compatible driver."
        ) from exc

    browser.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """
        },
    )

    wait = WebDriverWait(browser, 20)
    return browser, wait


def login_tiktok(browser, wait, username, password):
    if should_use_existing_session():
        browser.get("https://www.tiktok.com/messages?lang=en")
        time.sleep(5)
        if is_logged_in(browser):
            print("Using existing TikTok browser session.")
            return
        raise RuntimeError(
            "USE_EXISTING_SESSION is enabled, but this Chrome profile is not logged into TikTok."
        )

    browser.get("https://www.tiktok.com/login/phone-or-email/email")
    try:
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        password_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="new-password"]'))
        )
        password_field.send_keys(password)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))).click()
        time.sleep(3)

        solver = get_captcha_solver()
        if solver is not None and has_working_captcha_key():
            api_key = os.getenv("CAPTCHA_API_KEY")
            solver(browser, api_key, "tiktokcircle", 10, 20, "fast")
        elif is_headless_enabled():
            raise RuntimeError(
                "No captcha solver configured and headless mode is enabled. "
                "Set HEADLESS=false or provide CAPTCHA_API_KEY to proceed."
            )
        else:
            print(
                "Captcha solver not configured. Waiting for manual login completion in the browser."
            )
            try:
                WebDriverWait(browser, get_login_wait_seconds()).until(
                    lambda drv: "/login" not in drv.current_url.lower()
                    and "/challenge" not in drv.current_url.lower()
                    and "tiktok.com" in drv.current_url.lower()
                )
            except TimeoutException:
                raise RuntimeError(
                    "Manual login did not complete in time. Complete any captcha/2FA in the browser "
                    "or set CAPTCHA_API_KEY."
                )

        time.sleep(5)
        current_url = browser.current_url.lower()
        if "/login" in current_url or "/challenge" in current_url:
            raise RuntimeError(
                "TikTok did not complete login. CAPTCHA, 2FA, suspicious-login checks, or rate limiting may still be blocking access. "
                "Use a real Chrome profile with USE_EXISTING_SESSION=true after logging in manually."
            )
    except TimeoutException as exc:
        raise RuntimeError(
            "TikTok login page did not load the expected fields. The site layout may have changed."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"TikTok login failed: {exc}") from exc


def get_all_friends(browser, wait):
    browser.get("https://www.tiktok.com/messages?lang=vi")

    try:
        all_user = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "css-2tydh5-PInfoNickname")))

        for user in all_user:
            user.click()
            time.sleep(2)
            profile_element = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "css-1qxabns-StyledLink"))
            )[0]
            href = profile_element.get_attribute("href")
            match = re.search(r"/@(.+)", href)
            if not match:
                continue

            username = match.group(1)
            if append_friend(username):
                print(f"Added friend: {username}")
    except TimeoutException as exc:
        raise RuntimeError(
            "TikTok messages page did not expose the expected friend list. The selectors likely need updating."
        ) from exc
    finally:
        browser.quit()


def auto_send_message(browser, wait):
    browser.get("https://www.tiktok.com/messages?lang=vi")

    my_friends = set(load_friends())
    if not my_friends:
        raise RuntimeError("friends.csv is empty. Run my-friends.py first or add usernames manually.")

    try:
        all_user = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "css-1mez8np-PInfoNickname")))

        for user in all_user:
            user.click()
            time.sleep(2)
            profile_element = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "css-1qxabns-StyledLink"))
            )[0]
            href = profile_element.get_attribute("href")
            match = re.search(r"/@(.+)", href)
            if not match:
                continue

            username = match.group(1)
            if username not in my_friends:
                continue

            print(f"Sending message to {username}")
            message_input = wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "public-DraftStyleDefault-block"))
            )
            message_input.click()
            message_input.send_keys(os.getenv("MESSAGE"))
            message_input.send_keys(Keys.RETURN)
    except TimeoutException as exc:
        raise RuntimeError(
            "TikTok messages UI did not match the expected selectors. The automation likely needs updated locators."
        ) from exc
    finally:
        browser.quit()
