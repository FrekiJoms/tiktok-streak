# TikTok Streak Auto

## Setup

Create and activate a virtual environment, then install dependencies:

```sh
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

This project currently depends on the PyPI package `ocacaptcha` for TikTok captcha solving.
The first Selenium run may need internet access to download a matching ChromeDriver.

## Environment Variables

Create a `.env` file in the root directory. You can copy `.env.example` and fill in the real values:

```sh
copy .env.example .env
```

```env
CAPTCHA_API_KEY="api_key_ocacaptcha"
TIKTOK_USERNAME="username"
TIKTOK_PASSWORD="password"
MESSAGE="auto send message"
```

> **Note:** Instead of a username, you can use an email for the `TIKTOK_USERNAME` variable.
>
> **Note:** The `MESSAGE` variable is the message that will be sent to all friends.

## Run Order

1. Install dependencies from `requirements.txt`.
2. Fill in `.env`.
3. Run `python my-friends.py` to collect usernames.
4. Review `friends.csv`.
5. Run `python main.py` to send the message.

## Get All Friends

To get all friends, run the `my-friends.py` file:

```sh
python my-friends.py
```

## Manage Friends List

You can add or remove your friends in the `friends.csv` file. This file contains the list of friends to whom messages will be sent.

## Send Message to All Friends

To send a message to all friends listed in the `friends.csv` file, run the `main.py` file:

```sh
python main.py
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=huuthang201/tiktok-streak&type=Date)](https://www.star-history.com/#huuthang201/tiktok-streak&Date)
