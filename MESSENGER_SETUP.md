# Facebook Messenger Tool - Setup Guide

## Overview

MessengerTool umożliwia komunikację przez Facebook Messenger dla strony **P4-Asiistant**.

Funkcje:
- ✉️ **Wysyłanie wiadomości** do użytkowników
- 📋 **Lista konwersacji** z informacjami o uczestnikach
- 💬 **Czytanie historii** konwersacji
- 🔔 **Sprawdzanie nieprzeczytanych** wiadomości

## Wymagania

```bash
pip install requests python-dotenv
```

## Konfiguracja Facebook

### Krok 1: Przygotowanie strony Facebook

1. Upewnij się że masz dostęp do strony **P4-Asiistant**
2. Strona musi być opublikowana (nie szkic)
3. Zaloguj się jako administrator strony

### Krok 2: Utworzenie Facebook App

1. Przejdź do https://developers.facebook.com/apps
2. Kliknij **Create App**
3. Wybierz typ: **Business**
4. Wypełnij dane:
   - **App Name**: np. "P4-Asiistant Messenger Bot"
   - **App Contact Email**: twój email
5. Kliknij **Create App**

### Krok 3: Dodanie Messenger

1. W Dashboard aplikacji znajdź **Add Products**
2. Znajdź **Messenger** i kliknij **Set Up**
3. Messenger zostanie dodany do twojej aplikacji

### Krok 4: Wygenerowanie Page Access Token

1. W lewym menu: **Messenger** → **Settings**
2. Sekcja **Access Tokens**
3. Kliknij **Add or Remove Pages**
4. Wybierz stronę **P4-Asiistant**
5. Kliknij **Generate Token**
6. **SKOPIUJ TOKEN** - pojawi się tylko raz!
7. Token wygląda tak: `EAAxxxxxxxxxxxxxxxxxxxxx...` (bardzo długi)

### Krok 5: Uzyskanie Page ID

**Opcja A - Z ustawień strony:**
1. Przejdź do https://facebook.com/P4-Asiistant
2. Kliknij **About** (O nas)
3. Przewiń do dołu
4. **Page ID** jest wyświetlone

**Opcja B - Z Graph API Explorer:**
1. Przejdź do https://developers.facebook.com/tools/explorer
2. Wybierz swoją aplikację
3. Wybierz User or Page → swoją stronę
4. W polu wpisz: `me?fields=id,name`
5. Kliknij **Submit**
6. Zobaczysz Page ID i nazwę

### Krok 6: Konfiguracja uprawnień

W **App Dashboard** → **Messenger** → **Settings**:

Upewnij się że masz włączone:
- ✅ `pages_messaging` - wysyłanie i odbieranie wiadomości
- ✅ `pages_read_engagement` - czytanie konwersacji
- ✅ `pages_manage_metadata` - zarządzanie metadanymi

Jeśli brakuje uprawnień:
1. Idź do **App Review** → **Permissions and Features**
2. Znajdź brakujące uprawnienia
3. Kliknij **Request** i wypełnij formularz

### Krok 7: Konfiguracja .env

Dodaj do pliku `.env`:

```bash
# Facebook Messenger Configuration
MESSENGER_PAGE_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxx...
MESSENGER_PAGE_ID=123456789012345
```

⚠️ **WAŻNE**: 
- Nie commituj `.env` do git!
- Token jest bardzo wrażliwy - traktuj jak hasło
- Token strony nie wygasa (chyba że go zregenerujesz)

## Testowanie

### Test 1: Podstawowa funkcjonalność

```python
from one_think.tools.messenger_tool import MessengerTool

tool = MessengerTool()

# Test help
result, error = tool.execute({"help": True})
print(result)
```

### Test 2: Lista konwersacji

```python
# Pobierz listę konwersacji
result, error = tool.execute({
    "operation": "list_conversations",
    "limit": 5
})

print(result if not error else f"Error: {error}")
```

### Test 3: Wyślij testową wiadomość

⚠️ **Najpierw wyślij wiadomość DO swojej strony** z osobistego konta!

```python
# 1. Pobierz listę konwersacji aby zobaczyć PSID
result, error = tool.execute({
    "operation": "list_conversations",
    "limit": 5
})

# Skopiuj participant_ids[0] z pierwszej konwersacji

# 2. Wyślij wiadomość testową
result, error = tool.execute({
    "operation": "send_message",
    "recipient_id": "TUTAJ_WKLEJ_PSID",
    "message": "Test wiadomości z MessengerTool!"
})

print(result if not error else f"Error: {error}")
```

### Test 4: Czytanie konwersacji

```python
# Skopiuj conversation_id z list_conversations

result, error = tool.execute({
    "operation": "read_conversation",
    "conversation_id": "t_1234567890",
    "limit": 10
})

print(result if not error else f"Error: {error}")
```

## Użycie

### Sprawdzanie nowych wiadomości

```python
tool = MessengerTool()

# 1. Pobierz listę konwersacji
result, error = tool.execute({
    "operation": "list_conversations",
    "limit": 10
})

conversations = json.loads(result)

# 2. Sprawdź nieprzeczytane
for conv in conversations["conversations"]:
    if conv["unread_count"] > 0:
        print(f"Nowa wiadomość od: {conv['participants']}")
        print(f"Snippet: {conv['snippet']}")
        print(f"Conversation ID: {conv['conversation_id']}")
        print(f"User PSID: {conv['participant_ids'][0]}")  # Pierwszy uczestnik (nie strona)
```

### Odpowiadanie na wiadomości

```python
import json

# 1. Lista konwersacji
result, _ = tool.execute({"operation": "list_conversations"})
conversations = json.loads(result)

# 2. Wybierz konwersację do odpowiedzi
for conv in conversations["conversations"]:
    if conv["unread_count"] > 0:
        # Znajdź PSID użytkownika (nie strony)
        user_psid = None
        for psid in conv["participant_ids"]:
            # Usuń PSID strony (możesz je rozpoznać lub sprawdzić który to użytkownik)
            if psid != tool.page_id:  # Nie PSID strony
                user_psid = psid
                break
        
        if user_psid:
            # 3. Wyślij odpowiedź
            tool.execute({
                "operation": "send_message",
                "recipient_id": user_psid,
                "message": "Dziękuję za wiadomość! Jak mogę pomóc?"
            })
```

### Czytanie pełnej historii

```python
# 1. Pobierz conversation_id
result, _ = tool.execute({"operation": "list_conversations", "limit": 1})
conv_data = json.loads(result)
conversation_id = conv_data["conversations"][0]["conversation_id"]

# 2. Przeczytaj historię
result, error = tool.execute({
    "operation": "read_conversation",
    "conversation_id": conversation_id,
    "limit": 50
})

messages = json.loads(result)

# 3. Wyświetl wiadomości
for msg in messages["messages"]:
    print(f"[{msg['created_time']}] {msg['from_name']}: {msg['message']}")
```

### Automatyczna odpowiedź

```python
import json

def check_and_respond():
    tool = MessengerTool()
    
    # Pobierz konwersacje
    result, _ = tool.execute({"operation": "list_conversations", "limit": 20})
    conversations = json.loads(result)
    
    for conv in conversations["conversations"]:
        # Sprawdź czy są nieprzeczytane
        if conv["unread_count"] > 0:
            # Pobierz historię
            conv_id = conv["conversation_id"]
            result, _ = tool.execute({
                "operation": "read_conversation",
                "conversation_id": conv_id,
                "limit": 5
            })
            
            msgs = json.loads(result)
            last_message = msgs["messages"][-1]  # Ostatnia wiadomość
            
            # Sprawdź czy ostatnia wiadomość nie jest od strony
            if last_message["from_id"] != tool.page_id:
                user_psid = last_message["from_id"]
                user_message = last_message["message"]
                
                # Tu możesz dodać logikę odpowiedzi
                if "help" in user_message.lower():
                    response = "Czym mogę Ci pomóc?"
                else:
                    response = "Dziękuję za wiadomość!"
                
                # Wyślij odpowiedź
                tool.execute({
                    "operation": "send_message",
                    "recipient_id": user_psid,
                    "message": response
                })

# Uruchom
check_and_respond()
```

## Ważne informacje

### PSID (Page-Scoped ID)

- Każdy użytkownik ma unikalny PSID dla każdej strony
- PSID otrzymujesz gdy użytkownik napisze do twojej strony
- Ten sam użytkownik ma różne PSID dla różnych stron
- PSID znajdziesz w:
  - `list_conversations` → `participant_ids`
  - `read_conversation` → `from_id`

### Ograniczenia 24-godzinnego okna

Facebook pozwala wysyłać wiadomości tylko:
- ✅ W ciągu 24h od ostatniej wiadomości użytkownika
- ❌ Po 24h potrzebujesz **Message Tags** (specjalne uprawnienia)

Message Tags służą do:
- Potwierdzenia transakcji
- Aktualizacji konta
- Powiadomień o wysyłce
- Itp.

### Limity API

- Rate limits są nakładane przez Facebook
- Zbyt wiele requestów → throttling
- Monitor odpowiedzi API dla błędów limitów

### Bezpieczeństwo

⚠️ **Nigdy nie udostępniaj**:
- Page Access Token
- App Secret
- Credentials

✅ **Dobre praktyki**:
- Token tylko w `.env`
- `.env` w `.gitignore`
- Regularnie sprawdzaj logi aplikacji
- Monitoruj nietypową aktywność

## Rozwiązywanie problemów

### Błąd: "Invalid OAuth access token"

**Przyczyny:**
- Token wygasł
- Token został odwołany
- Zła konfiguracja

**Rozwiązanie:**
1. Wygeneruj nowy token
2. Zaktualizuj `.env`
3. Zrestartuj aplikację

### Błąd: "No matching user found"

**Przyczyny:**
- Błędny PSID
- Użytkownik zablokował stronę
- Użytkownik usunął konwersację

**Rozwiązanie:**
- Sprawdź PSID w `list_conversations`
- Upewnij się że użytkownik nie zablokował strony

### Błąd: "Cannot message users who haven't messaged page"

**Przyczyna:**
- Użytkownik nigdy nie napisał do strony
- Nie możesz zainicjować konwersacji

**Rozwiązanie:**
- Poczekaj aż użytkownik napisze pierwszy
- Lub użyj Message Tags (wymaga uprawnień)

### Brak konwersacji w liście

**Przyczyny:**
- Brak wiadomości na stronie
- Nieprawidłowe uprawnienia

**Rozwiązanie:**
1. Wyślij testową wiadomość DO strony
2. Sprawdź uprawnienia w App Dashboard
3. Sprawdź czy token ma odpowiednie scope

## Przykładowe skrypty

### Monitor nowych wiadomości (prosty bot)

```python
import time
import json
from one_think.tools.messenger_tool import MessengerTool

def bot_loop():
    tool = MessengerTool()
    processed_messages = set()
    
    while True:
        try:
            # Pobierz konwersacje
            result, _ = tool.execute({"operation": "list_conversations", "limit": 10})
            conversations = json.loads(result)
            
            for conv in conversations["conversations"]:
                if conv["unread_count"] > 0:
                    conv_id = conv["conversation_id"]
                    
                    # Pobierz wiadomości
                    result, _ = tool.execute({
                        "operation": "read_conversation",
                        "conversation_id": conv_id,
                        "limit": 5
                    })
                    
                    msgs = json.loads(result)
                    
                    for msg in msgs["messages"]:
                        msg_id = msg["message_id"]
                        
                        # Sprawdź czy już przetworzona
                        if msg_id not in processed_messages:
                            # Pomiń wiadomości od strony
                            if msg["from_id"] != tool.page_id:
                                print(f"Nowa wiadomość od {msg['from_name']}: {msg['message']}")
                                
                                # Wyślij odpowiedź
                                tool.execute({
                                    "operation": "send_message",
                                    "recipient_id": msg["from_id"],
                                    "message": "Dziękuję! Sprawdzę to."
                                })
                                
                                processed_messages.add(msg_id)
            
            # Czekaj 10 sekund
            time.sleep(10)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

# Uruchom bota
# bot_loop()  # Odkomentuj aby uruchomić
```

## Dalsze kroki

1. **Webhook dla real-time** - konfiguruj webhook aby otrzymywać wiadomości natychmiast
2. **Przyciski i Quick Replies** - interaktywne elementy w wiadomościach
3. **Szablony wiadomości** - predefiniowane odpowiedzi
4. **NLP Integration** - integracja z AI do inteligentnych odpowiedzi

## Przydatne linki

- [Messenger Platform Documentation](https://developers.facebook.com/docs/messenger-platform)
- [Send API Reference](https://developers.facebook.com/docs/messenger-platform/reference/send-api)
- [Graph API Explorer](https://developers.facebook.com/tools/explorer)
- [App Dashboard](https://developers.facebook.com/apps)
