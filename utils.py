import csv
import os
import re
import time

from dotenv import load_dotenv
from ocacaptcha import oca_solve_captcha
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

FRIENDS_CSV = "friends.csv"
SELENIUM_CACHE_DIR = os.path.join(".selenium")
REQUIRED_ENV_VARS = (
    "CAPTCHA_API_KEY",
    "TIKTOK_USERNAME",
    "TIKTOK_PASSWORD",
    "MESSAGE",
)


def validate_environment():
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {joined}")

    return os.getenv("TIKTOK_USERNAME"), os.getenv("TIKTOK_PASSWORD")


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
    chrome_options.add_argument("--headless=new")
    try:
        browser = webdriver.Chrome(options=chrome_options)
    except WebDriverException as exc:
        raise RuntimeError(
            "Chrome WebDriver could not start. Install Google Chrome and ensure Selenium can access a compatible driver."
        ) from exc

    wait = WebDriverWait(browser, 20)
    return browser, wait


def login_tiktok(browser, wait, username, password):
    browser.get("https://www.tiktok.com/login/phone-or-email/email")
    actions = ActionChains(browser, duration=550)

    try:
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        password_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="new-password"]'))
        )
        password_field.send_keys(password)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "tiktok-11sviba-Button-StyledButton"))).click()
        time.sleep(3)
        oca_solve_captcha(browser, actions, os.getenv("CAPTCHA_API_KEY"), "tiktokcircle", 10)
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
