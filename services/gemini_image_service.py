"""
Servizio Gemini per Image Generation/Editing

Usa Gemini 2.0 Flash per:
- Chat con l'utente
- Analizzare foto di giardini
- Generare rendering modificando SOLO il landscape
- Preservare casa, muri, strutture esistenti
"""

import google.generativeai as genai
import base64
import httpx
from typing import Optional, List
from PIL import Image
import io


class GeminiImageService:
    """
    Servizio unificato per chat + image editing con Gemini.
    """

    def __init__(self, api_key: str):
        """
        Inizializza il servizio.

        Args:
            api_key: Google AI Studio API key
        """
        genai.configure(api_key=api_key)

        # Modello per chat e image generation
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 2048,
            }
        )

        # Chat session
        self.chat_session = None

        # Immagine corrente in sessione
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

2. **MODIFICA SOLO** l'area del giardino/landscape:
   {modifications}

3. **STILE RICHIESTO**: {style}

4. **QUALITÀ**:
   - Rendering fotorealistico professionale
   - Illuminazione naturale ({lighting})
   - Alta qualità, dettagli realistici

## DESCRIZIONE DETTAGLIATA DEL NUOVO GIARDINO:
{detailed_description}

IMPORTANTE: La casa e le strutture esistenti devono rimanere IDENTICHE.
Modifica SOLO il giardino, il prato, le piante e gli elementi esterni del landscape.
Il risultato deve sembrare una foto professionale di architettura del paesaggio."""

    # =========================================================================
    # CHAT METHODS
    # =========================================================================

    def _start_chat(self):
        """Avvia una nuova sessione di chat."""
        self.chat_session = self.model.start_chat(
            history=[
                {"role": "user", "parts": [f"[SYSTEM]: {self.CHAT_SYSTEM_PROMPT}"]},
                {"role": "model", "parts": ["Capito, sono pronto ad aiutare come consulente di garden design. Benvenuto! Sono il tuo Garden AI Designer. Carica una foto del tuo giardino e dimmi come vorresti trasformarlo."]}
            ]
        )

    async def chat(self, message: str, image_data: Optional[bytes] = None) -> str:
        """
        Chat con Gemini per conversazione.

        Args:
            message: Messaggio utente
            image_data: Immagine opzionale

        Returns:
            Risposta del bot
        """
        if self.chat_session is None:
            self._start_chat()

        # Prepara il contenuto
        parts = []

        if image_data:
            # Salva immagine originale
            self.original_image = image_data
            self.current_image = image_data

            # Converti in PIL Image
            img = Image.open(io.BytesIO(image_data))
            parts.append(img)

        parts.append(message)

        # Genera risposta
        response = self.chat_session.send_message(parts)

        return response.text

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

        Args:
            image_data: Immagine originale del giardino
            style: Stile desiderato
            modifications: Lista di modifiche da applicare
            preserve_elements: Elementi da preservare oltre la casa
            lighting: Tipo di illuminazione
            additional_notes: Note aggiuntive dal cliente

        Returns:
            Immagine generata in bytes
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

        # Converti immagine
        img = Image.open(io.BytesIO(image_data))

        # Genera con Gemini
        response = self.model.generate_content(
            [img, prompt],
            generation_config={
                "temperature": 0.4,
            }
        )

        # Per ora Gemini 2.0 Flash non genera immagini direttamente via API pubblica
        # Restituiamo l'immagine originale con una nota
        # In produzione useresti Imagen o Flux

        # Placeholder: restituisce l'originale
        # TODO: Integrare con Imagen API quando disponibile
        self.current_image = image_data

        return image_data

    async def refine_rendering(self, feedback: str) -> bytes:
        """
        Raffina il rendering corrente basandosi sul feedback.
        """
        if self.current_image is None:
            raise ValueError("Nessuna immagine corrente da raffinare")

        # Placeholder
        return self.current_image

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

        # Converti immagine
        img = Image.open(io.BytesIO(image_data))

        response = self.model.generate_content([img, prompt])

        return {
            "analysis": response.text,
            "has_image": True
        }

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def reset_session(self):
        """Resetta la sessione corrente."""
        self.chat_session = None
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
