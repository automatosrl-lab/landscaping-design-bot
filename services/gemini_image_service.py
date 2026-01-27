"""
Servizio Gemini per Image Generation/Editing

Modelli (Gennaio 2026):
- gemini-3-flash-preview: Chat veloce (Gemini 3 Flash)
- gemini-3-pro-image-preview: Image generation (Nano Banana Pro)

Funzionalità:
- Analizzare foto di giardini
- Generare rendering modificando SOLO il landscape
- Preservare casa, muri, strutture esistenti

Fonte: https://ai.google.dev/gemini-api/docs/image-generation
"""

from google import genai
from google.genai import types
import base64
import httpx
from typing import Optional, List


class GeminiImageService:
    """
    Servizio unificato per chat + image editing con Gemini.

    Modelli utilizzati (Gennaio 2026):
    - gemini-3-flash-preview: Chat veloce con l'utente (Gemini 3 Flash)
    - gemini-3-pro-image-preview: Generazione/editing immagini (Nano Banana Pro)
    """

    def __init__(self, api_key: str):
        """
        Inizializza il servizio.

        Args:
            api_key: Google AI Studio API key
        """
        self.client = genai.Client(api_key=api_key)

        # Modelli - Aggiornati a Gennaio 2026
        # gemini-3-flash-preview: Chat veloce con thinking minimo
        # gemini-2.5-flash-image: Nano Banana (più quota gratuita disponibile)
        self.chat_model = "gemini-3-flash-preview"  # Gemini 3 Flash per chat
        self.image_model = "gemini-2.5-flash-image"  # Nano Banana per image generation (più quota)

        # Chat session per conversazione multi-turn
        self.chat_history = []

        # Immagine corrente in sessione (per editing iterativo)
        self.current_image = None
        self.original_image = None

    # =========================================================================
    # SYSTEM PROMPTS
    # =========================================================================

    CHAT_SYSTEM_PROMPT = """Sei un esperto consulente di garden design e landscaping con 20 anni di esperienza.
Il tuo nome è "Garden AI Designer".

## IL TUO RUOLO
Aiuti i clienti a visualizzare e progettare il giardino dei loro sogni.
Quando il cliente carica una foto, la analizzi e proponi miglioramenti.

## FLUSSO CONVERSAZIONE

1. **Accoglienza**: Saluta e chiedi di caricare una foto del giardino
2. **Analisi**: Quando ricevi la foto, descrivi cosa vedi e chiedi cosa vorrebbero cambiare
3. **Raccolta requisiti**: Chiedi su:
   - Stile (Moderno, Mediterraneo, Tropicale, Zen, Inglese)
   - Elementi da aggiungere (piscina, prato, piante, vialetti, illuminazione)
   - Cosa PRESERVARE (la casa, alberi specifici, muri)
4. **Conferma**: Riassumi le richieste prima di generare

## STILE
- Professionale ma amichevole
- Una domanda alla volta
- Suggerisci idee basate sulla foto
- Rispondi in italiano

## IMPORTANTE
- NON modificare mai strutture architettoniche (casa, fondamenta)
- Puoi modificare: giardino, prato, piante, vialetti, illuminazione, colore muri esterni, recinzioni
- Preserva SEMPRE la casa e le strutture principali"""

    IMAGE_EDITING_PROMPT_TEMPLATE = """Modifica questa immagine di un giardino/spazio esterno.

## REGOLE CRITICHE - LEGGI ATTENTAMENTE:

1. **PRESERVA ASSOLUTAMENTE** questi elementi senza alcuna modifica:
   - La casa/edificio principale (forma, finestre, porte, tetto)
   - Le fondamenta e strutture architettoniche
   - {preserve_elements}

2. **AGGIUNGI SOLO QUESTI ELEMENTI** (nient'altro!):
   {modifications}

3. **STILE RICHIESTO**: {style}

4. **QUALITÀ**:
   - Rendering fotorealistico professionale
   - Illuminazione naturale ({lighting})
   - Alta qualità, dettagli realistici

## DESCRIZIONE DETTAGLIATA DEL NUOVO GIARDINO:
{detailed_description}

## REGOLE FINALI OBBLIGATORIE:
- La casa e le strutture esistenti devono rimanere IDENTICHE
- Aggiungi SOLO gli elementi elencati sopra, nient'altro
- Il risultato deve sembrare una foto professionale di architettura del paesaggio"""

    # =========================================================================
    # CHAT METHODS
    # =========================================================================

    async def chat(self, message: str, image_data: Optional[bytes] = None) -> str:
        """
        Chat con Gemini Flash per conversazione.

        Args:
            message: Messaggio utente
            image_data: Immagine opzionale

        Returns:
            Risposta del bot
        """
        contents = []

        # Aggiungi system prompt se è il primo messaggio
        if not self.chat_history:
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"[SYSTEM]: {self.CHAT_SYSTEM_PROMPT}")]
            ))
            contents.append(types.Content(
                role="model",
                parts=[types.Part.from_text(text="Capito, sono pronto ad aiutare come consulente di garden design.")]
            ))

        # Aggiungi history
        contents.extend(self.chat_history)

        # Prepara messaggio corrente
        parts = []
        if image_data:
            # Salva immagine originale
            self.original_image = image_data
            self.current_image = image_data

            parts.append(types.Part.from_bytes(
                data=image_data,
                mime_type="image/jpeg"
            ))

        parts.append(types.Part.from_text(text=message))

        contents.append(types.Content(role="user", parts=parts))

        # Genera risposta
        response = self.client.models.generate_content(
            model=self.chat_model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
            )
        )

        response_text = response.text

        # Aggiorna history
        self.chat_history.append(types.Content(role="user", parts=parts))
        self.chat_history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=response_text)]
        ))

        return response_text

    # =========================================================================
    # IMAGE EDITING METHODS
    # =========================================================================

    async def generate_landscape_rendering(
        self,
        image_data: bytes,
        style: str,
        modifications: List[str],
        preserve_elements: List[str] = None,
        lighting: str = "golden hour, pomeriggio",
        additional_notes: str = ""
    ) -> bytes:
        """
        Genera un rendering del giardino modificando SOLO il landscape.
        """
        # Prepara lista elementi da preservare
        preserve_list = ["la casa principale", "le finestre e porte", "il tetto", "le fondamenta"]
        if preserve_elements:
            preserve_list.extend(preserve_elements)

        # Mappa stili a descrizioni
        style_descriptions = {
            "modern": "Moderno e minimalista con linee pulite, materiali contemporanei come cemento e acciaio corten, piante architettoniche",
            "mediterranean": "Mediterraneo caldo con terracotta, ulivi, lavanda, pergole in legno, ghiaia naturale",
            "tropical": "Tropicale lussureggiante con palme, piante esotiche, piscina naturale, legno esotico",
            "zen": "Giapponese zen con ghiaia rastrellata, muschio, lanterne di pietra, bambù, acqua",
            "english": "Giardino all'inglese romantico con rose, bordure fiorite, prato verde, archi",
            "contemporary": "Contemporaneo con outdoor living, cucina esterna, fire pit, sedute integrate"
        }

        style_desc = style_descriptions.get(style, style_descriptions["modern"])

        # Costruisci descrizione dettagliata
        modifications_text = "\n   - ".join(modifications) if modifications else "Miglioramento generale del landscape"
        preserve_text = "\n   - ".join(preserve_list)

        detailed_desc = f"""
Trasforma questo giardino in uno spazio esterno {style_desc}.

Elementi da aggiungere/modificare:
- {modifications_text}

{additional_notes}

Il rendering deve essere fotorealistico, come una foto professionale di architettura del paesaggio
scattata con una Canon EOS 5D, luce naturale {lighting}.
"""

        # Costruisci prompt finale
        prompt = self.IMAGE_EDITING_PROMPT_TEMPLATE.format(
            preserve_elements=preserve_text,
            modifications=modifications_text,
            style=style_desc,
            lighting=lighting,
            detailed_description=detailed_desc
        )

        # Genera immagine con Gemini
        contents = [
            types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt)
        ]

        response = self.client.models.generate_content(
            model=self.image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=0.4,
            )
        )

        # Estrai immagine dalla risposta
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                self.current_image = part.inline_data.data
                return part.inline_data.data

        raise ValueError("Nessuna immagine generata nella risposta")

    async def refine_rendering(self, feedback: str) -> bytes:
        """
        Raffina il rendering corrente basandosi sul feedback.
        """
        if self.current_image is None:
            raise ValueError("Nessuna immagine corrente da raffinare")

        prompt = f"""Modifica questa immagine di giardino secondo il seguente feedback:

{feedback}

IMPORTANTE:
- Mantieni TUTTI gli altri elementi invariati
- La casa e le strutture devono rimanere IDENTICHE
- Modifica SOLO quello che è stato richiesto nel feedback
- Il risultato deve essere fotorealistico"""

        contents = [
            types.Part.from_bytes(data=self.current_image, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt)
        ]

        response = self.client.models.generate_content(
            model=self.image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        # Estrai immagine
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                self.current_image = part.inline_data.data
                return part.inline_data.data

        raise ValueError("Nessuna immagine generata")

    async def analyze_garden(self, image_data: bytes) -> dict:
        """
        Analizza una foto di giardino per identificare elementi.
        """
        prompt = """Analizza questa foto di uno spazio esterno/giardino.

Restituisci una descrizione strutturata con:

1. **ELEMENTI ESISTENTI**: Cosa c'è attualmente (casa, prato, alberi, pavimentazione, ecc.)
2. **CONDIZIONI**: Stato attuale del giardino (curato, trascurato, parzialmente sviluppato)
3. **DIMENSIONI STIMATE**: Approssimazione della metratura
4. **ESPOSIZIONE**: Orientamento solare visibile
5. **STILE CASA**: Stile architettonico dell'edificio se visibile
6. **POTENZIALE**: Cosa si potrebbe migliorare o aggiungere
7. **ELEMENTI DA PRESERVARE**: Cosa sarebbe importante mantenere

Rispondi in italiano in modo chiaro e strutturato."""

        contents = [
            types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt)
        ]

        response = self.client.models.generate_content(
            model=self.chat_model,
            contents=contents,
        )

        return {
            "analysis": response.text,
            "has_image": True
        }

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def reset_session(self):
        """Resetta la sessione corrente."""
        self.chat_history = []
        self.current_image = None
        self.original_image = None

    def get_original_image(self) -> Optional[bytes]:
        """Restituisce l'immagine originale caricata."""
        return self.original_image

    def get_current_image(self) -> Optional[bytes]:
        """Restituisce l'ultima immagine generata."""
        return self.current_image

    @staticmethod
    def image_to_base64(image_data: bytes) -> str:
        """Converte immagine in base64."""
        return base64.b64encode(image_data).decode()

    @staticmethod
    async def download_image(url: str) -> bytes:
        """Scarica immagine da URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.content
