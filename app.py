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

def get_session_choices():
    sessions = MemoryManager.get_all_sessions()
    return [(s["name"], s["id"]) for s in sessions]

def chat(message, history, model_choice, session_id, system_prompt):
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
        yield {"text": "", "files": []}, memory.get_history(), gr.update()
        return
        
    # Append to memory
    memory.add_message("user", full_prompt)
    
    # We yield the User message right away
    yield {"text": "", "files": []}, memory.get_history(), gr.update()
    
    # Generate response generator
    messages_for_llm = memory.get_history().copy()
    if system_prompt and system_prompt.strip():
        # Inject system prompt at the beginning just for LLM, don't save to memory's history this way
        messages_for_llm.insert(0, {"role": "system", "content": system_prompt.strip()})
        
    response_stream = llm_manager.generate_response(model_choice, messages_for_llm)
    
    # Create empty placeholder in memory for the assistant's reply
    memory.add_message("assistant", "")
    
    for chunk in response_stream:
        # Update the latest assistant message directly
        memory.history[-1]["content"] += chunk
        # Yield partial history for Gradio to stream visually
        yield {"text": "", "files": []}, memory.get_history(), gr.update()
        
    # Finalize by saving the complete history to disk (avoiding IO overhead on each chunk)
    memory.save_history()
    
    # Yield final history and update dropdown to ensure it shows if this was the first message
    yield {"text": "", "files": []}, memory.get_history(), gr.update(choices=get_session_choices(), value=session_id)

def clear_chat(session_id):
    memory = MemoryManager(session_id)
    memory.clear_history()
    return []

def create_new_chat():
    mem = MemoryManager()
    # When creating a new chat, the dropdown doesn't update its choices because the json file lacks until first save.
    # But we can still set the dropdown value to the new session ID.
    return mem.session_id, mem.get_history(), gr.update(value=mem.session_id)

def load_chat(session_id):
    # Session ID comes from dropdown value. If None, it means the dropdown was cleared (e.g. by deletion).
    if not session_id:
        mem = MemoryManager()
        return mem.session_id, mem.get_history()
    mem = MemoryManager(session_id)
    return mem.session_id, mem.get_history()

def rename_chat(session_id, new_name):
    if not new_name.strip():
        return gr.update()
    mem = MemoryManager(session_id)
    mem.rename_session(new_name)
    return gr.update(choices=get_session_choices(), value=session_id)

def delete_chat(session_id):
    MemoryManager.delete_session(session_id)
    choices = get_session_choices()
    if not choices:
        mem = MemoryManager()
        return mem.session_id, mem.get_history(), gr.update(choices=choices, value=None)
    
    new_id = choices[0][1] # Get most recent session
    mem = MemoryManager(new_id)
    return new_id, mem.get_history(), gr.update(choices=choices, value=new_id)

theme = gr.themes.Soft(
    primary_hue="indigo", 
    secondary_hue="blue", 
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"]
)

with gr.Blocks(title="Programmer's Multi-LLM Chatbot") as demo:
    gr.Markdown("# 🤖 Programmer's Multi-LLM Chatbot\nChat with top-tier reasoning and coding models.")
    
    # Attempt to load first session if available, else new one
    existing_choices = get_session_choices()
    initial_session_id = existing_choices[0][1] if existing_choices else MemoryManager().session_id
    initial_mem = MemoryManager(initial_session_id)
    
    session_id_state = gr.State(initial_session_id)
    
    with gr.Row():
        with gr.Column(scale=1):
            
            gr.Markdown("### 🗂️ History")
            history_dropdown = gr.Dropdown(choices=existing_choices, value=initial_session_id if existing_choices else None, label="Saved Chats", interactive=True)
            
            with gr.Row():
                new_chat_btn = gr.Button("➕ New Chat")
                delete_btn = gr.Button("🗑️ Delete")
                
            with gr.Row():
                rename_box = gr.Textbox(placeholder="New name...", show_label=False, scale=3)
                rename_btn = gr.Button("✏️ Rename", scale=2)
            
            gr.Markdown("---")
            gr.Markdown("### ⚙️ Settings")
            model_dropdown = gr.Dropdown(MODELS, value=MODELS[0], label="Select Model", interactive=True)
            system_prompt_input = gr.Textbox(label="System Prompt (Optional)", placeholder="Enter system instructions here...", lines=3)
            clear_btn = gr.Button("🧹 Clear Current Chat", variant="secondary")
            
            gr.Markdown(
                "### 📁 Supported Files\n"
                "- **Text:** `.txt`, `.md`, `.csv`\n"
                "- **Code:** `.py`, `.js`, `.cpp`, etc\n"
                "- **Documents:** `.pdf`\n"
                "- **Images:** `.jpg`, `.png` (Requires vision supported model)\n"
                "- **Audio:** `.mp3` (WIP)"
            )
            
        with gr.Column(scale=4):
            chatbot = gr.Chatbot(label="Conversation", height=600, value=initial_mem.get_history())
            
            chat_input = gr.MultimodalTextbox(
                interactive=True, file_types=[".txt", ".py", ".pdf", ".jpg", ".png", ".mp3", ".md", ".csv"],
                placeholder="Type a message or upload files...",
                show_label=False
            )

    # Event Wiring
    chat_input.submit(
        chat,
        inputs=[chat_input, chatbot, model_dropdown, session_id_state, system_prompt_input],
        outputs=[chat_input, chatbot, history_dropdown]
    )
    
    clear_btn.click(
        clear_chat,
        inputs=[session_id_state],
        outputs=[chatbot]
    )
    
    new_chat_btn.click(
        create_new_chat,
        inputs=[],
        outputs=[session_id_state, chatbot, history_dropdown]
    )
    
    history_dropdown.change(
        load_chat,
        inputs=[history_dropdown],
        outputs=[session_id_state, chatbot]
    )
    
    rename_btn.click(
        rename_chat,
        inputs=[session_id_state, rename_box],
        outputs=[history_dropdown]
    )
    
    delete_btn.click(
        delete_chat,
        inputs=[session_id_state],
        outputs=[session_id_state, chatbot, history_dropdown]
    )

if __name__ == "__main__":
    app_user = os.getenv("APP_USER")
    app_password = os.getenv("APP_PASSWORD")
    
    auth_credentials = None
    if app_user and app_password:
        auth_credentials = (app_user, app_password)
        
    demo.launch(theme=gr.themes.Ocean(), share=True, auth=auth_credentials)
