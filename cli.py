import requests
import shlex
import os
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

# --- Configuration ---
BASE_URL = os.getenv("CLAUSECOMPASS_API_URL", "http://localhost:8000") # Renamed env var for consistency
PERSISTENT_ENDPOINT = "/evaluate"
DYNAMIC_ENDPOINT = "/evaluate-with-docs"

# --- Application State ---
APP_STATE = {
    "token": None,
    "user_email": None,
    "mode": "persistent",
    "persistent_docs_context": [],
    "temp_docs_to_upload": [],
}

# --- Rich Console ---
console = Console()

# --- Command Handler Functions ---

def handle_help(*args):
    """Displays the comprehensive help message for both modes."""
    console.print(Panel("[bold]ClauseCompass Decision Engine CLI[/bold] 🧭", subtitle="A tool for querying the RAG system.", border_style="blue"))
    table = Table(title="Core Commands", show_header=False, box=None)
    table.add_row("[bold cyan]mode [persistent|temporary][/bold cyan]", "Switch between modes. This clears any set document context.")
    table.add_row("[bold cyan]login / register / logout[/bold cyan]", "Standard user session management.")
    table.add_row("[bold cyan]help[/bold cyan]", "Show this help message.")
    table.add_row("[bold cyan]exit / quit[/bold cyan]", "Exit the application.")
    console.print(table)
    
    console.print("\n[bold]Persistent Mode Commands:[/bold] (Query the pre-loaded server knowledge base)")
    table_p = Table(show_header=False, box=None)
    table_p.add_row("[bold cyan]list_docs[/bold cyan]", "List available documents in the persistent KB.")
    table_p.add_row("[bold cyan]set_docs [file1.pdf]...[/bold cyan]", "Set server-side document context for queries.")
    table_p.add_row("[bold cyan]clear_docs[/bold cyan]", "Clear document context for this mode.")
    console.print(table_p)

    console.print("\n[bold]Temporary Mode Commands:[/bold] (Upload your own documents for a one-time query)")
    table_t = Table(show_header=False, box=None)
    table_t.add_row("[bold cyan]add_doc /path/to/file.pdf[/bold cyan]", "Stage a local document for the next query.")
    table_t.add_row("[bold cyan]show_docs[/bold cyan]", "Show currently staged local documents.")
    table_t.add_row("[bold cyan]clear_docs[/bold cyan]", "Clear staged local documents.")
    console.print(table_t)

    console.print("\n[bold]Querying:[/bold]")
    console.print("Simply type your query and press Enter. The right action will be taken based on the current mode.")


def handle_mode_switch(args_str):
    """Switches the application mode and clears contexts."""
    new_mode = args_str.strip().lower()
    if new_mode in ["persistent", "temporary"]:
        APP_STATE["mode"] = new_mode
        console.print(f"[bold green]✔ Mode switched to: {new_mode}[/bold green]")
        APP_STATE["persistent_docs_context"] = []
        APP_STATE["temp_docs_to_upload"] = []
    else:
        console.print("[bold red]❌ Invalid mode. Use 'persistent' or 'temporary'.[/bold red]")

def handle_login(args_str):
    email = console.input("[bold]Email: [/bold]")
    password = console.input("[bold]Password: [/bold]", password=True)
    try:
        response = requests.post(f"{BASE_URL}/login", data={"username": email, "password": password})
        if response.status_code == 200:
            APP_STATE["token"] = response.json()["access_token"]
            APP_STATE["user_email"] = email
            console.print("[bold green]✔ Login successful.[/bold green]")
        else:
            console.print(f"[bold red]❌ Login failed: {response.json().get('detail', 'Invalid credentials')}[/bold red]")
    except requests.exceptions.RequestException: console.print(f"[bold red]Connection Error to API at {BASE_URL}.[/bold red]")

def handle_register(args_str):
    userid = console.input("[bold]Enter new User ID: [/bold]")
    email = console.input("[bold]Enter your Email: [/bold]")
    password = console.input("[bold]Enter Password: [/bold]", password=True)
    response = requests.post(f"{BASE_URL}/register", json={"userid": userid, "emailid": email, "password": password})
    if response.status_code == 200: console.print("[bold green]✔ Registration successful. Please login.[/bold green]")
    else: console.print(f"[bold red]❌ Registration failed: {response.json().get('detail', 'Unknown error')}[/bold red]")

def handle_logout(*args):
    APP_STATE["token"], APP_STATE["user_email"], APP_STATE["persistent_docs_context"], APP_STATE["temp_docs_to_upload"] = None, None, [], []
    console.print("[bold yellow]You have been logged out.[/bold yellow]")

def handle_list_docs(*args):
    if APP_STATE["mode"] != 'persistent': console.print("[bold red]This command is only available in 'persistent' mode.[/bold red]"); return
    if not APP_STATE["token"]: console.print("[bold red]You must be logged in first.[/bold red]"); return
    headers = {"Authorization": f"Bearer {APP_STATE['token']}"}
    response = requests.get(f"{BASE_URL}/documents", headers=headers)
    if response.status_code == 200:
        docs = response.json().get("documents", [])
        if not docs: console.print("[yellow]No documents found in persistent KB.[/yellow]"); return
        table = Table("Available Documents in Persistent KB")
        for doc in sorted(docs): table.add_row(doc)
        console.print(table)
    else: console.print(f"[bold red]Error fetching documents: {response.json().get('detail', 'Unknown error')}[/bold red]")

def handle_set_docs(args_str):
    if APP_STATE["mode"] != 'persistent': console.print("[bold red]This command is only available in 'persistent' mode.[/bold red]"); return
    if not args_str or args_str.strip() == '*': APP_STATE["persistent_docs_context"] = []; console.print("[bold yellow]Persistent document context cleared.[/bold yellow]"); return
    APP_STATE["persistent_docs_context"] = shlex.split(args_str)
    console.print(f"[bold yellow]Persistent document context set to: {APP_STATE['persistent_docs_context']}[/bold yellow]")

def handle_add_doc(args_str):
    if APP_STATE["mode"] != 'temporary': console.print("[bold red]This command is only available in 'temporary' mode.[/bold red]"); return
    if not args_str: console.print("[bold red]Usage: add_doc /path/to/file.pdf ...[/bold red]"); return
    files_to_add = shlex.split(args_str)
    for file_path in files_to_add:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            abs_path = os.path.abspath(file_path)
            if abs_path not in APP_STATE["temp_docs_to_upload"]: APP_STATE["temp_docs_to_upload"].append(abs_path); console.print(f"[green]Staged:[/green] {abs_path}")
            else: console.print(f"[yellow]Skipped (already staged):[/yellow] {abs_path}")
        else: console.print(f"[bold red]Error: File not found:[/bold red] {file_path}")

def handle_show_docs(*args):
    title = ""
    docs_list = []
    if APP_STATE["mode"] == 'persistent':
        title = "Document Context Set for Persistent Query"
        docs_list = APP_STATE["persistent_docs_context"]
    else:
        title = "Local Documents Staged for Temporary Query"
        docs_list = APP_STATE["temp_docs_to_upload"]
    
    if not docs_list: console.print("[yellow]No documents are currently set for this mode.[/yellow]"); return
    table = Table(title)
    for doc in docs_list: table.add_row(doc)
    console.print(table)
    
def handle_clear_docs(*args):
    if APP_STATE["mode"] == 'persistent': APP_STATE["persistent_docs_context"] = []
    else: APP_STATE["temp_docs_to_upload"] = []
    console.print("[bold yellow]Current document context has been cleared.[/bold yellow]")

def handle_query(query_text):
    if not APP_STATE["token"]: console.print("[bold red]You must be logged in to run a query.[/bold red]"); return
    
    if APP_STATE["mode"] == 'persistent':
        handle_persistent_query(query_text)
    else: # mode == 'temporary'
        handle_temporary_query(query_text)

def handle_persistent_query(query):
    headers = {"Authorization": f"Bearer {APP_STATE['token']}"}
    payload = {"query_text": query, "source_files": APP_STATE["persistent_docs_context"]}
    try:
        with console.status("[bold green]Querying persistent KB...[/bold green]"):
            response = requests.post(f"{BASE_URL}{PERSISTENT_ENDPOINT}", headers=headers, json=payload)
        
        if response.status_code == 200: display_structured_response(response.json())
        else: console.print(f"[bold red]Error: {response.status_code} - {response.json().get('detail', 'Unknown error')}[/bold red]")
    except requests.exceptions.RequestException: console.print(f"[bold red]Connection Error.[/bold red]")

def handle_temporary_query(query):
    if not APP_STATE["temp_docs_to_upload"]: console.print("[bold red]No documents staged. Use 'add_doc' first.[/bold red]"); return
    
    headers = {"Authorization": f"Bearer {APP_STATE['token']}"}
    data_payload = {'query': query}; files_payload = []; file_handles = []
    
    try:
        for file_path in APP_STATE["temp_docs_to_upload"]:
            handle = open(file_path, 'rb'); file_handles.append(handle)
            files_payload.append(('files', (os.path.basename(file_path), handle)))
        
        with console.status("[bold green]Uploading documents and processing...[/bold green]"):
            response = requests.post(f"{BASE_URL}{DYNAMIC_ENDPOINT}", headers=headers, data=data_payload, files=files_payload)

        if response.status_code == 200: display_structured_response(response.json())
        else: console.print(f"[bold red]Error: {response.status_code} - {response.json().get('detail', 'Unknown error')}[/bold red]")
    except requests.exceptions.RequestException: console.print(f"[bold red]Connection Error.[/bold red]")
    finally:
        for handle in file_handles: handle.close()

def display_structured_response(data):
    try:
        json_str = json.dumps(data, indent=2)
        syntax = Syntax(json_str, "json", theme="solarized-dark", line_numbers=True)
        console.print(Panel(syntax, title="AI Decision Engine Response", border_style="magenta", title_align="left"))
    except (json.JSONDecodeError, TypeError): console.print(Panel(str(data), title="AI Response (Raw)", border_style="magenta"))

COMMANDS = {
    "help": handle_help, "mode": handle_mode_switch,
    "register": handle_register, "login": handle_login, "logout": handle_logout,
    "list_docs": handle_list_docs, "set_docs": handle_set_docs,
    "add_doc": handle_add_doc, "show_docs": handle_show_docs, "clear_docs": handle_clear_docs,
    "exit": lambda *args: exit(), "quit": lambda *args: exit(),
}

def get_current_prompt():
    user_part = APP_STATE.get("user_email", "logged out")
    mode_part = f" ({APP_STATE['mode']})"
    docs_part = ""
    docs_list = APP_STATE["persistent_docs_context"] if APP_STATE["mode"] == 'persistent' else APP_STATE["temp_docs_to_upload"]
    num_docs = len(docs_list)
    if num_docs > 0:
        context_type = "docs" if APP_STATE["mode"] == 'persistent' else "staged"
        docs_part = f" [{num_docs} {context_type}]"
    
    return f"ClauseCompass{mode_part} ({user_part}){docs_part} > "

def main():
    console.print("[bold]Welcome to the ClauseCompass Decision Engine CLI! 🧭[/bold] Type 'help' for commands.")
    while True:
        try:
            user_input = console.input(get_current_prompt()).strip()
            if not user_input: continue
            parts = user_input.split(' ', 1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            if command in COMMANDS: COMMANDS[command](args)
            else: handle_query(user_input)
        except (KeyboardInterrupt, EOFError, SystemExit):
            console.print("\n[bold]Exiting...[/bold]"); break

if __name__ == "__main__":
    main()