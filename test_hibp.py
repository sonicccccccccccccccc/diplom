import requests
print("Попытка подключения к api.pwnedpasswords.com...")
try:
    r = requests.get("https://api.pwnedpasswords.com/range/00000", timeout=10)
    print(f"Успех! Статус: {r.status_code}, длина ответа: {len(r.text)}")
except Exception as e:
    print(f"Ошибка: {e}")