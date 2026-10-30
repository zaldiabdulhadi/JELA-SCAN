import os
from dotenv import load_dotenv
import requests

load_dotenv()
token = os.getenv("TG_TOKEN")
chat  = os.getenv("TG_CHAT")

print("Token :", token[:10] + "..." if token else "KOSONG")
print("Chat  :", chat)

r = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data={"chat_id": chat, "text": "Tes: pipeline Telegram OK"},
    timeout=10,
)
print("Status:", r.status_code)
print("Response:", r.json())