"""
API Keys 配置文件
请在下方填入你的 API Keys
"""

# Google API Key (用于 Gemini 3)
GOOGLE_API_KEY = "AIzaSyB-xLHjQJvv-Z8sHtONEw7BE9f3uqXRV4Q"

# Anthropic API Key (用于 Claude Opus 4.5)
ANTHROPIC_API_KEY = "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"

# OpenAI API Key (用于 GPT-5.2)
OPENAI_API_KEY = "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"


# 自动设置环境变量（运行时生效）
def setup_env():
    import os
    if GOOGLE_API_KEY:
        os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
    if ANTHROPIC_API_KEY:
        os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
    if OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    print("API Keys 已配置!")


if __name__ == "__main__":
    setup_env()
    print(f"GOOGLE_API_KEY: {'已设置' if GOOGLE_API_KEY else '未设置'}")
    print(f"ANTHROPIC_API_KEY: {'已设置' if ANTHROPIC_API_KEY else '未设置'}")
    print(f"OPENAI_API_KEY: {'已设置' if OPENAI_API_KEY else '未设置'}")
