"""Pre-download AI model during Docker build."""
import os
from transformers import BlipProcessor, BlipForConditionalGeneration

print("Downloading BLIP model weights...")
BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
print("BLIP model downloaded successfully.")

# Optionally also pre-download Moondream2
if os.environ.get("PRELOAD_MOONDREAM", "").lower() == "true":
    from transformers import AutoModelForCausalLM
    print("Downloading Moondream2 model weights...")
    AutoModelForCausalLM.from_pretrained(
        "vikhyatk/moondream2", revision="2025-01-09", trust_remote_code=True
    )
    print("Moondream2 model downloaded successfully.")
