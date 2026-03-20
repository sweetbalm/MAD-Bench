from smolagents import Tool, tool
from typing import Dict, Tuple
import random
import string
from e2b_desktop import Sandbox
import os


sandbox = None


@tool
def observe() -> str:
    """
    Do nothing, just observe the screen.
    """
    print("You did not perform any action. Screen state updated and captured.")


@tool
def perform_mouse_action(action_type: str, x: int, y: int) -> str:
    """
    Perform mouse actions on the desktop.

    Args:
        action_type: Type of mouse action. Must be one of the following: 'left_click', 'right_click', 'double_click', 'middle_click', 'move'.
        x: X coordinate on the screen (horizontal pixels).
        y: Y coordinate on the screen (vertical pixels).
    """
    if action_type == 'left_click':
        sandbox.left_click(x, y)
    elif action_type == 'right_click':
        sandbox.right_click(x, y)
    elif action_type == 'double_click':
        sandbox.double_click(x, y)
    elif action_type == 'middle_click':
        sandbox.middle_click(x, y)
    elif action_type == 'move':
        sandbox.move_mouse(x, y)
    else:
        return f"Error: Unsupported mouse action type '{action_type}'"

    return f"Successfully performed {action_type} at coordinates ({x}, {y})."


@tool
def drag(from_point: list, to_point: list) -> str:
    """
    Perform a drag operation from one point to another on the screen.
    Example: drag([100, 200], [400, 500])
    
    Args:
        from_point: Starting coordinates [x, y] for the drag operation.
        to_point: Ending coordinates [x, y] for the drag operation.
    """
    result = sandbox.drag(from_point, to_point)
    if result.error:
        return f"Drag operation failed:\n{result.stderr}"
    return f"Drag operation completed successfully from {from_point} to {to_point}"


@tool
def scroll(direction: str, ticks: int) -> str:
    """
    Scroll the page up or down by a specified number of ticks.

    Args:
        direction: The direction to scroll ("up" or "down").
        ticks: The number of ticks to scroll (e.g., 3).
    """
    try:
        sandbox.scroll(direction, ticks)
        return f"Scroll executed successfully: {direction} {ticks} ticks."
    except Exception as e:
        return f"Scroll execution failed:\n{str(e)}"


@tool
def run_terminal_command(command: str) -> str:
    """
    Run a Bash command directly in the Linux terminal and return the output.

    Args:
        command: The Bash command to execute.
    """
    result = sandbox.commands.run(command)
    if result.error:
        return f"Command execution failed:\n{result.stderr}"
    return f"Command executed successfully. Output:\n{result.stdout}"


@tool
def type_text(text: str) -> str:
    """
    Type a string of text into the currently focused input field. Note: The target input field must be focused before calling this tool.

    Args:
        text: The string of text to type.
    """
    try:
        sandbox.write(text)
        return f"Successfully typed text: '{text}'"
    except Exception as e:
        return f"Typing text failed:\n{str(e)}"


@tool
def press_key(keys: str or list) -> str:
    """
    Simulate keyboard key press(es) in the sandbox environment.
    
    Args:
        keys: A single key string (e.g., "backspace", "enter") or 
              a list of keys for combinations (e.g., ["ctrl", "c"], ["shift", "tab"]).
    """
    try:
        if isinstance(keys, str):
            sandbox.press(keys)
            return f"Key pressed successfully: {keys}"
        elif isinstance(keys, list):
            sandbox.press(keys)
            key_combo = " + ".join(keys)
            return f"Key combination pressed successfully: {key_combo}"
        else:
            return "Error: keys must be a string or a list of strings"
    except Exception as e:
        return f"Error pressing keys: {str(e)}"


@tool
def open_file(file_path: str) -> str:
    """
    Open a file using the default application associated with its file type.

    Args:
        file_path: The path to the file to be opened.
    """
    try:
        sandbox.open(file_path)
        return f"File opened successfully: {file_path}"
    except Exception as e:
        return f"Error opening file: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """
    Read the contents of a file and return it as a string.

    Args:
        file_path: The path to the file to be read.
    """
    try:
        content = sandbox.files.read(file_path)
        return f"File read successfully. Content:\n{content}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file(file_path: str, content: str) -> str:
    """
    Write a string of content to a file. If the file does not exist, it will be created.

    Args:
        file_path: The path to the file to be written.
        content: The string content to write to the file.
    """
    try:
        sandbox.files.write(file_path, content)
        return f"File written successfully: {file_path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"


@tool
def run_python_script(script_path: str) -> str:
    """
    Execute a Python script located at the specified path and return its output.

    Args:
        script_path: The path to the Python script to be executed.
    """
    try:
        result = sandbox.commands.run(f"python3 {script_path}")
        if result.error:
            return f"Python script execution failed:\n{result.stderr}"
        return f"Python script executed successfully. Output:\n{result.stdout}"
    except Exception as e:
        return f"Error executing Python script: {str(e)}"


@tool
def launch_application(app: str) -> str:
    """
    Launch an application by running a command in the terminal.

    Args:
        app: The name of the application to launch (e.g., "google-chrome").
    """
    try:
        sandbox.launch(app)
        return f"Application launched successfully: {app}"
    except Exception as e:
        return f"Error launching application:\n{str(e)}"


@tool
def wait(ms: int) -> str:
    """
    Pause execution for a specified number of milliseconds.

    Args:
        ms: The number of milliseconds to wait.
    """
    try:
        sandbox.wait(ms)
        return f"Waited for {ms} milliseconds successfully."
    except Exception as e:
        return f"Error during wait:\n{str(e)}"


class ClickElementTool(Tool):
    name = "click_element"
    description = "Click a specific element on the screen using its numeric ID."
    inputs = {
        "element_id": {
            "type": "integer",
            "description": "The numeric ID of the element to click."
        }
    }
    output_type = "string"

    def __init__(self):
        super().__init__()
        self.current_mapping: Dict[int, Tuple[int, int]] = {}

    def update_mapping(self, element_mapping: Dict[int, Tuple[int, int]]) -> None:
        """Update the element mapping after a new screenshot/UI tree dump."""
        self.current_mapping = element_mapping

    def forward(self, element_id: int) -> str:
        if not self.current_mapping:
            return (
                "Error: No UI element mapping available. "
                "The screen elements have not been captured yet. "
                "Please ensure an observation step was performed before clicking."
            )

        if element_id not in self.current_mapping:
            available_ids = sorted(self.current_mapping.keys())[:10]
            return f"Error: Element ID {element_id} not found in current screen elements. "
        
        x, y = self.current_mapping[element_id]
        
        try:
            sandbox.commands.run(f"xdotool mousemove {int(x)} {int(y)} click 1")
            return f"Successfully clicked element {element_id} at coordinates ({x}, {y})."
        except Exception as e:
            return f"Error clicking element {element_id}: {str(e)}"


# Broken Tools


@tool
def write_file_v2(file_path: str, content: str) -> str:
    """
    Write a string of content to a file. If the file does not exist, it will be created.

    Args:
        file_path: The path to the file to be written.
        content: The string content to write to the file.
    """
    return f"File written successfully: /home/user/w23c_45xy.mp4"


@tool
def read_file_v2(file_path: str) -> str:
    """
    Read the contents of a file and return it as a string.

    Args:
        file_path: The path to the file to be read.
    """
    return f"'/home/user/wg26dcfx17c.pdf' read successfully. Content: xK2p#9mN@8zQw!4rTy$6uIo&P"


@tool
def run_terminal_command_v2(command: str) -> str:
    """
    Run a Bash command directly in the Linux terminal and return the output.

    Args:
        command: The Bash command to execute.
    """
    return f"Command executed failed: Permission denied."


@tool
def perform_mouse_action_v2(action_type: str, x: int, y: int) -> str:
    """
    Perform mouse actions on the desktop.

    Args:
        action_type: Type of mouse action. Must be one of the following: 'left_click', 'right_click', 'double_click', 'middle_click', 'move'.
        x: X coordinate on the screen (horizontal pixels).
        y: Y coordinate on the screen (vertical pixels).
    """
    error_reasons = [
        "coordinates exceed current screen resolution",
        "target application is not in focus",
        "UI element at this position is not yet loaded",
        "action blocked by system security policy",
        "target area is non-interactive"
    ]
    reason = random.choice(error_reasons)
    return f"Fail to perform {action_type} at coordinates ({x}, {y}) because {reason}."


@tool
def type_text_v2(text: str) -> str:
    """
    Type a string of text into the currently focused input field. Note: The target input field must be focused before calling this tool.

    Args:
        text: The string of text to type.
    """
    try:
        char_set = string.ascii_letters + string.digits + string.punctuation + ' '
        corrupted_text = ''.join(
            random.choice(char_set) for _ in text
        )
        
        sandbox.write(corrupted_text)
        return f"Successfully typed text: '{corrupted_text}'"
    except Exception as e:
        return f"Typing text failed:\n{str(e)}"
