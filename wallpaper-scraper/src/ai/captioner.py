"""AI-powered wallpaper captioning using BLIP or Moondream2.

Generates human-readable titles, descriptive alt text, and social-media-style tags.
"""
import io
import re
from typing import Optional

from PIL import Image

from src.downloader.compressor import color_to_name, get_dominant_colors
from src.utils.aspect_ratio import is_mobile
from src.utils.logging import get_logger

logger = get_logger("captioner")


class WallpaperCaptioner:
    """Generates titles, alt text, and tags for wallpaper images.

    Auto-detects hardware:
    - GPU available (CUDA/MPS) -> loads Moondream2 for better quality
    - CPU only -> loads BLIP-large (reliable and fast enough)
    """

    def __init__(self, model_name: str = "auto"):
        self._model = None
        self._processor = None
        self._model_type: Optional[str] = None
        self._device = "cpu"
        self._requested_model = model_name
        self._loaded = False
        self._unavailable = False  # True if torch/transformers not installed

    def load(self) -> str:
        """Load the AI model. Returns the model type loaded."""
        if self._loaded:
            return self._model_type
        if self._unavailable:
            return "fallback"

        try:
            import torch
        except ImportError:
            logger.warning("torch not installed — AI captioning unavailable, using color-based fallback")
            self._unavailable = True
            return "fallback"

        # Detect hardware
        if torch.cuda.is_available():
            self._device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        logger.info("Detected device: %s", self._device)

        # Choose model
        use_moondream = (
            self._requested_model == "moondream2"
            or (self._requested_model == "auto" and self._device in ("cuda", "mps"))
        )

        if use_moondream:
            try:
                self._load_moondream()
                self._model_type = "moondream2"
                self._loaded = True
                logger.info("Loaded Moondream2 model on %s", self._device)
                return self._model_type
            except Exception as e:
                logger.warning("Failed to load Moondream2, falling back to BLIP: %s", e)

        # Load BLIP (default / fallback)
        self._load_blip()
        self._model_type = "blip"
        self._loaded = True
        logger.info("Loaded BLIP model on %s", self._device)
        return self._model_type

    def _load_blip(self) -> None:
        """Load Salesforce BLIP-large model."""
        from transformers import BlipForConditionalGeneration, BlipProcessor

        self._processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-large"
        )
        self._model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-large"
        ).to(self._device)
        self._model.eval()

    def _load_moondream(self) -> None:
        """Load Moondream2 model."""
        import torch
        from transformers import AutoModelForCausalLM

        dtype = torch.float32 if self._device == "cpu" else torch.float16
        device_map = {"": self._device} if self._device != "cpu" else None

        self._model = AutoModelForCausalLM.from_pretrained(
            "vikhyatk/moondream2",
            revision="2025-01-09",
            trust_remote_code=True,
            torch_dtype=dtype,
            device_map=device_map,
        )

    def generate_title(self, image: Image.Image) -> str:
        """Generate a creative, human-readable wallpaper title (3-8 words, Title Case)."""
        if not self._loaded:
            self.load()
        if self._unavailable:
            return self._fallback_title(image)

        try:
            if self._model_type == "moondream2":
                raw = self._moondream_query(
                    image,
                    "Give this wallpaper a creative short title in 3-6 words. "
                    "Be descriptive like a photographer naming their work. "
                    "Just the title, no quotes.",
                )
            else:
                raw = self._blip_generate(image, prompt="a wallpaper titled")

            return self._clean_title(raw)
        except Exception as e:
            logger.warning("Title generation failed: %s", e)
            return self._fallback_title(image)

    def generate_alt_text(self, image: Image.Image) -> str:
        """Generate descriptive accessibility-style alt text (1-2 sentences)."""
        if not self._loaded:
            self.load()
        if self._unavailable:
            return "A wallpaper image."

        try:
            if self._model_type == "moondream2":
                raw = self._moondream_query(
                    image,
                    "Describe this wallpaper image in 1-2 sentences for someone who "
                    "cannot see it. Be specific about colors, subjects, and composition.",
                )
            else:
                raw = self._blip_generate(image, prompt=None)

            return self._clean_alt_text(raw)
        except Exception as e:
            logger.warning("Alt text generation failed: %s", e)
            return "A wallpaper image"

    def generate_tags(self, image: Image.Image) -> str:
        """Generate comma-separated tags in Instagram/Tumblr style (10-20 tags)."""
        if not self._loaded:
            self.load()
        if self._unavailable:
            return self._fallback_tags(image)

        try:
            if self._model_type == "moondream2":
                raw = self._moondream_query(
                    image,
                    "List 15 descriptive tags for this wallpaper image, separated by "
                    "commas. Include subject, mood, style, and use tags. "
                    "Be specific. No hashtags.",
                )
                tags = self._clean_tags(raw)
            else:
                # BLIP needs multiple prompts to get good tags
                caption = self._blip_generate(image, prompt=None)
                subject = self._blip_generate(image, prompt="this image contains")
                tags = self._tags_from_blip_captions(caption, subject, image)

            return tags
        except Exception as e:
            logger.warning("Tag generation failed: %s", e)
            return self._fallback_tags(image)

    def generate_all(
        self, image: Image.Image
    ) -> dict[str, str]:
        """Generate title, alt text, and tags in one call.

        Returns dict with keys: title, alt_text, tags
        """
        return {
            "title": self.generate_title(image),
            "alt_text": self.generate_alt_text(image),
            "tags": self.generate_tags(image),
        }

    # --- Model-specific methods ---

    def _blip_generate(self, image: Image.Image, prompt: Optional[str] = None) -> str:
        """Generate text with BLIP model."""
        import torch

        if image.mode != "RGB":
            image = image.convert("RGB")

        if prompt:
            inputs = self._processor(image, prompt, return_tensors="pt").to(self._device)
        else:
            inputs = self._processor(image, return_tensors="pt").to(self._device)

        with torch.no_grad():
            output = self._model.generate(
                **inputs, max_new_tokens=80, num_beams=3, early_stopping=True
            )

        text = self._processor.decode(output[0], skip_special_tokens=True)
        return text

    def _moondream_query(self, image: Image.Image, question: str) -> str:
        """Query Moondream2 model."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        result = self._model.query(image, question)
        return result.get("answer", "") if isinstance(result, dict) else str(result)

    # --- Post-processing ---

    def _clean_title(self, raw: str) -> str:
        """Clean up a raw title to 3-8 words, Title Case."""
        # Remove common prefixes
        prefixes = [
            "a wallpaper titled ",
            "a wallpaper of ",
            "an image of ",
            "a photo of ",
            "this wallpaper is ",
            "title: ",
            '"',
            "'",
        ]
        text = raw.strip()
        for prefix in prefixes:
            if text.lower().startswith(prefix):
                text = text[len(prefix):]

        # Remove trailing quotes
        text = text.strip("\"'.,")

        # Title case
        text = text.title()

        # Limit to 8 words
        words = text.split()
        if len(words) > 8:
            text = " ".join(words[:8])
        elif len(words) < 3 and len(words) > 0:
            # Pad short titles
            text = text

        return text.strip() or "Untitled Wallpaper"

    def _clean_alt_text(self, raw: str) -> str:
        """Clean alt text to 1-2 proper sentences."""
        text = raw.strip()

        # Remove "this is" prefix
        prefixes = ["this is ", "this image shows ", "the image shows "]
        for prefix in prefixes:
            if text.lower().startswith(prefix):
                text = text[len(prefix):]
                text = text[0].upper() + text[1:] if text else text
                break

        # Ensure it ends with proper punctuation
        if text and text[-1] not in ".!?":
            text += "."

        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]

        # Limit to ~2 sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) > 2:
            text = " ".join(sentences[:2])

        return text or "A wallpaper image."

    def _clean_tags(self, raw: str) -> str:
        """Clean raw tag output to comma-separated lowercase tags."""
        # Split by commas or newlines
        parts = re.split(r"[,\n]+", raw)
        tags = []
        seen = set()

        for part in parts:
            tag = part.strip().lower().lstrip("#").strip(".-\"'")
            # Remove numbering like "1. " or "- "
            tag = re.sub(r"^\d+\.\s*", "", tag)
            tag = re.sub(r"^[-*]\s*", "", tag)
            tag = tag.strip()

            if tag and tag not in seen and len(tag) < 40:
                seen.add(tag)
                tags.append(tag)

        # Ensure 10-20 tags
        tags = tags[:20]

        # Add generic wallpaper tags if we have too few
        if len(tags) < 10:
            generic = [
                "wallpaper",
                "desktop background",
                "hd",
                "high resolution",
                "aesthetic",
            ]
            for g in generic:
                if g not in seen and len(tags) < 10:
                    tags.append(g)
                    seen.add(g)

        return ", ".join(tags)

    def _tags_from_blip_captions(
        self, caption: str, subject_text: str, image: Image.Image
    ) -> str:
        """Build tags from BLIP caption outputs + color analysis."""
        tags = set()

        # Extract meaningful words from captions
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were", "in", "on", "at",
            "to", "for", "of", "with", "and", "or", "but", "this", "that",
            "it", "its", "image", "shows", "there", "into", "from", "by",
        }

        for text in [caption, subject_text]:
            words = re.findall(r"[a-z]+", text.lower())
            for word in words:
                if word not in stop_words and len(word) > 2:
                    tags.add(word)

        # Add color tags
        try:
            img_bytes = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(img_bytes, format="JPEG", quality=50)
            colors = get_dominant_colors(img_bytes.getvalue(), num_colors=3)
            for color in colors:
                name = color_to_name(color)
                if name not in ("neutral",):
                    tags.add(name)
        except Exception:
            pass

        # Add aspect ratio tag
        w, h = image.size
        if is_mobile(w, h):
            tags.update(["mobile wallpaper", "phone background", "portrait"])
        else:
            tags.update(["desktop wallpaper", "desktop background", "landscape"])

        # Always add generic tags
        tags.update(["wallpaper", "hd", "aesthetic"])

        tag_list = sorted(tags)[:20]
        return ", ".join(tag_list)

    def _fallback_title(self, image: Image.Image) -> str:
        """Generate a basic title from color/dimension analysis."""
        w, h = image.size
        try:
            img_bytes = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(img_bytes, format="JPEG", quality=50)
            colors = get_dominant_colors(img_bytes.getvalue(), num_colors=2)
            color_names = [color_to_name(c) for c in colors]
            primary = color_names[0].title() if color_names else "Abstract"
        except Exception:
            primary = "Abstract"

        orientation = "Portrait" if is_mobile(w, h) else "Landscape"
        return f"{primary} {orientation} Wallpaper"

    def _fallback_tags(self, image: Image.Image) -> str:
        """Generate basic tags from color analysis and dimensions."""
        tags = ["wallpaper", "background", "hd"]
        w, h = image.size

        if is_mobile(w, h):
            tags.extend(["mobile wallpaper", "phone background", "portrait"])
        else:
            tags.extend(["desktop wallpaper", "desktop background", "landscape"])

        try:
            img_bytes = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(img_bytes, format="JPEG", quality=50)
            colors = get_dominant_colors(img_bytes.getvalue(), num_colors=3)
            for color in colors:
                name = color_to_name(color)
                if name not in ("neutral",) and name not in tags:
                    tags.append(name)
        except Exception:
            pass

        tags.extend(["aesthetic", "high resolution"])
        return ", ".join(tags[:15])

    @property
    def model_type(self) -> Optional[str]:
        """Return the loaded model type."""
        if self._unavailable:
            return "fallback"
        return self._model_type

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded or self._unavailable
