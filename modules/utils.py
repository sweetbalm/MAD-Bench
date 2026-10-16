import os
import io
import time
from time import sleep
from io import BytesIO
import ast
from typing import Dict, Tuple, Optional
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from e2b_desktop import Sandbox
from smolagents import CodeAgent, LiteLLMModel, tool
from smolagents.agents import ActionStep
from .tools import ClickElementTool


sandbox = None
trajectory_dir: Optional[str] = None
trajectory_screenshot_dir: Optional[str] = None


def set_trajectory_dir(task_dir: str):
    """
    Set the current task trajectory directory.
    Screenshots will be saved under: {task_dir}/screenshots
    """
    global trajectory_dir, trajectory_screenshot_dir
    trajectory_dir = task_dir
    trajectory_screenshot_dir = os.path.join(task_dir, "screenshots")
    os.makedirs(trajectory_screenshot_dir, exist_ok=True)


def init_sandbox(timeout: int, with_extra_setup: bool = False):
    sandbox_instance = Sandbox.create(timeout=timeout)

    if with_extra_setup:
        sandbox_instance.commands.run("sudo pip install psutil")
        sandbox_instance.commands.run("sudo apt-get update && sudo apt-get install -y python3-pyatspi")
        sandbox_instance.commands.run("sudo pip install playwright && playwright install chromium")
        with open("assets/at_dump_script.py", "rb") as file:
            sandbox_instance.files.write("/home/user/dump_at.py", file)

    return sandbox_instance


def _extract_visible_elements(xml_str: str) -> list[dict]:
    """
    Parse XML and extract visible interactive elements.

    Returns:
        list: A list of dictionaries containing element information.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return []
    
    elements = []
    for node in root.iter():
        visible = node.get("visible", "false") == "true"
        showing = node.get("showing", "true") == "true"
        name = node.get("name", "").strip()
        tag = node.tag
        
        is_interactive = (
            tag.endswith("button") or 
            tag in ["input", "link", "menu", "menu-item", "entry", "check-box", "combo-box", "text"] or 
            name != ""
        )

        if visible and showing and is_interactive:
            coord_str = node.get("screencoord", "(-1, -1)")
            size_str = node.get("size", "(-1, -1)")
            
            try:
                x, y = ast.literal_eval(coord_str)
                w, h = ast.literal_eval(size_str)
                
                if w <= 0 or h <= 0 or x < 0 or y < 0:
                    continue
                
                center_x = x + w // 2
                center_y = y + h // 2
                
                elements.append({
                    "id": len(elements) + 1,
                    "tag": tag,
                    "name": name,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "center_x": center_x,
                    "center_y": center_y,
                })
            except (ValueError, SyntaxError):
                continue
    
    return elements


def get_linearized_text(xml_str: str) -> tuple[str, dict[int, tuple[int, int]]]:
    """
    Parse XML, filter invisible nodes, and generate linearized text description.
    
    Args:
        xml_str: XML string of the UI tree
        
    Returns:
        tuple: 
            - linearized_text: Tab-separated text containing ID/Tag/Name/coordinates
            - element_mapping: {element_id: (center_x, center_y)} for subsequent click positioning
    """
    elements = _extract_visible_elements(xml_str)
    
    text_lines = ["ID\tTag\tName\tCenter_X\tCenter_Y"]
    element_mapping: dict[int, tuple[int, int]] = {}
    
    for elem in elements:
        text_lines.append(
            f"{elem['id']}\t{elem['tag']}\t{elem['name']}\t{elem['center_x']}\t{elem['center_y']}"
        )
        element_mapping[elem['id']] = (elem['center_x'], elem['center_y'])
    
    linearized_text = "\n".join(text_lines)
    return linearized_text, element_mapping


def annotate_screenshot(
    screenshot_bytes: bytes, 
    xml_str: str,
    font_path: str = "arial.ttf",
    font_size: int = 20
) -> Image.Image:
    """
    Parse XML, filter invisible nodes, and draw bounding boxes with numeric IDs on the screenshot.
    
    Args:
        screenshot_bytes: Byte data of the original screenshot
        xml_str: XML string of the UI tree
        font_path: Font file path (optional, default arial.ttf)
        font_size: Font size (optional, default 15)
        
    Returns:
        Image.Image: Annotated PIL Image object (RGB mode)
    """
    elements = _extract_visible_elements(xml_str)
    
    image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()
    
    # Draw annotations for each element
    for elem in elements:
        x, y, w, h = elem['x'], elem['y'], elem['w'], elem['h']
        element_id = elem['id']
        
        # Draw red bounding box
        draw.rectangle([(x, y), (x + w, y + h)], outline="red", width=2)
        
        # Draw ID label with black background
        text_pos = (x, y)
        text_bbox = draw.textbbox(text_pos, str(element_id), font=font)
        draw.rectangle(text_bbox, fill="black")
        draw.text(text_pos, str(element_id), font=font, fill="white")
    
    return image


def _cleanup_old_steps(agent: CodeAgent, current_step: int, clear_text: bool = False):
    """
    Clear old observations to reduce memory usage.
    """
    for previous_memory_step in agent.memory.steps:
        if isinstance(previous_memory_step, ActionStep) and previous_memory_step.step_number <= current_step - 2:
            if clear_text:
                previous_memory_step.observations = None
            previous_memory_step.observations_images = None


def _save_step_image(image: Image.Image, current_step: int) -> Optional[str]:
    """
    Save step image to trajectory directory.
    """
    global trajectory_screenshot_dir

    if trajectory_screenshot_dir is None:
        return None

    filename = f"Step{current_step}.png"

    screenshot_path = os.path.join(trajectory_screenshot_dir, filename)
    image.save(screenshot_path)


def input_screenshot(memory_step: ActionStep, agent: CodeAgent):
    """Input the screenshot to the memory step."""
    global sandbox

    if sandbox is None:
        raise RuntimeError("Sandbox is not initialized.")

    sleep(1.0)
    current_step = memory_step.step_number

    _cleanup_old_steps(agent, current_step, clear_text=False)

    screenshot = sandbox.screenshot()
    image = Image.open(BytesIO(screenshot)).convert("RGB")
    memory_step.observations_images = [image.copy()]

    _save_step_image(image, current_step)


def input_sc_and_txt(memory_step: ActionStep, agent: CodeAgent):
    """Input the screenshot and the linear text of the UI tree to the memory step."""
    global sandbox

    if sandbox is None:
        raise RuntimeError("Sandbox is not initialized.")

    sleep(1.0)
    current_step = memory_step.step_number

    _cleanup_old_steps(agent, current_step, clear_text=True)

    screenshot = sandbox.screenshot()
    result = sandbox.commands.run("python3 /home/user/dump_at.py")
    if result.error:
        raise Exception(f"Failed to dump UI tree: {result.error}")
    else:
        raw_xml = result.stdout

    image = Image.open(BytesIO(screenshot)).convert("RGB")

    linearized_text, _ = get_linearized_text(raw_xml)
    # print(f"Linearized text for step {current_step}:\n{linearized_text}")
    memory_step.observations = linearized_text
    memory_step.observations_images = [image.copy()]

    _save_step_image(image, current_step)


class InputSoMCallback:
    """Input the annotated screenshot to the memory step."""
    def __init__(self, click_tool: ClickElementTool):
        self.click_tool = click_tool

    def __call__(self, memory_step: ActionStep, agent: CodeAgent) -> None:
        sleep(1.0)
        current_step = memory_step.step_number
        
        for previous_memory_step in agent.memory.steps:
            if isinstance(previous_memory_step, ActionStep) and previous_memory_step.step_number <= current_step - 2:
                previous_memory_step.observations_images = None

        result = sandbox.commands.run("python3 /home/user/dump_at.py")
        if result.error:
            raise Exception(f"Failed to dump UI tree: {result.error}")
        else:
            raw_xml = result.stdout
        
        _, element_mapping = get_linearized_text(raw_xml)
        self.click_tool.update_mapping(element_mapping)

        screenshot = sandbox.screenshot()
        anno_image = annotate_screenshot(screenshot, raw_xml)
        # anno_image.save(f"annotated_screenshot_step_{current_step}.png")
        print(f"Captured an annotated screenshot: {anno_image.size} pixels")
        memory_step.observations_images = [anno_image.copy()]
