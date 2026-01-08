#!/usr/bin/env python3
"""
Test script for Hybrid Legal Assistant (Saul-7B + Claude + Multi-Document RAG)
"""

import requests
import json

def test_chat():
    """Test chat endpoint with legal question"""

    url = "http://localhost:8000/api/chat/message"

    # Test 1: Legal question (should trigger Saul-7B + Claude hybrid)
    print("=" * 80)
    print("TEST 1: Legal Question - AI Act")
    print("=" * 80)

    payload = {
        "message": "What are the main requirements of the AI Act (Regulation 2024/1689)?",
        "use_context": True,
        "stream": False
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Chat ID: {data.get('chat_id')}")
        print(f"✅ Model: {data.get('model')}")
        print(f"✅ Tokens used: {data.get('tokens_used')}")
        print(f"✅ Search time: {data.get('search_time_ms'):.2f}ms")
        print(f"✅ Total time: {data.get('total_time_ms'):.2f}ms")
        print(f"\n📝 Response (first 500 chars):")
        print(data.get('message', '')[:500])
        print(f"\n📚 Citations: {len(data.get('citations', []))} found")

        # Check if hybrid model was used
        if data.get('model') == 'hybrid-saul-claude':
            print("\n✅ SUCCESS: Hybrid Legal Assistant (Saul-7B + Claude) was used!")
        else:
            print(f"\n⚠️  WARNING: Expected 'hybrid-saul-claude', got '{data.get('model')}'")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

    print("\n" + "=" * 80)
    print("TEST 2: Non-legal question (should use Claude only)")
    print("=" * 80)

    payload2 = {
        "message": "Hello! How are you?",
        "use_context": False,
        "stream": False
    }

    response2 = requests.post(url, json=payload2)

    if response2.status_code == 200:
        data2 = response2.json()
        print(f"\n✅ Model: {data2.get('model')}")
        print(f"✅ Response (first 200 chars):")
        print(data2.get('message', '')[:200])

        if 'hybrid' not in data2.get('model', ''):
            print("\n✅ SUCCESS: Standard Claude was used for non-legal query")
        else:
            print(f"\n⚠️  Note: Hybrid model was used: '{data2.get('model')}'")
    else:
        print(f"❌ Error: {response2.status_code}")
        print(response2.text)

if __name__ == "__main__":
    test_chat()
