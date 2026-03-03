"""
Landscaping Design Bot - Applicazione Chainlit

Chatbot AI per garden design con rendering automatico.
Usa Gemini via OpenRouter per:
- Chat (Gemini 3 Flash)
- Image Generation/Editing (Nano Banana Pro)

Il sistema modifica SOLO il landscape preservando casa e strutture.
"""

import chainlit as cl
import os
import logging
import asyncio
from dotenv import load_dotenv
from typing import Optional
import base64
import io
from PIL import Image

logger = logging.getLogger(__name__)

# Carica variabili ambiente
load_dotenv()

# Import servizio
from services.gemini_image_service import GeminiImageService

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

MAX_IMAGE_SIZE = 1600  # px lato lungo
MAX_IMAGE_BYTES = 1_500_000  # ~1.5MB


def compress_image(image_data: bytes) -> bytes:
    """Ridimensiona e comprimi l'immagine per evitare payload troppo grandi."""
    img = Image.open(io.BytesIO(image_data))

    # Converti RGBA/palette in RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Ridimensiona se troppo grande
    w, h = img.size
    if max(w, h) > MAX_IMAGE_SIZE:
        ratio = MAX_IMAGE_SIZE / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        logger.info(f"Immagine ridimensionata: {w}x{h} -> {new_size[0]}x{new_size[1]}")

    # Comprimi come JPEG
    buffer = io.BytesIO()
    quality = 85
    img.save(buffer, format="JPEG", quality=quality, optimize=True)

    # Se ancora troppo grande, riduci qualità
    while buffer.tell() > MAX_IMAGE_BYTES and quality > 40:
        quality -= 10
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)

    result = buffer.getvalue()
    logger.info(f"Immagine compressa: {len(image_data)} -> {len(result)} bytes (quality={quality})")
    return result


def get_service() -> GeminiImageService:
    """Ottiene o crea il servizio per la sessione corrente (NON globale)."""
    service = cl.user_session.get("service")
    if service is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY non configurata")
        service = GeminiImageService(api_key)
        cl.user_session.set("service", service)
    return service


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
        # Verifica API key all'avvio
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY non configurata")
        # Crea un servizio NUOVO per questa sessione (ogni sessione ha il suo)
        service = GeminiImageService(api_key)
        cl.user_session.set("service", service)
    except ValueError as e:
        await cl.Message(
            content=f"⚠️ Errore di configurazione: {e}\n\nConfigura OPENROUTER_API_KEY nelle variabili ambiente."
        ).send()
        return

    # Inizializza stato sessione
    cl.user_session.set("state", SessionState.WELCOME)
    cl.user_session.set("uploaded_image", None)
    cl.user_session.set("style", None)
    cl.user_session.set("elements", [])  # Elementi DA aggiungere
    cl.user_session.set("excluded", [])  # Elementi DA ESCLUDERE
    cl.user_session.set("user_description", "")  # Descrizione originale utente
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
            if hasattr(element, "mime") and element.mime and "image" in element.mime:
                with open(element.path, "rb") as f:
                    raw_data = f.read()
                # Comprimi per evitare payload troppo grandi
                image_data = compress_image(raw_data)
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
    status = await cl.Message(content="📸 **Foto ricevuta!**").send()

    try:
        # Analizza l'immagine INTERNAMENTE (non mostrare all'utente)
        analysis = await service.analyze_garden(image_data)
        # Salva l'analisi per uso interno nel prompt
        cl.user_session.set("photo_analysis", analysis['analysis'])

        # Chiedi direttamente cosa vuole l'utente
        await cl.Message(
            content="""Perfetto! Ho analizzato il tuo spazio.

**Che tipo di giardino vorresti?** Scegli uno stile:

• 🏛️ **Moderno** - Linee pulite, minimalista
• 🌿 **Mediterraneo** - Ulivi, lavanda, caldo
• 🌴 **Tropicale** - Palme, piante esotiche
• ☯️ **Zen** - Giapponese, sereno
• 🌹 **Inglese** - Romantico, fiori, rose
• 🔥 **Contemporaneo** - Outdoor living, fire pit
"""
        ).send()

        cl.user_session.set("state", SessionState.COLLECTING_STYLE)

        # Se l'utente ha scritto qualcosa insieme all'immagine, processalo
        if user_message and len(user_message) > 5:
            await handle_chat(service, user_message)

    except Exception as e:
        await cl.Message(content=f"❌ Errore: {e}").send()


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
        # Salva la descrizione originale dell'utente
        cl.user_session.set("user_description", user_message)
        style = cl.user_session.get("style", "modern")

        # Usa l'AI per interpretare la richiesta
        status_msg = await cl.Message(content="🤔 Sto elaborando la tua richiesta...").send()

        try:
            interpretation = await service.interpret_user_request(user_message, style)

            detected_elements = interpretation.get("elements", [])
            excluded_elements = interpretation.get("excluded", [])
            out_of_scope = interpretation.get("out_of_scope", [])
            summary = interpretation.get("summary", "")

            cl.user_session.set("elements", detected_elements)
            cl.user_session.set("excluded", excluded_elements)

            # Aggiorna messaggio status
            status_msg.content = "✅ Ho capito!"
            await status_msg.update()

            # Se ci sono richieste fuori ambito, avvisa l'utente
            if out_of_scope:
                out_of_scope_list = "\n".join([f"  • {item}" for item in out_of_scope])
                await cl.Message(
                    content=f"""⚠️ **Nota importante:**

Sono un esperto di **garden design e landscaping**. Mi occupo esclusivamente della progettazione di giardini e spazi esterni.

Non posso modificare:
{out_of_scope_list}

Queste modifiche richiedono un architetto o un professionista dell'edilizia.

Posso però aiutarti a trasformare il tuo giardino! 🌿
"""
                ).send()

            # Se non ci sono elementi validi da aggiungere
            if not detected_elements:
                await cl.Message(
                    content="""Non ho trovato elementi di landscaping da aggiungere nella tua richiesta.

Dimmi cosa vorresti nel tuo giardino: prato, piante, piscina, vialetti, fontane, illuminazione...
"""
                ).send()
                return

            # Mostra riepilogo compatto
            elements_list = "\n".join([f"  ✅ {el}" for el in detected_elements])
            excluded_section = ""
            if excluded_elements:
                excluded_list = "\n".join([f"  ❌ {el}" for el in excluded_elements])
                excluded_section = f"\n\n**Non aggiungerò:**\n{excluded_list}"

            await cl.Message(
                content=f"""📋 **Riepilogo:**

**Stile:** {style.title()}

**Aggiungerò:**
{elements_list}{excluded_section}

Scrivi **"ok"** per generare, oppure dimmi se vuoi modificare qualcosa.
"""
            ).send()

            cl.user_session.set("state", SessionState.READY_TO_GENERATE)
            return

        except Exception as e:
            await cl.Message(content=f"❌ Errore nell'interpretazione: {e}").send()
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
    excluded = cl.user_session.get("excluded", [])
    user_description = cl.user_session.get("user_description", "")

    # Costruisci note aggiuntive con esclusioni
    additional = f"Stile {style} con focus su estetica professionale."
    if excluded:
        excluded_text = ", ".join(excluded)
        additional += f"\n\nIMPORTANTE - NON AGGIUNGERE ASSOLUTAMENTE: {excluded_text}. Il cliente ha esplicitamente richiesto di NON includere questi elementi."
    if user_description:
        additional += f"\n\nRichiesta originale del cliente: {user_description}"

    logger.info(f"Avvio generazione: style={style}, elements={elements}, image_size={len(image_data)} bytes")

    # Messaggio di progresso - aggiornato periodicamente per tenere vivo il WebSocket
    progress_msg = await cl.Message(content="🎨 **Generazione rendering in corso...**\n\n⏳ Preparazione prompt...").send()

    try:
        # Lancia la generazione come task asincrono
        generation_task = asyncio.create_task(
            service.generate_landscape_rendering(
                image_data=image_data,
                style=style,
                modifications=elements,
                preserve_elements=["alberi esistenti da preservare"],
                lighting="golden hour, tardo pomeriggio",
                additional_notes=additional
            )
        )

        # Keepalive: aggiorna il messaggio ogni 5 secondi per tenere vivo il WebSocket
        elapsed = 0
        animations = ["🎨", "🖌️", "🖼️", "✨"]
        while not generation_task.done():
            await asyncio.sleep(5)
            elapsed += 5
            icon = animations[(elapsed // 5) % len(animations)]
            progress_msg.content = f"{icon} **Generazione rendering in corso...**\n\n⏳ Elaborazione in corso... ({elapsed}s)"
            await progress_msg.update()
            logger.info(f"Keepalive: {elapsed}s trascorsi")

        # Ottieni il risultato (solleva eccezione se la task è fallita)
        rendered_image = generation_task.result()

        logger.info(f"Immagine ricevuta: {len(rendered_image)} bytes")

        # Aggiorna messaggio progresso
        progress_msg.content = f"✅ **Rendering completato!** ({len(rendered_image) // 1024} KB generati in ~{elapsed}s)"
        await progress_msg.update()

        # Salva immagine generata in file temporaneo
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(rendered_image)
            temp_path = f.name

        logger.info(f"Immagine salvata in {temp_path}")

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
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"Errore generazione rendering: {error_msg}")
        import traceback
        logger.error(traceback.format_exc())

        # Aggiorna il messaggio di progresso con l'errore
        progress_msg.content = f"❌ **Errore nella generazione:**\n\n`{error_msg}`\n\nRiprova o contatta il supporto."
        await progress_msg.update()


async def refine_current_rendering(service: GeminiImageService, feedback: str):
    """Raffina il rendering corrente basandosi sul feedback."""

    progress_msg = await cl.Message(content=f"🔄 **Modificando il rendering...**\n\n*{feedback}*").send()

    try:
        # Lancia la raffinazione come task asincrono con keepalive
        refine_task = asyncio.create_task(service.refine_rendering(feedback))

        elapsed = 0
        while not refine_task.done():
            await asyncio.sleep(5)
            elapsed += 5
            progress_msg.content = f"🔄 **Modificando il rendering...**\n\n*{feedback}*\n\n⏳ Elaborazione... ({elapsed}s)"
            await progress_msg.update()

        refined_image = refine_task.result()

        # Salva immagine
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(refined_image)
            temp_path = f.name

        progress_msg.content = "✅ **Modifica completata!**"
        await progress_msg.update()

        await cl.Message(
            content="🌿 **Ecco il rendering aggiornato:**",
            elements=[
                cl.Image(path=temp_path, name="garden_rendering_refined", display="inline")
            ]
        ).send()

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"Errore raffinazione: {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        progress_msg.content = f"❌ **Errore nella modifica:**\n\n`{error_msg}`"
        await progress_msg.update()


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
    if not os.getenv("OPENROUTER_API_KEY"):
        print("⚠️  OPENROUTER_API_KEY non configurata!")
        print("   Crea un file .env con: OPENROUTER_API_KEY=your_key")

    print("\n🌿 Garden Design Bot pronto!")
    print("   Avvia con: chainlit run app.py")
