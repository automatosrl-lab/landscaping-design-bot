"""
Landscaping Design Bot - Applicazione Chainlit

Chatbot AI per garden design con rendering automatico.
Usa SOLO Gemini per:
- Chat (Gemini 2.5 Flash)
- Image Generation/Editing (Gemini 2.5 Flash Image / Nano Banana)

Il sistema modifica SOLO il landscape preservando casa e strutture.
"""

import chainlit as cl
import os
from dotenv import load_dotenv
from typing import Optional
import base64
import io

# Carica variabili ambiente
load_dotenv()

# Import servizio
from services.gemini_image_service import GeminiImageService

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

gemini_service: Optional[GeminiImageService] = None


def get_service() -> GeminiImageService:
    """Ottiene o crea il servizio Gemini."""
    global gemini_service
    if gemini_service is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY non configurata")
        gemini_service = GeminiImageService(api_key)
    return gemini_service


# =============================================================================
# STATO SESSIONE
# =============================================================================

class SessionState:
    """Stato della sessione utente."""
    WELCOME = "welcome"
    WAITING_IMAGE = "waiting_image"
    ANALYZING = "analyzing"
    COLLECTING_STYLE = "collecting_style"
    COLLECTING_ELEMENTS = "collecting_elements"
    READY_TO_GENERATE = "ready_to_generate"
    GENERATED = "generated"


# =============================================================================
# CHAINLIT HANDLERS
# =============================================================================

@cl.on_chat_start
async def on_chat_start():
    """Inizializza la sessione di chat."""

    try:
        service = get_service()
        service.reset_session()
    except ValueError as e:
        await cl.Message(
            content=f"⚠️ Errore di configurazione: {e}\n\nConfigura GOOGLE_API_KEY nel file .env"
        ).send()
        return

    # Inizializza stato sessione
    cl.user_session.set("state", SessionState.WELCOME)
    cl.user_session.set("uploaded_image", None)
    cl.user_session.set("style", None)
    cl.user_session.set("elements", [])
    cl.user_session.set("preserve", [])

    # Messaggio di benvenuto
    welcome = """🌿 **Benvenuto in Garden Design AI!**

Sono il tuo consulente personale per trasformare il tuo spazio esterno.

**Come funziona:**
1. 📸 Carica una foto del tuo giardino/cortile attuale
2. 💬 Dimmi cosa vorresti cambiare
3. 🎨 Genero un rendering fotorealistico del nuovo design

**Importante:** Il sistema modifica SOLO il giardino e il landscape.
La casa e le strutture rimangono esattamente come sono.

---

**Per iniziare, carica una foto del tuo spazio esterno** usando il pulsante 📎
"""

    await cl.Message(content=welcome).send()
    cl.user_session.set("state", SessionState.WAITING_IMAGE)


@cl.on_message
async def on_message(message: cl.Message):
    """Gestisce i messaggi dell'utente."""

    service = get_service()
    state = cl.user_session.get("state")

    # Controlla se c'è un'immagine allegata
    image_data = None
    if message.elements:
        for element in message.elements:
            if isinstance(element, cl.Image):
                with open(element.path, "rb") as f:
                    image_data = f.read()
                cl.user_session.set("uploaded_image", image_data)
                break

    # Se è stata caricata un'immagine
    if image_data:
        await handle_image_upload(service, image_data, message.content)
        return

    # Altrimenti gestisci in base allo stato
    if state == SessionState.WAITING_IMAGE:
        await cl.Message(
            content="📸 Per favore, carica prima una foto del tuo giardino usando il pulsante 📎"
        ).send()
        return

    # Chat normale con eventuale trigger di generazione
    await handle_chat(service, message.content)


async def handle_image_upload(service: GeminiImageService, image_data: bytes, user_message: str):
    """Gestisce il caricamento di un'immagine."""

    # Notifica ricezione
    status = await cl.Message(content="📸 **Foto ricevuta!** Sto analizzando il tuo spazio...").send()

    try:
        # Analizza l'immagine
        analysis = await service.analyze_garden(image_data)

        # Mostra analisi
        await cl.Message(
            content=f"""✅ **Analisi completata!**

{analysis['analysis']}

---

**Ora dimmi:** Che tipo di giardino vorresti? Scegli uno stile:

• 🏛️ **Moderno** - Linee pulite, minimalista, contemporaneo
• 🌿 **Mediterraneo** - Ulivi, lavanda, terracotta, caldo
• 🌴 **Tropicale** - Palme, piante esotiche, lussureggiante
• ☯️ **Zen** - Giapponese, sereno, ghiaia, bambù
• 🌹 **Inglese** - Romantico, fiori, rose, classico
• 🔥 **Contemporaneo** - Outdoor living, cucina esterna, fire pit

Scrivi lo stile che preferisci!
"""
        ).send()

        cl.user_session.set("state", SessionState.COLLECTING_STYLE)

        # Se l'utente ha scritto qualcosa insieme all'immagine, processalo
        if user_message and len(user_message) > 5:
            await handle_chat(service, user_message)

    except Exception as e:
        await cl.Message(content=f"❌ Errore nell'analisi: {e}").send()


async def handle_chat(service: GeminiImageService, user_message: str):
    """Gestisce la chat e il flusso di conversazione."""

    state = cl.user_session.get("state")
    user_lower = user_message.lower()

    # Rileva stile dalla risposta
    style_keywords = {
        "modern": ["moderno", "minimalista", "contemporaneo", "modern"],
        "mediterranean": ["mediterraneo", "italiano", "toscano", "med"],
        "tropical": ["tropicale", "esotico", "tropico", "palme"],
        "zen": ["zen", "giapponese", "japponese", "orientale"],
        "english": ["inglese", "romantico", "cottage", "english"],
        "contemporary": ["outdoor living", "fire pit", "cucina esterna", "lounge"]
    }

    # Se stiamo raccogliendo lo stile
    if state == SessionState.COLLECTING_STYLE:
        detected_style = None
        for style, keywords in style_keywords.items():
            if any(kw in user_lower for kw in keywords):
                detected_style = style
                break

        if detected_style:
            cl.user_session.set("style", detected_style)
            cl.user_session.set("state", SessionState.COLLECTING_ELEMENTS)

            await cl.Message(
                content=f"""Perfetto! Hai scelto lo stile **{detected_style.title()}** 🎨

Ora dimmi cosa vorresti nel tuo giardino. Puoi scegliere più elementi:

• 🏊 **Piscina** (forma, dimensione)
• 🌱 **Prato** (inglese, rustico, sintetico)
• 🌳 **Piante/Alberi** (quali tipi?)
• 🚶 **Vialetti** (pietra, ghiaia, legno)
• 🏠 **Pergola/Gazebo**
• 💡 **Illuminazione**
• ⛲ **Fontana/Acqua**
• 🍖 **Area BBQ/Cucina**
• 🛋️ **Area relax/Sedute**

Descrivi liberamente cosa desideri!
"""
            ).send()
            return

    # Se stiamo raccogliendo elementi
    if state == SessionState.COLLECTING_ELEMENTS:
        # Rileva elementi menzionati
        element_keywords = {
            "piscina": ["piscina", "pool", "vasca"],
            "prato verde": ["prato", "erba", "lawn", "verde"],
            "vialetto in pietra naturale": ["vialetto", "sentiero", "percorso", "camminamento"],
            "pergola con rampicanti": ["pergola", "gazebo", "tettoia"],
            "piante e fiori": ["piante", "fiori", "alberi", "siepe", "vegetazione"],
            "illuminazione da giardino": ["illuminazione", "luci", "lampioni", "faretti"],
            "fontana decorativa": ["fontana", "acqua", "cascata"],
            "area barbecue": ["bbq", "barbecue", "cucina", "grill"],
            "area relax con sedute": ["relax", "sedute", "divano", "lounge", "salotto"]
        }

        detected_elements = []
        for element, keywords in element_keywords.items():
            if any(kw in user_lower for kw in keywords):
                detected_elements.append(element)

        # Aggiungi elementi rilevati
        current_elements = cl.user_session.get("elements", [])
        current_elements.extend(detected_elements)
        # Rimuovi duplicati mantenendo ordine
        current_elements = list(dict.fromkeys(current_elements))
        cl.user_session.set("elements", current_elements)

        # Chiedi conferma per generare
        if current_elements:
            style = cl.user_session.get("style", "modern")
            elements_list = "\n".join([f"  • {el}" for el in current_elements])

            await cl.Message(
                content=f"""📋 **Riepilogo del tuo progetto:**

**Stile:** {style.title()}

**Elementi da aggiungere:**
{elements_list}

**Da preservare:** Casa e strutture esistenti

---

Vuoi che generi il rendering? Scrivi **"genera"** o **"ok"** per procedere.

Oppure aggiungi altri dettagli o modifiche!
"""
            ).send()

            cl.user_session.set("state", SessionState.READY_TO_GENERATE)
            return

    # Trigger per generare
    generate_triggers = ["genera", "ok", "procedi", "vai", "crea", "rendering", "inizia", "perfetto", "sì", "si"]
    if state == SessionState.READY_TO_GENERATE and any(t in user_lower for t in generate_triggers):
        await generate_rendering()
        return

    # Se già generato, permetti modifiche
    if state == SessionState.GENERATED:
        if any(t in user_lower for t in ["rigenera", "nuovo", "ricomincia"]):
            await generate_rendering()
            return

        # Raffina il rendering
        await refine_current_rendering(service, user_message)
        return

    # Chat generica con Gemini
    image_data = cl.user_session.get("uploaded_image")
    response = await service.chat(user_message, image_data if state == SessionState.WAITING_IMAGE else None)
    await cl.Message(content=response).send()


async def generate_rendering():
    """Genera il rendering del giardino."""

    service = get_service()
    image_data = cl.user_session.get("uploaded_image")

    if not image_data:
        await cl.Message(content="⚠️ Nessuna immagine caricata. Carica prima una foto del giardino.").send()
        return

    style = cl.user_session.get("style", "modern")
    elements = cl.user_session.get("elements", ["prato verde", "piante decorative"])

    # Status message
    status = await cl.Message(content="🎨 **Generazione rendering in corso...**\n\nSto trasformando il tuo giardino mantenendo la casa e le strutture esistenti...").send()

    try:
        # Genera con Gemini Image
        rendered_image = await service.generate_landscape_rendering(
            image_data=image_data,
            style=style,
            modifications=elements,
            preserve_elements=["alberi esistenti da preservare"],
            lighting="golden hour, tardo pomeriggio",
            additional_notes=f"Stile {style} con focus su estetica professionale"
        )

        # Salva immagine generata in file temporaneo
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(rendered_image)
            temp_path = f.name

        # Aggiorna status
        status.content = "✅ **Rendering completato!**"
        await status.update()

        # Mostra risultato
        await cl.Message(
            content="🌿 **Ecco il rendering del tuo nuovo giardino!**\n\nLa casa e le strutture sono rimaste identiche, ho trasformato solo il landscape.",
            elements=[
                cl.Image(path=temp_path, name="garden_rendering", display="inline")
            ]
        ).send()

        # Opzioni post-generazione
        await cl.Message(
            content="""💡 **Cosa puoi fare ora:**

• Chiedi modifiche specifiche (es. *"aggiungi più fiori"*, *"cambia forma piscina"*)
• Scrivi **"rigenera"** per un nuovo rendering
• Carica una nuova foto per un altro progetto

Dimmi cosa ne pensi!
"""
        ).send()

        cl.user_session.set("state", SessionState.GENERATED)

    except Exception as e:
        await cl.Message(content=f"❌ **Errore nella generazione:**\n\n{str(e)}\n\nRiprova o contatta il supporto.").send()


async def refine_current_rendering(service: GeminiImageService, feedback: str):
    """Raffina il rendering corrente basandosi sul feedback."""

    status = await cl.Message(content=f"🔄 **Modificando il rendering...**\n\n*{feedback}*").send()

    try:
        refined_image = await service.refine_rendering(feedback)

        # Salva immagine
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(refined_image)
            temp_path = f.name

        status.content = "✅ **Modifica completata!**"
        await status.update()

        await cl.Message(
            content="🌿 **Ecco il rendering aggiornato:**",
            elements=[
                cl.Image(path=temp_path, name="garden_rendering_refined", display="inline")
            ]
        ).send()

    except Exception as e:
        await cl.Message(content=f"❌ Errore nella modifica: {e}").send()


# =============================================================================
# STARTERS
# =============================================================================

@cl.set_starters
async def set_starters():
    """Suggerimenti iniziali."""
    return [
        cl.Starter(
            label="🏊 Voglio una piscina",
            message="Vorrei aggiungere una bella piscina al mio giardino",
        ),
        cl.Starter(
            label="🌿 Giardino verde",
            message="Vorrei un giardino con tanto verde, prato e piante",
        ),
        cl.Starter(
            label="🏝️ Stile tropicale",
            message="Mi piacerebbe uno stile tropicale con palme",
        ),
        cl.Starter(
            label="☯️ Giardino zen",
            message="Vorrei un giardino zen giapponese rilassante",
        ),
    ]


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY non configurata!")
        print("   Crea un file .env con: GOOGLE_API_KEY=your_key")

    print("\n🌿 Garden Design Bot pronto!")
    print("   Avvia con: chainlit run app.py")
