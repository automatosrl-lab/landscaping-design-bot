# 🚀 Guida Setup - Garden Design AI Bot

## Prerequisiti

- Python 3.10+
- Account Google AI Studio (gratuito)
- Account Replicate (pay-per-use)

---

## Step 1: Ottieni le API Keys

### Google AI Studio (Gemini)

1. Vai su [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Clicca "Create API Key"
3. Copia la chiave generata

**Costo**: Gemini Flash è praticamente gratuito per uso normale

### Replicate (Flux Pro)

1. Vai su [Replicate](https://replicate.com)
2. Registrati/Accedi
3. Vai su [API Tokens](https://replicate.com/account/api-tokens)
4. Crea un nuovo token

**Costo**: ~$0.055 per immagine generata

---

## Step 2: Setup Locale

```bash
# 1. Vai nella cartella del progetto
cd landscaping-design-bot

# 2. Crea ambiente virtuale
python -m venv venv

# 3. Attiva ambiente virtuale
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 4. Installa dipendenze
pip install -r requirements.txt

# 5. Configura variabili ambiente
cp .env.example .env

# 6. Modifica .env con le tue API keys
# Apri .env e inserisci:
# GOOGLE_API_KEY=your_key_here
# REPLICATE_API_TOKEN=your_token_here

# 7. Avvia il bot
chainlit run app.py
```

Il bot sarà disponibile su: **http://localhost:8000**

---

## Step 3: Deploy su Cloud

### Opzione A: Railway (Consigliato)

1. Vai su [Railway](https://railway.app)
2. Connetti il tuo GitHub
3. Crea nuovo progetto da repository
4. Aggiungi le variabili ambiente:
   - `GOOGLE_API_KEY`
   - `REPLICATE_API_TOKEN`
5. Deploy automatico!

**Costo**: Free tier disponibile, poi ~$5/mese

### Opzione B: Render

1. Vai su [Render](https://render.com)
2. Crea nuovo "Web Service"
3. Connetti repository
4. Configura:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `chainlit run app.py --host 0.0.0.0 --port $PORT`
5. Aggiungi Environment Variables
6. Deploy!

### Opzione C: Docker

```bash
# Build
docker build -t garden-design-bot -f deploy/Dockerfile .

# Run
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY=your_key \
  -e REPLICATE_API_TOKEN=your_token \
  garden-design-bot
```

---

## Step 4: Embed sul Sito del Cliente

Una volta deployato, puoi embeddare il widget sul sito:

```html
<!-- Aggiungi nel <head> -->
<script src="https://cdn.jsdelivr.net/npm/@anthropic/embed-widget@latest"></script>

<!-- Aggiungi nel <body> -->
<iframe
  src="https://your-app-url.railway.app"
  width="400"
  height="600"
  style="border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
></iframe>
```

Oppure usa un widget popup:

```html
<script>
  // Pulsante per aprire chat
  const chatButton = document.createElement('button');
  chatButton.innerHTML = '🌿 Progetta il tuo giardino';
  chatButton.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 16px 24px;
    background: #228B22;
    color: white;
    border: none;
    border-radius: 50px;
    cursor: pointer;
    font-size: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  `;

  chatButton.onclick = () => {
    window.open('https://your-app-url.railway.app', 'GardenDesign', 'width=450,height=700');
  };

  document.body.appendChild(chatButton);
</script>
```

---

## Struttura del Progetto

```
landscaping-design-bot/
├── app.py                    # App principale Chainlit
├── requirements.txt          # Dipendenze Python
├── .env.example             # Template variabili ambiente
├── chainlit.md              # Pagina benvenuto
├── .chainlit/
│   └── config.toml          # Configurazione Chainlit
├── prompts/
│   ├── __init__.py
│   └── system_prompts.py    # Prompt per Gemini e templates
├── services/
│   ├── __init__.py
│   ├── gemini_service.py    # Servizio Gemini (chat + analisi)
│   └── flux_service.py      # Servizio Flux (image gen)
└── deploy/
    ├── Dockerfile           # Per deploy Docker
    └── railway.json         # Config Railway
```

---

## Troubleshooting

### "GOOGLE_API_KEY non configurata"
- Verifica che il file `.env` esista
- Verifica che la chiave sia corretta
- Riavvia l'applicazione

### "Errore generazione immagine"
- Verifica credito Replicate
- Controlla che il token sia valido
- Prova con un'immagine più piccola

### "Chat non risponde"
- Controlla la console per errori
- Verifica connessione internet
- Riavvia Chainlit

---

## Supporto

Per assistenza: [Automato AI](https://automato.ai)
