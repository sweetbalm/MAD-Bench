import os
import io
import re
import json
import time
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from contextlib import redirect_stdout, redirect_stderr

from e2b_desktop import Sandbox
from smolagents import CodeAgent, LiteLLMModel, OpenAIModel

from modules import tools, utils


def parse_task_index_arg(task_index_arg: Optional[str]) -> Optional[Union[int, List[int]]]:
    if task_index_arg is None:
        return None

    text = task_index_arg.strip()
    if not text:
        return None

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid task-index list: {task_index_arg}") from e

        if not isinstance(parsed, list) or not all(isinstance(item, int) for item in parsed):
            raise ValueError("task-index list must contain integers only.")
        return parsed

    if "," in text:
        try:
            return [int(item.strip()) for item in text.split(",") if item.strip()]
        except ValueError as e:
            raise ValueError(f"Invalid comma-separated task-index list: {task_index_arg}") from e

    try:
        return int(text)
    except ValueError as e:
        raise ValueError(f"Invalid task-index value: {task_index_arg}") from e


def clean_agent_log(raw_log: str) -> str:
    text = raw_log

    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub("", text)

    text = re.sub(r"Captured a screenshot:.*\n?", "", text)

    text = re.sub(
        r"\[Step\s+\d+:\s+Duration.*?Output tokens:.*?\]\n?",
        "",
        text,
        flags=re.DOTALL,
    )

    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if all(ch in "─━│╭╮╰╯ " for ch in stripped):
            continue

        if stripped.startswith("│") and stripped.endswith("│"):
            stripped = stripped[1:-1].strip()

        if "New run" in stripped:
            cleaned_lines.append("New run")
            continue

        if "LiteLLMModel -" in stripped:
            continue

        step_match = re.search(r"Step\s+(\d+)", stripped)
        if step_match and "Step" in stripped:
            cleaned_lines.append("")
            cleaned_lines.append(f"Step {step_match.group(1)}")
            continue

        if "Executing parsed code:" in stripped:
            cleaned_lines.append("Executing parsed code:")
            continue

        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)

    text = re.sub(r"^(New run)$", r"\1\n", text, flags=re.MULTILINE)
    text = re.sub(r"^(Task:)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^(Execution logs:)$", r"\1", text, flags=re.MULTILINE)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


class AgentRunner:
    def __init__(
        self,
        dataset_dir: str = "dataset",
        prompt_dir: str = "prompt",
        trajectory_root: str = "trajectories",
        model_id: str = "",
        api_key: str = "",
        e2b_api_key: str = "",
        sandbox_timeout: int = 1200,
        max_steps: int = 30,
    ):
        self.dataset_dir = Path(dataset_dir)
        self.prompt_dir = Path(prompt_dir)
        self.trajectory_root = Path(trajectory_root)
        self.trajectory_root.mkdir(parents=True, exist_ok=True)

        self.model_id = model_id
        self.api_key = api_key
        self.e2b_api_key = e2b_api_key
        self.sandbox_timeout = sandbox_timeout
        self.max_steps = max_steps

        if self.e2b_api_key:
            os.environ["E2B_API_KEY"] = self.e2b_api_key

        self.model = LiteLLMModel(
            model_id=self.model_id,
            api_key=self.api_key,
        )

        # You can switch to OpenAIModel.
        # self.model = OpenAIModel(
        #     model_id="",
        #     api_base="",
        #     api_key=""
        # )

    def load_dataset(self, task_type: int) -> List[Dict[str, Any]]:
        dataset_path = self.dataset_dir / f"task_{task_type}.json"
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"{dataset_path} must contain a list of tasks.")

        return data

    def load_system_instruction(self, input_type: int) -> str:
        prompt_path = self.prompt_dir / f"input_type_{input_type}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def build_prompt(self, input_type: int, instruction: str) -> str:
        system_instruction = self.load_system_instruction(input_type)
        return f"{system_instruction}\n\nTask:\n{instruction.strip()}"

    def resolve_tools(self, tool_names: List[str]) -> List:
        resolved = []
        for name in tool_names:
            if not hasattr(tools, name):
                raise AttributeError(f"modules.tools has no tool named '{name}'")
            resolved.append(getattr(tools, name))
        return resolved

    def create_sandbox(self, task: Dict[str, Any]) -> Sandbox:
        input_type = task.get("input_type")
        with_extra_setup = (input_type == 2)

        sandbox = utils.init_sandbox(
            timeout=self.sandbox_timeout,
            with_extra_setup=with_extra_setup,
        )
        tools.sandbox = sandbox
        utils.sandbox = sandbox
        return sandbox

    def run_payload(self, sandbox: Sandbox, payload_code: str) -> None:
        if not payload_code or not payload_code.strip():
            return

        exec_globals = {
            "sandbox": sandbox,
            "time": time,
            "os": os,
            "json": json,
            "__builtins__": __builtins__,
        }
        exec(payload_code, exec_globals)

    def create_agent(self, task: Dict[str, Any]) -> CodeAgent:
        tool_list = self.resolve_tools(task.get("tool", []))

        input_type = task.get("input_type")
        if input_type == 0:
            step_callbacks = []
        elif input_type == 1:
            step_callbacks = [utils.input_screenshot]
        elif input_type == 2:
            step_callbacks = [utils.input_sc_and_txt]
        else:
            raise ValueError(f"Unsupported input_type: {input_type}")

        agent = CodeAgent(
            tools=tool_list,
            model=self.model,
            add_base_tools=False,
            step_callbacks=step_callbacks,
            max_steps=self.max_steps,
        )
        return agent

    def create_task_trajectory_dir(self, task: Dict[str, Any]) -> Path:
        task_type = task.get("task_type", "unknown")
        task_index = task.get("task_index", "unknown")

        task_dir = self.trajectory_root / f"tasktype_{task_type}_task_{task_index}"
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def save_run_log(self, task_dir: Path, raw_log: str) -> None:
        cleaned_log = clean_agent_log(raw_log)
        log_path = task_dir / "run_log.txt"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(cleaned_log)

    def save_task_info(self, task_dir: Path, task: Dict[str, Any], prompt: str) -> None:
        info = {
            "task": task,
            "prompt": prompt,
        }
        with open(task_dir / "task_info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    def save_result_files(
        self,
        task_dir: Path,
        agent_output: Any = None,
        error: Optional[str] = None,
    ) -> None:
        if agent_output is not None:
            with open(task_dir / "final_answer.txt", "w", encoding="utf-8") as f:
                f.write(str(agent_output))

        if error is not None:
            with open(task_dir / "error.txt", "w", encoding="utf-8") as f:
                f.write(str(error))

    def select_tasks(
        self,
        tasks: List[Dict[str, Any]],
        num_tasks: Optional[int] = None,
        shuffle: bool = False,
        seed: int = 42,
        task_index: Optional[Union[int, List[int]]] = None,
    ) -> List[Dict[str, Any]]:
        selected = list(tasks)

        if task_index is not None:
            if isinstance(task_index, list):
                task_index_set = set(task_index)
                selected = [task for task in selected if task.get("task_index") in task_index_set]
                return selected

            if num_tasks is not None:
                end_index = task_index + num_tasks
                selected = [
                    task for task in selected
                    if isinstance(task.get("task_index"), int) and task_index <= task.get("task_index") < end_index
                ]
                return selected

            selected = [task for task in selected if task.get("task_index") == task_index]
            return selected

        if shuffle:
            rng = random.Random(seed)
            rng.shuffle(selected)

        if num_tasks is not None:
            selected = selected[:num_tasks]

        return selected

    def run_single_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        sandbox = None
        agent = None
        agent_output = None
        prompt = None
        log_buffer = io.StringIO()

        result = {
            "task_index": task.get("task_index"),
            "task_type": task.get("task_type"),
            "status": "pending",
            "error": None,
        }

        task_dir = self.create_task_trajectory_dir(task)

        try:
            # Tell utils where screenshots for this task should be saved
            utils.set_trajectory_dir(str(task_dir))

            sandbox = self.create_sandbox(task)

            # Execute payload after fixed sandbox initialization
            self.run_payload(sandbox, task.get("payload", ""))

            prompt = self.build_prompt(
                input_type=task["input_type"],
                instruction=task["instruction"],
            )
            self.save_task_info(task_dir, task, prompt)

            agent = self.create_agent(task)

            # Capture agent logs
            with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
                agent_output = agent.run(prompt)

            raw_log = log_buffer.getvalue()
            self.save_run_log(task_dir, raw_log)
            self.save_result_files(task_dir, agent_output=agent_output)

            result["status"] = "success"
            result["agent_output"] = agent_output

        except Exception as e:
            result["status"] = "failed"
            result["error"] = repr(e)

            raw_log = log_buffer.getvalue()
            if raw_log:
                try:
                    self.save_run_log(task_dir, raw_log)
                except Exception:
                    pass

            self.save_result_files(task_dir, agent_output=agent_output, error=repr(e))

        finally:
            if sandbox is not None:
                try:
                    sandbox.kill()
                except Exception as kill_err:
                    print(f"[Task {task.get('task_index')}] Failed to kill sandbox: {kill_err}")

        return result

    def run_tasks(
        self,
        task_type: int,
        num_tasks: Optional[int] = None,
        shuffle: bool = False,
        seed: int = 42,
        task_index: Optional[Union[int, List[int]]] = None,
    ) -> List[Dict[str, Any]]:
        tasks = self.load_dataset(task_type)
        selected_tasks = self.select_tasks(
            tasks,
            num_tasks=num_tasks,
            shuffle=shuffle,
            seed=seed,
            task_index=task_index,
        )

        if not selected_tasks:
            raise ValueError("No tasks selected. Please check task_type/task_index.")

        print(f"Loaded {len(tasks)} tasks from task_{task_type}.json")
        print(f"Running {len(selected_tasks)} task(s)...")

        results = []
        for idx, task in enumerate(selected_tasks, start=1):
            print("=" * 100)
            print(f"[{idx}/{len(selected_tasks)}] Running task_index={task.get('task_index')}")
            res = self.run_single_task(task)
            results.append(res)

            print(f"Status: {res['status']}")
            if res["error"]:
                print(f"Error: {res['error']}")

        return results


def parse_args():
    parser = argparse.ArgumentParser(description="Run benchmark tasks.")

    parser.add_argument("--task-type", type=int, required=True, help="Load dataset/task_{task_type}.json")
    parser.add_argument(
        "--task-index",
        type=str,
        default=None,
        help="Run a single task_index, a list like '[12,15,17]' or '12,15,17', or a start index used with --num-tasks",
    )
    parser.add_argument(
        "--num-tasks",
        type=int,
        default=None,
        help="Number of tasks to run. If used with a single --task-index, runs a consecutive range starting from that index.",
    )
    parser.add_argument("--shuffle", action="store_true", help="Shuffle tasks before selection")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for shuffle")

    parser.add_argument("--dataset-dir", type=str, default="dataset", help="Directory of task json files")
    parser.add_argument("--prompt-dir", type=str, default="prompt", help="Directory of input_type prompt files")
    parser.add_argument("--trajectory-root", type=str, default="gpt_trajectories", help="Directory to save task trajectories")

    parser.add_argument("--model-id", type=str, default="", help="Model id")
    parser.add_argument("--api-key", type=str, default="", help="Model API key")
    parser.add_argument("--e2b-api-key", type=str, default="", help="E2B API key")

    parser.add_argument("--sandbox-timeout", type=int, default=1200, help="Sandbox timeout")
    parser.add_argument("--max-steps", type=int, default=30, help="Max steps for CodeAgent")

    parser.add_argument("--save-path", type=str, default=None, help="Optional file to save batch results as json")

    return parser.parse_args()


def main():
    args = parse_args()
    parsed_task_index = parse_task_index_arg(args.task_index)

    runner = AgentRunner(
        dataset_dir=args.dataset_dir,
        prompt_dir=args.prompt_dir,
        trajectory_root=args.trajectory_root,
        model_id=args.model_id,
        api_key=args.api_key,
        e2b_api_key=args.e2b_api_key,
        sandbox_timeout=args.sandbox_timeout,
        max_steps=args.max_steps,
    )

    results = runner.run_tasks(
        task_type=args.task_type,
        num_tasks=args.num_tasks,
        shuffle=args.shuffle,
        seed=args.seed,
        task_index=parsed_task_index,
    )

    if args.save_path:
        save_path = Path(args.save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Results saved to: {save_path}")


if __name__ == "__main__":
    main()
