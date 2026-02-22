#!/usr/bin/env python3
"""
Image Agent - Takes prompts and generates images via Replicate API

Usage:
    from image_agent import ImageAgent
    
    agent = ImageAgent()
    results = agent.generate(prompts, negative_prompts, models, aspect_ratios)
"""

import os
import replicate
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# Model mappings for Replicate
MODELS = {
    "flux-pro": "black-forest-labs/flux-1.1-pro",
    "sd-xl": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
    "midjourney": "prompthero/openjourney:ad59ca21177f9e217b9075e7300cf6e14f7e5b4505b87b9689dbd866e9768969",
}

# Aspect ratio to dimensions
ASPECT_RATIOS = {
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "16:9": (1344, 768),
    "21:9": (1536, 640),
    "9:16": (768, 1344),
}


class ImageAgent:
    def __init__(self, output_dir: str = "output/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Verify API token
        if not os.getenv("REPLICATE_API_TOKEN"):
            raise ValueError("REPLICATE_API_TOKEN not found in environment")
    
    def generate_single(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = "flux-pro",
        aspect_ratio: str = "1:1",
        index: int = 0
    ) -> dict:
        """Generate a single image."""
        
        model_id = MODELS.get(model, MODELS["flux-pro"])
        width, height = ASPECT_RATIOS.get(aspect_ratio, (1024, 1024))
        
        print(f"\n🎨 Generating image {index + 1}...")
        print(f"   Model: {model} ({model_id.split('/')[0]})")
        print(f"   Size: {width}x{height}")
        print(f"   Prompt: {prompt[:60]}...")
        
        try:
            # Different models have different input schemas
            if "flux" in model_id:
                output = replicate.run(
                    model_id,
                    input={
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "output_format": "png",
                        "safety_tolerance": 2,
                    }
                )
            elif "sdxl" in model_id:
                output = replicate.run(
                    model_id,
                    input={
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "width": width,
                        "height": height,
                        "num_outputs": 1,
                    }
                )
            else:
                # OpenJourney / other models
                output = replicate.run(
                    model_id,
                    input={
                        "prompt": f"mdjrny-v4 style {prompt}",
                        "width": width,
                        "height": height,
                        "num_outputs": 1,
                    }
                )
            
            # Handle different output formats
            if isinstance(output, list):
                image_url = output[0]
            elif hasattr(output, 'url'):
                image_url = output.url
            else:
                image_url = str(output)
            
            # Download and save
            filename = f"image_{index + 1}_{model}_{datetime.now().strftime('%H%M%S')}.png"
            filepath = self.output_dir / filename
            
            response = requests.get(image_url)
            response.raise_for_status()
            
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            print(f"   ✅ Saved: {filepath}")
            
            return {
                "success": True,
                "filepath": str(filepath),
                "url": image_url,
                "model": model,
                "prompt": prompt
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "model": model,
                "prompt": prompt
            }
    
    def generate(
        self,
        prompts: List[str],
        negative_prompts: List[str],
        models: List[str],
        aspect_ratios: List[str]
    ) -> List[dict]:
        """Generate multiple images from prompt agent output."""
        
        print(f"\n{'='*50}")
        print(f"🖼️  IMAGE AGENT - Generating {len(prompts)} images")
        print(f"{'='*50}")
        
        results = []
        
        for i, (prompt, neg, model, ratio) in enumerate(
            zip(prompts, negative_prompts, models, aspect_ratios)
        ):
            result = self.generate_single(
                prompt=prompt,
                negative_prompt=neg,
                model=model,
                aspect_ratio=ratio,
                index=i
            )
            results.append(result)
        
        # Summary
        success = sum(1 for r in results if r["success"])
        print(f"\n{'='*50}")
        print(f"✨ Complete: {success}/{len(prompts)} images generated")
        print(f"📁 Output: {self.output_dir}")
        print(f"{'='*50}")
        
        return results


def main():
    """Test with sample prompts."""
    agent = ImageAgent()
    
    # Sample from your pipeline output
    prompts = [
        "A serene home office with a minimalist wooden desk, displaying a pair of sleek headphones. The room is bathed in soft natural light, with beige tones creating a calm atmosphere.",
    ]
    negative_prompts = ["clutter, harsh light, bright captions, excessive accessories"]
    models = ["flux-pro"]
    aspect_ratios = ["16:9"]
    
    results = agent.generate(prompts, negative_prompts, models, aspect_ratios)
    print(results)


if __name__ == "__main__":
    main()
