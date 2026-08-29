import email
import imaplib
import io
import os
import sys
from dotenv import load_dotenv
import chess
import chess.engine
import chess.pgn
import requests
import re

load_dotenv()

IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
EMAIL_ACCOUNT = os.environ.get("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ICCF_USERNAME = os.environ.get("ICCF_USERNAME")
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

def escape_markdown(text: str) -> str:
    """Zabezpiecza znaki specjalne przed wywaleniem błędu w Markdown."""
    escape_chars = r"_*`["
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()

def analyze_board(board: chess.Board, seconds: int = 90) -> str:
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({
        "Threads": 2,
        "Hash": 256,
        "Skill Level": 20
    })

    info = engine.analyse(board, chess.engine.Limit(time=seconds), multipv=3)
    engine.quit()

    lines = []
    for entry in info:
        move = board.san(entry["pv"][0])
        score = entry["score"].white() if board.turn == chess.WHITE else entry["score"].black()
        depth = entry.get("depth", 0)
        
        eval_str = f"#M{score.mate()}" if score.is_mate() else f"{score.score() / 100:+.2f}"
        lines.append(f"• *{move}* (`{eval_str}`, depth: {depth})")
        
    return "\n".join(lines)


def clean_html(raw_html: str) -> str:
    """Usuwa tagi HTML i zamienia <br>, <p>, <div> na znaki nowej linii."""
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
    text = re.sub(r'</?(p|div|tr|table)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return text

def extract_clean_pgn(text: str) -> str:
    """
    Wyciąga blok PGN od [Event ...] aż do gwiazdki lub wyniku (*, 1-0, 0-1, 1/2-1/2),
    zapewniając poprawny odstęp między nagłówkami a listą posunięć.
    """
    text = clean_html(text)
    
    # 1. Znajdź początek PGN (pierwszy nagłówek)
    start_idx = text.find('[Event')
    if start_idx == -1:
        return ""
    
    pgn_candidate = text[start_idx:]
    
    # 2. Obetnij tekst na końcu partii (wynik lub gwiazdka *)
    # Szukamy sekwencji ruchów zakończonej *, 1-0, 0-1 lub 1/2-1/2
    match = re.search(r'(\[Event[\s\S]*?(\*|1-0|0-1|1/2-1/2))', pgn_candidate)
    if match:
        pgn_candidate = match.group(1)
        
    lines = pgn_candidate.splitlines()
    headers = []
    movetext_parts = []
    in_moves = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('['):
            if not in_moves:
                headers.append(stripped)
        else:
            # Ignoruj polskie stopki ICCF o czasie
            if "Pozostały czas" in stripped or "Wyświetl partię" in stripped:
                continue
            in_moves = True
            movetext_parts.append(stripped)
            
    # Standard PGN WYMAGA pustej linii między nagłówkami a ruchami!
    clean_pgn = '\n'.join(headers) + '\n\n' + ' '.join(movetext_parts)
    return clean_pgn

def process_pgn(pgn_text: str):
    try:
        clean_text = extract_clean_pgn(pgn_text)
        if not clean_text or '[Event' not in clean_text:
            print("[DEBUG] Brak poprawnego bloku PGN w mailu.")
            return

        pgn_io = io.StringIO(clean_text)
        game = chess.pgn.read_game(pgn_io)
        
        if not game:
            print("[DEBUG] chess.pgn nie zdołał odczytać partii.")
            return

        white = game.headers.get("White", "Nieznany")
        black = game.headers.get("Black", "Nieznany")
        event = game.headers.get("Event", "Partia ICCF")

        url_match = re.search(r'https?://(?:www\.)?iccf\.com/game\?id=\d+', pgn_text)
        game_url = url_match.group(0) if url_match else game.headers.get("Site", "https://www.iccf.com")

        board = game.board()
        moves_count = 0
        for move in game.mainline_moves():
            board.push(move)
            moves_count += 1

        print(f"[DEBUG] Wczytano partię: {white} vs {black} | Wykonanych półruchów: {moves_count} | FEN: {board.fen()}")

        user_clean = ICCF_USERNAME.lower().strip()
        is_white = user_clean in white.lower()
        is_black = user_clean in black.lower()

        is_my_turn = (board.turn == chess.WHITE and is_white) or \
                     (board.turn == chess.BLACK and is_black)

        print(f"[DEBUG] is_my_turn: {is_my_turn} (Biały: {is_white}, Czarny: {is_black})")

        if is_my_turn and not board.is_game_over():
            opponent = black if is_white else white
            color = "Białe" if board.turn == chess.WHITE else "Czarne"
            move_num = board.fullmove_number
            
            print(f"Analizowanie pozycji przeciwko {opponent} (Ruch {move_num}, {color})...")
            top_lines = analyze_board(board, seconds=90)
            
            safe_event = escape_markdown(event)
            safe_opponent = escape_markdown(opponent)
            
            msg = (
                f"♟️ *Ruch na ICCF!*\n"
                f"🏆 *Turniej:* {safe_event}\n"
                f"👤 *Rywal:* {safe_opponent} ({color})\n"
                f"🔢 *Posunięcie:* {move_num}. ({color.lower()})\n"
                f"🔗 [Przejdź do partii na ICCF]({game_url})\n\n"
                f"*Rekomendacje Stockfish (Top 3):*\n{top_lines}"
            )
            send_telegram(msg)
        else:
            if board.is_game_over():
                print("[DEBUG] Partia jest już zakończona.")
            elif not is_my_turn:
                print("[DEBUG] To nie jest Twój ruch.")

    except Exception as e:
        print(f"Pominięto partię ze względu na błąd: {e}")
        
def run():
    if not all([EMAIL_ACCOUNT, EMAIL_PASSWORD, TELEGRAM_TOKEN, CHAT_ID, ICCF_USERNAME]):
        print("Błąd: Brak zdefiniowanych wymaganych zmiennych środowiskowych.")
        sys.exit(1)

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select("INBOX")

    status, messages = mail.search(None, "UNSEEN")
    if status != "OK" or not messages or not messages[0].strip():
        print("Brak nowych powiadomień w skrzynce.")
        mail.close()
        mail.logout()
        return

    msg_ids = messages[0].split()
    print(f"Znaleziono {len(msg_ids)} nowych powiadomień. Przetwarzanie...")

    for msg_id in msg_ids:
        res, data = mail.fetch(msg_id, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                for part in msg.walk():
                    filename = part.get_filename()
                    if filename and filename.endswith(".pgn"):
                        payload = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        process_pgn(payload)
                    elif part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        if "[Event " in body and "[Site " in body:
                            process_pgn(body)

        mail.store(msg_id, "+FLAGS", "\\Seen")

    mail.close()
    mail.logout()

if __name__ == "__main__":
    run()
