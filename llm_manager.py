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
            base_url=os.getenv("QWEN_BASE_URL", "https://dashscope-us.aliyuncs.com/compatible-mode/v1")
        ) if os.getenv("QWEN_API_KEY") else None
        
    def generate_response(self, model_choice, messages):
        """Routes the request and returns a generator for streaming."""
        if model_choice == "GPT-5 (OpenAI)":
             return self._call_openai("gpt-5-2025-08-07", messages)
        elif model_choice == "Claude Sonnet 4.6":
             return self._call_anthropic("claude-sonnet-4-6", messages)
        elif model_choice == "Gemini-3":
             return self._call_gemini("gemini-3.1-pro-preview", messages)
        elif model_choice == "grok-4-1-fast-reasoning":
             return self._call_xai("grok-4-1-fast-reasoning", messages)
        elif model_choice == "Qwen3-Coder":
             return self._call_qwen("qwen3.5-plus", messages)
        else:
             def fallback():
                 yield "Model not implemented."
             return fallback()
             
    def _call_openai(self, model, messages):
        if not self.openai_client:
            yield "Error: OPENAI_API_KEY not configured. Please add it to your .env file."
            return
        try:
            response = self.openai_client.chat.completions.create(model=model, messages=messages, stream=True)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
             yield f"OpenAI Error: {str(e)}"
             
    def _call_anthropic(self, model, messages):
        if not self.anthropic_client:
            yield "Error: ANTHROPIC_API_KEY not configured. Please add it to your .env file."
            return
        
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        anthropic_msgs = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ["user", "assistant"]]
        if anthropic_msgs and anthropic_msgs[0]["role"] != "user":
            anthropic_msgs = anthropic_msgs[1:]
            
        try:
            kwargs = {
                "model": model,
                "max_tokens": 4096,
                "messages": anthropic_msgs,
                "stream": True
            }
            if system_msg:
                 kwargs["system"] = system_msg
                 
            response = self.anthropic_client.messages.create(**kwargs)
            for chunk in response:
                if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                    yield chunk.delta.text
        except Exception as e:
            yield f"Anthropic Error: {str(e)}"
            
    def _call_gemini(self, model, messages):
       if not self.gemini_client:
           yield "Error: GEMINI_API_KEY not configured. Please add it to your .env file."
           return
       
       system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
       contents = []
       for m in messages:
           if m["role"] == "system":
               continue
           role = "user" if m["role"] == "user" else "model"
           text = m["content"]
           if role == "user" and system_msg and len(contents) == 0:
               text = f"System Instructions:\n{system_msg}\n\nUser:\n{text}"
           contents.append({"role": role, "parts": [{"text": text}]})
       
       try:
           response = self.gemini_client.models.generate_content_stream(
               model=model,
               contents=contents
           )
           for chunk in response:
               if chunk.text:
                   yield chunk.text
       except Exception as e:
           yield f"Gemini Error: {str(e)}"

    def _call_xai(self, model, messages):
         if not self.xai_client:
             yield "Error: XAI_API_KEY not configured. Please add it to your .env file."
             return
         try:
            response = self.xai_client.chat.completions.create(model=model, messages=messages, stream=True)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
         except Exception as e:
             yield f"xAI Error: {str(e)}"

    def _call_qwen(self, model, messages):
         if not self.qwen_client:
             yield "Error: QWEN_API_KEY not configured. Please add it to your .env file."
             return
         try:
            response = self.qwen_client.chat.completions.create(model=model, messages=messages, stream=True)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
         except Exception as e:
             yield f"Qwen Error: {str(e)}"
