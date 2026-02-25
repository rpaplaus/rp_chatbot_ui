import gradio as gr
import os
from dotenv import load_dotenv
from llm_manager import LLMManager
from memory_manager import MemoryManager
from file_parser import parse_file

load_dotenv()

llm_manager = LLMManager()

MODELS = [
    "GPT-5 (OpenAI)",
    "Claude Sonnet 4.6",
    "Gemini-3",
    "grok-4-1-fast-reasoning",
    "Qwen3-Coder"
]



def chat(message, history, model_choice, session_id):
    memory = MemoryManager(session_id)
    
    user_text = ""
    file_info = ""
    
    if message.get("files"):
        for file in message["files"]:
            parsed = parse_file(file)
            if parsed["type"] == "text":
                file_info += f"\n\n--- Content of {os.path.basename(file)} ---\n{parsed['content']}\n--- End of File ---\n"
            elif parsed["type"] == "image":
                 file_info += f"\n\n[Attached Image: {os.path.basename(file)}]"
                 # Requires Vision model integration to transmit the base64, leaving as text ref for now.
            elif parsed["type"] == "audio":
                 file_info += f"\n\n[Attached Audio: {os.path.basename(file)}]"
            else:
                 file_info += f"\n\n[Attached File: {os.path.basename(file)} - {parsed['content']}]"
                
    if message.get("text"):
        user_text = message["text"]
        
    full_prompt = user_text + file_info
    
    if not full_prompt.strip():
        yield {"text": "", "files": []}, memory.get_history()
        return
        
    # Append to memory
    memory.add_message("user", full_prompt)
    
    # We yield the User message right away
    yield {"text": "", "files": []}, memory.get_history()
    
    # Generate response
    response = llm_manager.generate_response(model_choice, memory.get_history())
    
    # Save response to memory
    memory.add_message("assistant", response)
    
    # Yield final history
    yield {"text": "", "files": []}, memory.get_history()

def clear_chat(session_id):
    memory = MemoryManager(session_id)
    memory.clear_history()
    return []

theme = gr.themes.Soft(
    primary_hue="indigo", 
    secondary_hue="blue", 
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"]
)

with gr.Blocks(title="Programmer's Multi-LLM Chatbot") as demo:
    gr.Markdown("# 🤖 Programmer's Multi-LLM Chatbot\nChat with top-tier reasoning and coding models.")
    
    session_id_state = gr.State(lambda: MemoryManager().session_id)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Settings")
            model_dropdown = gr.Dropdown(MODELS, value=MODELS[0], label="Select Model", interactive=True)
            clear_btn = gr.Button("🗑️ Clear Chat", variant="secondary")
            
            gr.Markdown(
                "### 📁 Supported Files\n"
                "- **Text:** `.txt`, `.md`, `.csv`\n"
                "- **Code:** `.py`, `.js`, `.cpp`, etc\n"
                "- **Documents:** `.pdf`\n"
                "- **Images:** `.jpg`, `.png` (Requires vision supported model)\n"
                "- **Audio:** `.mp3` (WIP)"
            )
            
        with gr.Column(scale=4):
            chatbot = gr.Chatbot(label="Conversation", height=600)
            
            chat_input = gr.MultimodalTextbox(
                interactive=True, file_types=[".txt", ".py", ".pdf", ".jpg", ".png", ".mp3", ".md", ".csv"],
                placeholder="Type a message or upload files...",
                show_label=False
            )

    chat_input.submit(
        chat,
        inputs=[chat_input, chatbot, model_dropdown, session_id_state],
        outputs=[chat_input, chatbot]
    )
    
    clear_btn.click(
        clear_chat,
        inputs=[session_id_state],
        outputs=[chatbot]
    )

if __name__ == "__main__":
    demo.launch(theme=theme)
