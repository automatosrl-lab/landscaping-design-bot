# 🌿 Landscaping Design Bot

AI-powered chatbot per **garden design e rendering automatico**.

Il bot prende una foto di un giardino "brutto" o trascurato e genera un rendering professionale con le modifiche richieste dal cliente, **preservando la casa e le strutture esistenti**.

## Come Funziona

```
┌─────────────────────────────────────────────────────────────┐
│  1. CLIENTE CARICA FOTO                                     │
│     Giardino trascurato, cortile spoglio, ecc.              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. GEMINI FLASH ANALIZZA                                   │
│     - Identifica elementi esistenti                         │
│     - Capisce lo spazio disponibile                         │
│     - Chiede preferenze al cliente                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. CLIENTE DESCRIVE COSA VUOLE                             │
│     "Voglio una piscina, prato verde, qualche palma..."     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. GEMINI IMAGE (NANO BANANA) GENERA RENDERING             │
│     - Modifica SOLO il giardino/landscape                   │
│     - Preserva casa, muri, strutture                        │
│     - Aggiunge piscina, prato, piante, vialetti, ecc.       │
│     - Rendering fotorealistico professionale                │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  5. ITERAZIONI                                              │
│     Cliente può chiedere modifiche:                         │
│     "Aggiungi più fiori", "Cambia forma piscina"            │
└─────────────────────────────────────────────────────────────┘
```

## Stack Tecnologico

| Componente | Tecnologia | Ruolo |
|------------|------------|-------|
| **Chat** | Gemini 2.5 Flash | Conversazione con utente |
| **Rendering** | Gemini 2.5 Flash Image (Nano Banana) | Generazione immagini |
| **Frontend** | Chainlit | Widget chat embeddabile |

**Una sola API key** (Google AI Studio) per tutto il sistema!

## Cosa Può Modificare

✅ **MODIFICA:**
- Prato e terreno
- Piante, fiori, alberi
- Piscine e vasche
- Vialetti e percorsi
- Pergole e gazebo
- Illuminazione esterna
- Recinzioni
- Colore muri esterni

❌ **PRESERVA:**
- Casa/edificio principale
- Finestre e porte
- Tetto
- Strutture architettoniche
- Fondamenta

## Setup Rapido

```bash
# 1. Installa dipendenze
pip install -r requirements.txt

# 2. Configura API key
cp .env.example .env
# Modifica .env: GOOGLE_API_KEY=your_key

# 3. Avvia
chainlit run app.py
```

## Costi

| Operazione | Costo |
|------------|-------|
| Chat (per messaggio) | ~$0.0001 |
| Rendering (per immagine) | ~$0.039 |
| **Demo 100 rendering** | **~$4** |

## Struttura Progetto

```
landscaping-design-bot/
├── app.py                      # App Chainlit principale
├── requirements.txt            # Dipendenze
├── .env.example               # Template config
├── services/
│   └── gemini_image_service.py # Servizio Gemini unificato
├── .chainlit/
│   └── config.toml            # Config UI
└── deploy/
    ├── Dockerfile
    └── railway.json
```

## Esempio Conversazione

```
🤖: Benvenuto! Carica una foto del tuo giardino.

👤: [Carica foto di cortile spoglio]

🤖: Ho analizzato il tuo spazio! Vedo un'area di circa 60mq
    con terreno in parte sterrato. Che stile preferisci?
    • Moderno • Mediterraneo • Tropicale • Zen

👤: Mediterraneo, voglio una piscina e delle palme

🤖: Perfetto! Genero il rendering...
    [IMMAGINE: Stesso cortile trasformato con piscina,
     palme, prato verde - casa identica]

👤: Aggiungi più fiori colorati

🤖: [IMMAGINE: Versione aggiornata con fiori]
```

---

*Powered by Automato AI*
