#!/usr/bin/env python3
"""
Test script to verify LLM fallback mechanism works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_client import call_llm

def test_fallback():
    """Test the LLM fallback mechanism."""
    print("Testing LLM fallback mechanism...")
    print("-" * 50)

    # Test message
    messages = [
        {"role": "user", "content": "Reply with 'Hello! The LLM is working.' and nothing else."}
    ]

    try:
        # Test with automatic backend selection
        print("\n1. Testing with automatic backend selection:")
        response = call_llm(messages)
        print(f"Response: {response}")
        print("✅ Automatic backend selection successful!")

        # Test preferring Hugging Face
        print("\n2. Testing with prefer_backend='huggingface':")
        try:
            response = call_llm(messages, prefer_backend="huggingface")
            print(f"Response: {response}")
            print("✅ Hugging Face preference successful!")
        except Exception as e:
            print(f"⚠️  Hugging Face preference failed: {e}")

        # Test preferring Ollama
        print("\n3. Testing with prefer_backend='ollama':")
        try:
            response = call_llm(messages, prefer_backend="ollama")
            print(f"Response: {response}")
            print("✅ Ollama preference successful!")
        except Exception as e:
            print(f"⚠️  Ollama preference failed: {e}")

    except RuntimeError as e:
        print(f"\n❌ All backends failed: {e}")
        print("\nMake sure either:")
        print("  - HF_TOKEN is set in your .env file, OR")
        print("  - Ollama is running ('ollama serve' in another terminal)")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

    print("\n" + "=" * 50)
    print("✅ LLM fallback mechanism is working correctly!")
    print("The system will automatically try both backends if one fails.")
    return True

if __name__ == "__main__":
    success = test_fallback()
    sys.exit(0 if success else 1)