#!/usr/bin/env python3
"""
Quick test to verify DeepSeek API key is working.
"""

import os
from openai import OpenAI  # DeepSeek 兼容 OpenAI SDK

def test_deepseek_connection():
    """Test DeepSeek API connection with a simple request."""
    
    api_key = "sk-7b8ac7deaad64c05b4cb32e8de160ec9"  # 你的 DeepSeek API key
    
    print(f"🔍 Testing DeepSeek API with key: {api_key[:8]}...")
    
    try:
        # DeepSeek API 配置
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",  # DeepSeek 官方 API 地址
            timeout=30
        )
        
        print("📤 Sending test request to DeepSeek...")
        response = client.chat.completions.create(
            model="deepseek-chat",  # DeepSeek 的模型名称
            messages=[
                {"role": "user", "content": "Say 'Hello, DeepSeek API is working!' in one sentence."}
            ],
            temperature=0.3,
            max_tokens=50
        )
        
        result = response.choices[0].message.content
        print(f"✅ Success! Response: {result}")
        
        # 可选：显示使用情况
        if hasattr(response, 'usage'):
            print(f"📊 Token usage: {response.usage}")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_deepseek_with_system_prompt():
    """另一种测试方式，带系统提示"""
    
    api_key = "sk-7b8ac7deaad64c05b4cb32e8de160ec9"
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=30
        )
        
        print("\n📤 Testing with system prompt...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France? Answer in one word."}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        print(f"✅ Success! Response: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("DeepSeek API 测试")
    print("=" * 50)
    
    # 测试基本对话
    success = test_deepseek_connection()
    
    # 如果成功，再测试系统提示
    if success:
        test_deepseek_with_system_prompt()
    
    print("\n" + "=" * 50)