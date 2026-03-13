import os
import io
import time
from time import sleep
from io import BytesIO
import ast
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from e2b_desktop import Sandbox
from smolagents import CodeAgent, LiteLLMModel, tool
from smolagents.agents import ActionStep


sandbox = None


at_dump_script = """import pyatspi
import xml.etree.ElementTree as ET

def build_tree(accessible):
    # 获取控件类型，并将空格替换为连字符
    role_name = accessible.getRoleName() if accessible else "unknown"
    tag_name = role_name.replace(" ", "-")
    node = ET.Element(tag_name)
    
    # 获取 Name 和 Description
    try:
        if accessible.name:
            node.set('name', str(accessible.name))
        if accessible.description:
            node.set('description', str(accessible.description))
    except Exception:
        pass
        
    # 获取状态信息
    try:
        state_set = accessible.getState()
        node.set('visible', 'true' if state_set.contains(pyatspi.STATE_VISIBLE) else 'false')
        node.set('showing', 'true' if state_set.contains(pyatspi.STATE_SHOWING) else 'false')
        node.set('enabled', 'true' if state_set.contains(pyatspi.STATE_ENABLED) else 'false')
    except Exception:
        pass

    # 获取坐标和尺寸
    try:
        extents = accessible.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        node.set('screencoord', f"({extents.x}, {extents.y})")
        node.set('size', f"({extents.width}, {extents.height})")
    except NotImplementedError:
        pass
        
    # 递归获取子节点
    for i in range(accessible.getChildCount()):
        try:
            child = accessible.getChildAtIndex(i)
            if child:
                node.append(build_tree(child))
        except Exception:
            pass
            
    return node

# 获取桌面根节点
desktop = pyatspi.Registry.getDesktop(0)
if desktop:
    root = build_tree(desktop)
    print(ET.tostring(root, encoding='unicode'))
else:
    print("<error>Desktop not found</error>")
"""


def init_sandbox(timeout: int):
    sandbox_instance = Sandbox.create(timeout=timeout)
    # sandbox_instance.commands.run("sudo apt-get update && sudo apt-get install -y python3-pyatspi")
    # sandbox_instance.files.write("/home/user/dump_at.py", at_dump_script)
    return sandbox_instance


def process_ui_tree(xml_str: str, screenshot_bytes: bytes):
    """
    解析 XML，过滤不可见节点，并在截图上画带有数字 ID 的边界框。
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return None, "XML 解析失败"

    # 加载截图
    image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体，如果失败则使用默认字体
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        font = ImageFont.load_default()

    filtered_elements = []
    text_information = ["ID\tTag\tName\tCenter_X\tCenter_Y"]
    element_mapping = {} # 用于映射 ID 到中心坐标
    
    element_id = 1

    # 遍历并过滤节点
    for node in root.iter():
        # 启发式过滤规则：必须可见、且有意义
        visible = node.get("visible") == "true"
        showing = node.get("showing") == "true"
        name = node.get("name", "").strip()
        tag = node.tag
        
        # 只保留交互元素或者有名字的元素
        is_interactive = tag.endswith("button") or tag in [
            "link", "menu", "menu-item", "entry", "check-box", "combo-box", "text"
        ] or name != ""

        if visible and showing and is_interactive:
            coord_str = node.get("screencoord", "(-1, -1)")
            size_str = node.get("size", "(-1, -1)")
            
            try:
                # 安全解析坐标字符串 "(x, y)"
                x, y = ast.literal_eval(coord_str)
                w, h = ast.literal_eval(size_str)
                
                # 剔除无效尺寸或坐标
                if w <= 0 or h <= 0 or x < 0 or y < 0:
                    continue
                    
                bottom_right = (x + w, y + h)
                center_x = x + w // 2
                center_y = y + h // 2
                
                # 在图片上画红框
                draw.rectangle([(x, y), bottom_right], outline="red", width=2)
                
                # 画黑色底色的 ID 标签
                text_position = (x, y)
                text_bbox = draw.textbbox(text_position, str(element_id), font=font)
                draw.rectangle(text_bbox, fill="black")
                draw.text(text_position, str(element_id), font=font, fill="white")
                
                # 记录元素信息
                text_information.append(f"{element_id}\t{tag}\t{name}\t{center_x}\t{center_y}")
                element_mapping[element_id] = (center_x, center_y)
                
                element_id += 1
                
            except (ValueError, SyntaxError):
                continue
                
    # 返回标注好的图片、文本列表、以及用于点击的坐标映射字典
    linearized_text = "\n".join(text_information)
    return image, linearized_text, element_mapping


def get_observation():
    """从 E2B 获取截图和 UI 树，并进行标注处理"""
    screenshot_bytes = sandbox.screenshot()
    
    result = sandbox.commands.run("python3 /home/user/dump_at.py")
    if result.error:
        raise Exception(f"Failed to dump UI tree: {result.error}")
    else:
        raw_xml = result.stdout
    
    annotated_img, linear_text, mapping = process_ui_tree(raw_xml, screenshot_bytes)
    annotated_img.save("annotated_desktop.png")
    
    return linear_text, mapping


def save_screenshot(memory_step: ActionStep, agent: CodeAgent):
    sleep(1.0)
    current_step = memory_step.step_number
    for previous_memory_step in agent.memory.steps:
        if isinstance(previous_memory_step, ActionStep) and previous_memory_step.step_number <= current_step - 2:
            previous_memory_step.observations_images = None
    screenshot = sandbox.screenshot()
    image = Image.open(BytesIO(screenshot))
    image.save(f"screenshot_step_{current_step}.png")
    print(f"Captured a browser screenshot: {image.size} pixels")
    memory_step.observations_images = [image.copy()]
