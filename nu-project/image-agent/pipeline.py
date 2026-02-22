#!/usr/bin/env python3
"""
Content Agent Pipeline
Context Agent → Research Agent → Prompt Agent → (Image Agent)

Usage:
    python pipeline.py "client: beats, product: wireless earbuds, campaign: summer fitness"
    python pipeline.py "client: beats, product: earbuds" --quiet
    python pipeline.py "client: beats, product: earbuds" --fast
"""

import os
import json
import sys
import re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Load agent prompts
PROMPTS_DIR = Path(__file__).parent / "agents" / "prompts"

# Global verbosity flag
VERBOSE = True


def log(msg: str, always: bool = False):
    """Print only if verbose mode or always flag."""
    if VERBOSE or always:
        print(msg)


def load_prompt(agent_name: str) -> str:
    """Load an agent's system prompt from markdown file."""
    prompt_file = PROMPTS_DIR / f"{agent_name}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    return prompt_file.read_text()


def call_agent(agent_name: str, user_input: str, model: str = "gpt-4o-mini", fast: bool = False) -> str:
    """Call an agent with the given input and return its response."""
    system_prompt = load_prompt(agent_name)
    
    # Use faster model if requested
    if fast:
        model = "gpt-4o-mini"
    
    log(f"\n🤖 Calling {agent_name}...")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        response_format={"type": "json_object"}  # Force JSON output
    )
    
    result = response.choices[0].message.content
    log(f"✅ {agent_name} complete")
    return result


def extract_json(text: str) -> dict:
    """Extract JSON from agent response."""
    # Clean up common issues
    text = text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log(f"⚠️  JSON parse error: {e}")
        log(f"Raw text (first 300 chars): {text[:300]}...")
        
        # Try to find JSON object in text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return {"raw": text, "error": str(e)}


def run_pipeline(brief: str, selected_direction: int = 0, fast: bool = False) -> dict:
    """
    Run the full content agent pipeline.
    
    Args:
        brief: The initial client brief
        selected_direction: Which creative direction to use (0-indexed)
        fast: Use faster (cheaper) model
    
    Returns:
        dict with all pipeline outputs
    """
    results = {}
    model = "gpt-4o-mini" if fast else "gpt-4o"
    
    # Step 1: Context Agent
    log("\n" + "="*50)
    log("📋 STEP 1: Context Agent")
    log("="*50)
    
    context_response = call_agent("context_agent", f"Get context for: {brief}", model)
    results["context"] = extract_json(context_response)
    
    ctx = results["context"]
    brand_name = ctx.get('brand', {}).get('name', 'N/A')
    product_name = ctx.get('product', {}).get('name', 'N/A')
    log(f"\n📦 Context: {brand_name} / {product_name}")
    
    # Step 2: Research Agent
    log("\n" + "="*50)
    log("🔍 STEP 2: Research Agent")
    log("="*50)
    
    research_input = f"""
Brand: {ctx.get('brand', {}).get('name', 'Unknown')}
Colors: {', '.join(ctx.get('brand', {}).get('colors', []))}
Mood: {ctx.get('brand', {}).get('mood', 'N/A')}
Avoid: {', '.join(ctx.get('brand', {}).get('avoid', []))}
Style: {ctx.get('preferences', {}).get('style', 'N/A')}
Product: {ctx.get('product', {}).get('name', 'Unknown')}
Target Audience: {ctx.get('product', {}).get('target_audience', 'N/A')}
Additional: {ctx.get('additional_notes', '')}
"""
    
    research_response = call_agent("research_agent", research_input, model)
    results["research"] = extract_json(research_response)
    
    directions = results["research"].get("suggested_directions", [])
    log(f"\n🎯 {len(directions)} creative directions found")
    
    if VERBOSE:
        for i, d in enumerate(directions):
            marker = "→" if i == selected_direction else " "
            conf = d.get('confidence', 'N/A')
            log(f"   {marker} [{i}] {d.get('name', 'Unnamed')} ({conf})")
    
    # Step 3: Prompt Agent
    log("\n" + "="*50)
    log("✍️  STEP 3: Prompt Agent")
    log("="*50)
    
    if not directions:
        selected = {"name": "Default", "description": brief}
    else:
        selected = directions[min(selected_direction, len(directions) - 1)]
    
    log(f"\n🎨 Direction: {selected.get('name')}")
    
    prompt_input = f"""
Brand Context:
- Name: {ctx.get('brand', {}).get('name', 'Unknown')}
- Colors: {', '.join(ctx.get('brand', {}).get('colors', []))}
- Mood: {ctx.get('brand', {}).get('mood', 'N/A')}
- Avoid: {', '.join(ctx.get('brand', {}).get('avoid', []))}
- Style: {ctx.get('preferences', {}).get('style', 'N/A')}

Selected Direction: {selected.get('name', 'N/A')}
Description: {selected.get('description', 'N/A')}

Generate 3 prompt variations for this direction.
"""
    
    prompt_response = call_agent("prompt_agent", prompt_input, model)
    results["prompts"] = extract_json(prompt_response)
    
    prompts = results["prompts"].get("prompts", [])
    log(f"\n📝 Generated {len(prompts)} prompts")
    
    return results


def save_results(results: dict, output_dir: str = "output"):
    """Save pipeline results to JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    output_file = output_path / "pipeline_output.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    log(f"\n💾 Saved: {output_file}")
    return output_file


def main():
    global VERBOSE
    
    args = sys.argv[1:]
    
    # Parse flags
    quiet = "--quiet" in args or "-q" in args
    fast = "--fast" in args or "-f" in args
    
    # Remove flags from args
    args = [a for a in args if not a.startswith("-")]
    
    if not args:
        print("Usage: python pipeline.py \"client: brand, product: item, campaign: theme\" [--quiet] [--fast]")
        print("\nFlags:")
        print("  --quiet, -q   Minimal output")
        print("  --fast, -f    Use faster/cheaper model (gpt-4o-mini)")
        print("\nExample:")
        print('  python pipeline.py "client: beats, product: wireless earbuds" --fast --quiet')
        sys.exit(1)
    
    VERBOSE = not quiet
    brief = args[0]
    direction = int(args[1]) if len(args) > 1 else 0
    
    log("\n" + "="*50, always=True)
    log("🚀 CONTENT AGENT PIPELINE", always=True)
    log("="*50, always=True)
    log(f"Brief: {brief}", always=True)
    if fast:
        log("Mode: Fast (gpt-4o-mini)", always=True)
    
    results = run_pipeline(brief, direction, fast)
    save_results(results)
    
    log("\n" + "="*50, always=True)
    log("✨ Pipeline complete!", always=True)
    log("="*50, always=True)
    
    # Always print final prompts
    print("\n📋 GENERATED PROMPTS:\n")
    for p in results.get("prompts", {}).get("prompts", []):
        print(f"--- {p.get('id', 'prompt')} ---")
        print(p.get("main_prompt", ""))
        neg = p.get('negative_prompt', '')
        if neg:
            print(f"\nNegative: {neg}")
        ratio = p.get('aspect_ratio', p.get('technical', {}).get('aspect_ratio', ''))
        if ratio:
            print(f"Aspect: {ratio}")
        print()


if __name__ == "__main__":
    main()
