import os
from openai import OpenAI
import anthropic
from google import genai

class LLMManager:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
        self.anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) if os.getenv("ANTHROPIC_API_KEY") else None
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) if os.getenv("GEMINI_API_KEY") else None
        self.xai_client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1") if os.getenv("XAI_API_KEY") else None
        self.qwen_client = OpenAI(
            api_key=os.getenv("QWEN_API_KEY"), 
            base_url=os.getenv("QWEN_BASE_URL", "https://api.deepseek.com/v1") # Typical OpenAI compatible url for Qwen models
        ) if os.getenv("QWEN_API_KEY") else None
        
    def generate_response(self, model_choice, messages):
        """Routes the request to the correct LLM provider."""
        if model_choice == "GPT-5 (OpenAI)":
             return self._call_openai("gpt-5-2025-08-07", messages) # Placeholder map
        elif model_choice == "Claude Sonnet 4.6":
             return self._call_anthropic("claude-opus-4-6", messages) # Placeholder map
        elif model_choice == "Gemini-3":
             return self._call_gemini("gemini-3.1-pro-preview", messages) # Placeholder map
        elif model_choice == "grok-4-1-fast-reasoning":
             return self._call_xai("grok-4-1-fast-reasoning", messages) # Placeholder map
        elif model_choice == "Qwen3-Coder":
             return self._call_qwen("qwen2.5-coder-32b-instruct", messages) # Placeholder map
        else:
             return "Model not implemented."
             
    def _call_openai(self, model, messages):
        if not self.openai_client:
            return "Error: OPENAI_API_KEY not configured. Please add it to your .env file."
        try:
            response = self.openai_client.chat.completions.create(model=model, messages=messages)
            return response.choices[0].message.content
        except Exception as e:
             return f"OpenAI Error: {str(e)}"
             
    def _call_anthropic(self, model, messages):
        if not self.anthropic_client:
            return "Error: ANTHROPIC_API_KEY not configured. Please add it to your .env file."
        
        # Anthropic requires precise alternating roles, system prompts separate, etc. This is a basic mapping.
        anthropic_msgs = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ["user", "assistant"]]
        
        # Ensure it starts with user
        if anthropic_msgs and anthropic_msgs[0]["role"] != "user":
            anthropic_msgs = anthropic_msgs[1:]
            
        try:
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=4096,
                messages=anthropic_msgs
            )
            return response.content[0].text
        except Exception as e:
            return f"Anthropic Error: {str(e)}"
            
    def _call_gemini(self, model, messages):
       if not self.gemini_client:
           return "Error: GEMINI_API_KEY not configured. Please add it to your .env file."
       
       contents = []
       for m in messages:
           role = "user" if m["role"] == "user" else "model"
           contents.append({"role": role, "parts": [{"text": m["content"]}]})
       
       try:
           response = self.gemini_client.models.generate_content(
               model=model,
               contents=contents
           )
           return response.text
       except Exception as e:
           return f"Gemini Error: {str(e)}"

    def _call_xai(self, model, messages):
         if not self.xai_client:
             return "Error: XAI_API_KEY not configured. Please add it to your .env file."
         try:
            response = self.xai_client.chat.completions.create(model=model, messages=messages)
            return response.choices[0].message.content
         except Exception as e:
             return f"xAI Error: {str(e)}"

    def _call_qwen(self, model, messages):
         if not self.qwen_client:
             return "Error: QWEN_API_KEY not configured. Please add it to your .env file."
         try:
            response = self.qwen_client.chat.completions.create(model=model, messages=messages)
            return response.choices[0].message.content
         except Exception as e:
             return f"Qwen Error: {str(e)}"
