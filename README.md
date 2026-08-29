# ♟️ ICCF Chess Notifier & Analyzer Bot

An automated correspondence chess assistant built with Python and GitHub Actions. It monitors incoming ICCF notification emails, parses game PGNs, runs deep engine analysis with **Stockfish**, and delivers move recommendations directly to **Telegram**.

---

## ⚡ Features

* **Zero-Server Setup:** Runs entirely on GitHub Actions using automated cron schedules.
* **Email Integration:** Connects via IMAP (SSL) to monitor unread ICCF move notifications.
* **Smart Turn Detection:** Automatically validates player tags in PGNs to analyze only positions where it is your turn.
* **Deep Engine Analysis:** Utilizes Stockfish on multi-core runners to calculate the Top 3 move recommendations.
* **Instant Telegram Alerts:** Delivers formatted markdown reports with evaluation scores (`cp` / `mate`), depth, principal variations, and a direct link back to the ICCF game board.

---
## 🛠️ Architecture & Workflow

```text
[ICCF Server] 
      │ (Move notification email)
      ▼
[Mailbox (IMAP)] 
      │ (Checked every 20 mins)
      ▼
[GitHub Actions Runner]
      ├── 1. Fetch unread PGN emails
      ├── 2. Verify player turn
      ├── 3. Run Stockfish analysis (MultiPV)
      └── 4. Mark email as read
      │
      ▼
[Telegram Bot API] ──► [Your Telegram Chat]
```
---

## ⚙️ Setup & Configuration

### 1. Telegram Bot Setup
1. Create a bot using [@BotFather](https://t.me/botfather) on Telegram and save the **API Token**.
2. Send `/start` to your bot.
3. Obtain your personal Chat ID (e.g., using [@userinfobot](https://t.me/userinfobot)).

### 2. Configure GitHub Secrets
Navigate to **Settings** → **Secrets and variables** → **Actions** in your repository and configure the following secrets:

| Secret Name | Description | Example |
| :--- | :--- | :--- |
| `IMAP_SERVER` | IMAP hostname for your email | `imap.gmail.com` |
| `EMAIL_ACCOUNT` | Your email address | `example@gmail.com` |
| `EMAIL_PASSWORD` | IMAP password or App Password | `abcd efgh ijkl mnop` |
| `TELEGRAM_TOKEN` | Telegram Bot Token from BotFather | `123456789:ABCdefGHI...` |
| `CHAT_ID` | Your numeric Telegram Chat ID | `123456789` |
| `ICCF_USERNAME` | Your exact name/handle on ICCF | `Kowalski, Jan` |

---

## ⏱️ Customizing Schedule & Analysis Time

* **Schedule Interval:** Modify `.github/workflows/chess_watcher.yml` under `cron: '*/20 * * * *'` to adjust check frequency.
* **Engine Depth & Think Time:** Edit `main.py` in the `analyze_position()` function (`time_limit = 90`) to increase or decrease analysis duration.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
