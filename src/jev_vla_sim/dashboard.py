"""RoboJEV laboratory display, using only measured state and recorded API outputs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .tasks import TASKS

BG = (10, 16, 27)
PANEL = (20, 30, 45)
INK = (232, 240, 250)
MUTED = (147, 165, 185)
CYAN = (65, 210, 227)
AMBER = (255, 178, 68)
TRACK = (44, 57, 74)


def font(size, bold=False):
    for path in (f"/usr/share/fonts/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
                 f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
                 f"C:/Windows/Fonts/{'arialbd' if bold else 'arial'}.ttf"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


class Dashboard:
    def __init__(self, fps, policy_name):
        self.fps, self.policy_name = fps, policy_name
        self.state = self.decision = None
        self.exchange = {}
        self.frame_index = 0
        self.fonts = {n: font(n) for n in (12, 13, 14, 16, 18, 22, 30)}
        self.brand = font(30, True)

    def set_context(self, state, decision=None, exchange=None):
        self.state = state.to_dict() if hasattr(state, "to_dict") else state
        self.decision = decision
        self.exchange = exchange or {}

    def text(self, d, x, y, text, size=14, color=INK):
        d.text((x, y), str(text), font=self.fonts[size], fill=color)

    def bar(self, d, x, y, label, probability, chosen, width=108):
        self.text(d, x, y, label, 12, INK if chosen else MUTED)
        d.rectangle((x + 76, y + 5, x + 76 + width, y + 9), fill=TRACK)
        if probability is not None:
            value = min(1., max(0., probability))
            if value:
                d.rectangle((x + 76, y + 5, x + 76 + width * value, y + 9),
                            fill=AMBER if chosen else CYAN)
        self.text(d, x + width + 86, y, "--" if probability is None else f"{probability:.0%}", 12)

    def compose(self, pixels):
        out = Image.new("RGB", (1280, 720), BG)
        # Letterbox a wide scene viewport; do not obscure the robot with side panels.
        scene = Image.fromarray(pixels).convert("RGB")
        scene.thumbnail((960, 490), Image.Resampling.LANCZOS)
        out.paste(scene, ((1280 - scene.width) // 2, 62))
        d = ImageDraw.Draw(out)
        d.text((28, 16), "RoboJEV", font=self.brand, fill=INK)
        state = self.state or {}
        task = TASKS.get(state.get("task_id", "pick_place"), TASKS["pick_place"])
        self.text(d, 222, 25, task.title.upper(), 16, CYAN)
        policy = "JEV / TWO STAGES" if self.policy_name == "jev" else self.policy_name.upper()
        self.text(d, 1010, 23, policy, 14, AMBER)
        d.line((28, 60, 1252, 60), fill=TRACK, width=1)
        self.text(d, 28, 91, "OBSERVATION", 12, MUTED)
        self.text(d, 28, 115, "Simulator state", 14)
        self.text(d, 28, 137, "No image input", 12, MUTED)
        if state:
            robot, rel = state["robot"], state["relations"]
            for row, (label, value) in enumerate(zip("XYZ", robot["tcp_position"])):
                self.text(d, 28, 192 + row * 24, f"{label}  {value:+.3f} m", 14)
            self.text(d, 28, 281, f"Jaw  {robot['gripper_width'] * 1000:.0f} mm", 14)
            self.text(d, 28, 305, "CONTACT" if any(robot["finger_object_contacts"]) else "FREE", 12, CYAN)
            self.text(d, 1090, 98, "CYCLE", 12, MUTED)
            self.text(d, 1090, 121, f"{state['step_id']:03d}", 30)
            latency = self.exchange.get("latency_ms")
            self.text(d, 1090, 188, "API LATENCY", 12, MUTED)
            self.text(d, 1090, 212, f"{latency:.0f} ms" if latency is not None else "--", 18)
            self.text(d, 1090, 267, "OBJECT HEIGHT", 12, MUTED)
            self.text(d, 1090, 291, f"{rel['cube_bottom_above_table_m'] * 1000:.0f} mm", 18)
        d.rounded_rectangle((20, 554, 1260, 679), radius=10, fill=PANEL)
        intent = self.exchange.get("intent", {}).get("response", {}).get("answers", {}).get("intent", {})
        self.text(d, 36, 565, "01  INTENT", 12, CYAN)
        self.text(d, 36, 587, intent.get("choice", "No model response").upper(), 16)
        ordered = list(self.exchange.get("intent", {}).get("request", {}).get("questions", {})
                       .get("intent", {}).get("criteria", {}))
        probabilities = intent.get("probabilities", {})
        # All intent probabilities remain visible; missing values stay unavailable.
        for i, name in enumerate(ordered):
            col, row = divmod(i, 4)
            value = probabilities.get(name)
            self.text(d, 245 + col * 139, 580 + row * 21,
                      f"{name} {'--' if value is None else format(value, '.0%')}", 12,
                      AMBER if name == intent.get("choice") else MUTED)
        answers = self.exchange.get("response", {}).get("answers", {})
        for col, key in enumerate(("x", "y", "z", "gripper")):
            x = 555 + col * 174
            self.text(d, x, 565, key.upper(), 12, CYAN)
            options = ("negative", "zero", "positive") if key != "gripper" else ("open", "hold", "close")
            answer = answers.get(key, {})
            for row, name in enumerate(options):
                self.bar(d, x, 594 + row * 23, name, answer.get("probabilities", {}).get(name),
                         name == answer.get("choice"), width=44)
        step = state.get("relations", {}).get("action_step_m", .01)*1000
        self.text(d, 28, 693, f"MuJoCo / base XYZ / {step:g} mm steps / simulation-time playback; API waits omitted", 12, MUTED)
        self.text(d, 1140, 691, f"{self.frame_index / self.fps:06.2f} s", 16, CYAN)
        self.frame_index += 1
        return np.asarray(out)
