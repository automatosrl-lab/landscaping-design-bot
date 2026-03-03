"""
Servizio per Chat + Image Generation/Editing via OpenRouter

Modelli (Marzo 2026):
- google/gemini-3-flash-preview: Chat veloce (Gemini 3 Flash)
- google/gemini-3-pro-image-preview: Image generation (Nano Banana Pro)

OpenRouter API (compatibile OpenAI)
Fonte: https://openrouter.ai/docs/guides/overview/multimodal/image-generation
"""

import base64
import httpx
import json
import logging
import re
from typing import Optional, List

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class GeminiImageService:
    """
    Servizio unificato per chat + image editing via OpenRouter.

    Modelli utilizzati (Marzo 2026):
    - google/gemini-3-flash-preview: Chat veloce (Gemini 3 Flash)
    - google/gemini-3-pro-image-preview: Generazione/editing immagini (Nano Banana Pro)
    """

    def __init__(self, api_key: str):
        """
        Inizializza il servizio.

        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gardendesignai.app",
            "X-Title": "Garden Design AI",
        }

        # Modelli - Marzo 2026 via OpenRouter
        self.chat_model = "google/gemini-3-flash-preview"
        self.image_model = "google/gemini-3-pro-image-preview"  # Nano Banana Pro

        # Chat history (formato OpenAI messages)
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

## REGOLE CRITICHE - RISPETTA RIGOROSAMENTE:

### 1. PRESERVA SENZA MODIFICHE:
- La casa/edificio principale (forma, finestre, porte, tetto)
- Le fondamenta e strutture architettoniche
- {preserve_elements}

### 2. AGGIUNGI SOLO ED ESCLUSIVAMENTE QUESTI ELEMENTI:
{modifications}

### 3. VIETATO AGGIUNGERE (anche se sembrano adatti allo stile):
- Vialetti o sentieri (SE NON nella lista sopra)
- Gazebo, pergole, tettoie (SE NON nella lista sopra)
- Fontane o elementi d'acqua (SE NON nella lista sopra)
- Area barbecue o cucina esterna (SE NON nella lista sopra)
- Sedute, divani, mobili da esterno (SE NON nella lista sopra)
- Illuminazione (SE NON nella lista sopra)
- QUALSIASI elemento non esplicitamente elencato al punto 2

### 4. STILE: {style}
(Lo stile influenza SOLO l'aspetto degli elementi richiesti, NON aggiungere elementi tipici dello stile se non richiesti!)

### 5. QUALITÀ: Rendering fotorealistico professionale, illuminazione naturale ({lighting})

{detailed_description}

## ISTRUZIONI FINALI OBBLIGATORIE:
1. La casa DEVE rimanere IDENTICA
2. Aggiungi SOLO ED ESCLUSIVAMENTE gli elementi elencati al punto 2
3. NON aggiungere NULLA che non sia nella lista - anche se "starebbe bene" o è tipico dello stile
4. Se la lista dice solo "prato e piante", metti SOLO prato e piante, NIENT'ALTRO"""

    # =========================================================================
    # API HELPERS
    # =========================================================================

    async def _call_openrouter(
        self,
        model: str,
        messages: list,
        modalities: list = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict:
        """Chiama l'API OpenRouter e restituisce la risposta JSON."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if modalities:
            payload["modalities"] = modalities

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=self.headers,
                json=payload,
            )

            if response.status_code != 200:
                error_body = response.text[:500]
                logger.error(f"OpenRouter errore {response.status_code}: {error_body}")
                raise ValueError(
                    f"Errore API ({response.status_code}): {error_body}"
                )

            return response.json()

    @staticmethod
    def _image_to_data_url(image_data: bytes, mime_type: str = "image/jpeg") -> str:
        """Converte immagine bytes in data URL base64."""
        b64 = base64.b64encode(image_data).decode()
        return f"data:{mime_type};base64,{b64}"

    def _extract_text_from_response(self, data: dict) -> str:
        """Estrai testo dalla risposta OpenRouter."""
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("Nessuna risposta dal modello")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if isinstance(content, str):
            return content

        # Se content è un array, concatena le parti testuali
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            return "\n".join(text_parts)

        return str(content)

    def _extract_image_from_response(self, data: dict) -> bytes:
        """Estrai immagine dalla risposta OpenRouter con error handling robusto."""
        choices = data.get("choices", [])
        if not choices:
            error = data.get("error", {})
            if error:
                raise ValueError(f"Errore dal modello: {error.get('message', error)}")
            raise ValueError("Nessuna risposta dal modello")

        message = choices[0].get("message", {})

        # 1. Cerca in message.images[] (formato OpenRouter)
        images = message.get("images", [])
        if images:
            for img in images:
                url = ""
                if isinstance(img, dict):
                    url = img.get("image_url", {}).get("url", "")
                if url.startswith("data:image"):
                    b64_data = url.split(",", 1)[1]
                    return base64.b64decode(b64_data)

        # 2. Cerca in content array (formato OpenAI vision)
        content = message.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("data:image"):
                            b64_data = url.split(",", 1)[1]
                            return base64.b64decode(b64_data)

        # 3. Cerca data URL nel testo della risposta
        if isinstance(content, str) and "data:image" in content:
            match = re.search(
                r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content
            )
            if match:
                return base64.b64decode(match.group(1))

        # Nessuna immagine trovata — restituisci errore descrittivo
        finish_reason = choices[0].get("finish_reason", "unknown")
        text_content = content if isinstance(content, str) else str(content)
        if len(text_content) > 200:
            text_content = text_content[:200] + "..."

        logger.error(
            f"Nessuna immagine nella risposta. finish_reason={finish_reason}, "
            f"content={text_content}"
        )
        raise ValueError(
            f"Il modello non ha generato un'immagine. "
            f"Risposta: {text_content}"
        )

    def _build_image_message(self, image_data: bytes, text: str) -> dict:
        """Costruisce un messaggio utente con immagine + testo."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._image_to_data_url(image_data),
                    },
                },
                {"type": "text", "text": text},
            ],
        }

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
        # Costruisci messages
        messages = [{"role": "system", "content": self.CHAT_SYSTEM_PROMPT}]
        messages.extend(self.chat_history)

        # Messaggio corrente
        if image_data:
            self.original_image = image_data
            self.current_image = image_data
            user_msg = self._build_image_message(image_data, message)
        else:
            user_msg = {"role": "user", "content": message}

        messages.append(user_msg)

        # Chiama API
        data = await self._call_openrouter(
            model=self.chat_model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        response_text = self._extract_text_from_response(data)

        # Aggiorna history (salva solo testo per non esplodere la memoria)
        self.chat_history.append({"role": "user", "content": message})
        self.chat_history.append({"role": "assistant", "content": response_text})

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
        additional_notes: str = "",
    ) -> bytes:
        """
        Genera un rendering del giardino modificando SOLO il landscape.
        """
        # Prepara lista elementi da preservare
        preserve_list = [
            "la casa principale",
            "le finestre e porte",
            "il tetto",
            "le fondamenta",
        ]
        if preserve_elements:
            preserve_list.extend(preserve_elements)

        # Mappa stili a descrizioni
        style_descriptions = {
            "modern": "Moderno e minimalista con linee pulite, materiali contemporanei come cemento e acciaio corten, piante architettoniche",
            "mediterranean": "Mediterraneo caldo con terracotta, ulivi, lavanda, pergole in legno, ghiaia naturale",
            "tropical": "Tropicale lussureggiante con palme, piante esotiche, piscina naturale, legno esotico",
            "zen": "Giapponese zen con ghiaia rastrellata, muschio, lanterne di pietra, bambù, acqua",
            "english": "Giardino all'inglese romantico con rose, bordure fiorite, prato verde, archi",
            "contemporary": "Contemporaneo con outdoor living, cucina esterna, fire pit, sedute integrate",
        }

        style_desc = style_descriptions.get(style, style_descriptions["modern"])

        # Costruisci descrizione dettagliata
        modifications_text = (
            "\n- ".join(modifications)
            if modifications
            else "Miglioramento generale del landscape"
        )
        preserve_text = "\n- ".join(preserve_list)

        detailed_desc = f"""
Trasforma questo giardino in uno spazio esterno {style_desc}.

LISTA COMPLETA DEGLI ELEMENTI DA AGGIUNGERE:
- {modifications_text}

IMPORTANTE: Aggiungi SOLO gli elementi elencati qui sopra. Non aggiungere nient'altro.

{additional_notes}

Il rendering deve essere fotorealistico, come una foto professionale scattata con Canon EOS 5D.
"""

        # Costruisci prompt finale
        prompt = self.IMAGE_EDITING_PROMPT_TEMPLATE.format(
            preserve_elements=preserve_text,
            modifications=modifications_text,
            style=style_desc,
            lighting=lighting,
            detailed_description=detailed_desc,
        )

        # Chiama OpenRouter con modello immagine
        messages = [self._build_image_message(image_data, prompt)]

        data = await self._call_openrouter(
            model=self.image_model,
            messages=messages,
            modalities=["image", "text"],
            temperature=0.4,
            max_tokens=4096,
        )

        # Estrai immagine
        image_result = self._extract_image_from_response(data)
        self.current_image = image_result
        return image_result

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

        messages = [self._build_image_message(self.current_image, prompt)]

        data = await self._call_openrouter(
            model=self.image_model,
            messages=messages,
            modalities=["image", "text"],
            temperature=0.4,
            max_tokens=4096,
        )

        image_result = self._extract_image_from_response(data)
        self.current_image = image_result
        return image_result

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

        messages = [self._build_image_message(image_data, prompt)]

        data = await self._call_openrouter(
            model=self.chat_model,
            messages=messages,
            temperature=0.5,
            max_tokens=1024,
        )

        return {
            "analysis": self._extract_text_from_response(data),
            "has_image": True,
        }

    # =========================================================================
    # AI INTERPRETATION
    # =========================================================================

    async def interpret_user_request(self, user_message: str, style: str) -> dict:
        """
        Usa l'AI per interpretare la richiesta dell'utente e tradurla in parametri strutturati.

        Returns:
            dict con: elements (lista), excluded (lista), summary (stringa breve)
        """
        prompt = f"""Sei un interprete ESPERTO di richieste per garden design e landscaping.

STILE SCELTO: {style}

RICHIESTA UTENTE:
"{user_message}"

## IL TUO COMPITO:
Analizza la richiesta e traduci ESATTAMENTE quello che l'utente vuole in elementi per il giardino.
Sii FEDELE alla richiesta: se chiede un "laghetto con pesci koi e ponte rosso", scrivi esattamente quello.

## REGOLE:

1. ELEMENTI DA AGGIUNGERE (metti in "elements"):
   - Tutto ciò che l'utente vuole nel giardino
   - Mantieni i dettagli specifici (colori, materiali, posizioni)
   - Esempi:
     * "laghetto con pesci koi" → "laghetto con pesci koi"
     * "ponte di legno rosso" → "ponte di legno rosso in stile giapponese"
     * "statua di Buddha" → "statua di Buddha"
     * "albero di ciliegio" → "albero di ciliegio (sakura)"

2. ELEMENTI DA ESCLUDERE (metti in "excluded"):
   - Quando dice "niente X", "no X", "non voglio X", "senza X"

3. REGOLA "SOLO X":
   - Se dice "solo X", escludi automaticamente tutto il resto
   - excluded: ["vialetti", "pergola", "gazebo", "fontana", "illuminazione", "area barbecue", "sedute", "mobili"]

4. RICHIESTE FUORI AMBITO (metti in "out_of_scope"):
   - Modifiche alla CASA (finestre, porte, tetto, facciata, colore muri della casa)
   - Modifiche ARCHITETTONICHE (fondamenta, strutture, ampliamenti)
   - Interni della casa
   - Se l'utente chiede queste cose, mettile in "out_of_scope"

5. ELEMENTI GIÀ ESISTENTI: se dice "c'è già", non mettere in nessuna lista

RISPONDI CON QUESTO JSON (senza markdown):
{{
    "elements": ["elemento1 con dettagli", "elemento2 con dettagli"],
    "excluded": ["cosa non mettere"],
    "out_of_scope": ["richieste fuori ambito (casa, architettura)"],
    "summary": "Riassunto breve"
}}"""

        messages = [{"role": "user", "content": prompt}]

        data = await self._call_openrouter(
            model=self.chat_model,
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )

        response_text = self._extract_text_from_response(data)

        # Parse JSON dalla risposta
        try:
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "elements": [user_message],
                "excluded": [],
                "summary": user_message[:100],
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
