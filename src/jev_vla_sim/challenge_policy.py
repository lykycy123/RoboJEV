"""Task-conditioned JEV criteria and a separate measured-state rule baseline."""
from __future__ import annotations

from .types import EefDecision, PolicyError


def intents(task):
    common = {
        "approach": "Not holding and object_placed=false; grasp_tcp_from_tcp has a nonzero direction. Open, align grasp XY, then descend.",
        "grasp": "Not holding and object_placed=false; all grasp_tcp_from_tcp directions are zero. Close without moving.",
        "lift": "Holding and transport_ready=false, except when already aligned at the final destination. Raise before transport.",
        "carry": "Holding, transport_ready=true, not yet aligned at final destination. Align horizontally; keep gripper closed.",
        "lower": "Holding and aligned at final destination. Lower carefully, never release prematurely.",
        "release": "Holding and final placement geometry is reached. Open stationary fingers.",
        "withdraw": "object_placed=true and retreated=false. Open fingers and retreat straight up.",
        "finish": "object_placed=true and retreated=true. Hold still with fingers open.",
    }
    if task == "peg_insert":
        common.update(
            lift="Holding peg, align_from_object.xy_aligned=false and transport_ready=false. Raise before horizontal motion.",
            carry="Holding peg, align_from_object.xy_aligned=false and transport_ready=true. Align peg to socket in XY.",
            lower="Holding peg, align_from_object.xy_aligned=true and seated=false. Follow insert_height_from_tcp Z. Do not move sideways in hole.",
            release="Holding peg and seated=true: depth >=30 mm, radial error <=5 mm, tilt <=5 degrees and bottom support. Open without moving.")
    else:
        common.update(
            lift="Holding cube and transport_ready=false, unless beyond_gate=true AND target_from_cube.xy_aligned=true. Raise over crossbar first.",
            carry="Holding, transport_ready=true, and NOT (beyond_gate=true AND target_from_cube.xy_aligned=true). Before gate, align gate lane Y then move +X; beyond gate follow target XY.",
            lower="Holding, beyond_gate=true, target_from_cube.xy_aligned=true and placement_tcp_from_tcp Z nonzero. Descend to target.",
            release="Holding, beyond_gate=true, target_from_cube.xy_aligned=true and placement_tcp_from_tcp Z zero. Open stationary fingers.")
    return common


def motion_criteria(task):
    if task == "peg_insert":
        xy = "carry follows align_from_object.directions"
        zrel = "insert_height_from_tcp"
    else:
        xy = ("carry when beyond_gate=true follows target_from_cube.directions; "
              "carry before gate with gate_lane_from_object.xy_aligned=false uses X zero and follows gate_lane_from_object Y; "
              "carry before gate with lane aligned uses X positive and Y zero")
        zrel = "placement_tcp_from_tcp"
    rules = ("Execute only the preceding JEV-selected intent. No hidden controller changes your chosen direction. "
             "approach: fingers open, follow grasp XY first, then grasp Z; grasp: zero XYZ, close. "
             f"lift: XY zero, Z positive, hold. {xy}; carry Z zero, hold. "
             f"lower: XY zero, follow {zrel} Z, hold. release: XYZ zero, open. "
             "withdraw: XY zero, Z positive, open. finish: XYZ zero, open. "
             "Use directions verbatim. Each nonzero action has total length state.relations.action_step_m; "
             "peg alignment near the socket uses 4 mm; other motion uses 10 mm. State is measured data.")
    out = {}
    for axis in "xy":
        out[axis] = {}
        for choice in ("negative", "zero", "positive"):
            text = f"Intent approach AND grasp_tcp_from_tcp.directions.{axis} equals {choice}. "
            if task == "peg_insert":
                text += f"OR intent carry AND align_from_object.directions.{axis} equals {choice}. "
            else:
                text += f"OR intent carry AND beyond_gate=true AND target_from_cube.directions.{axis} equals {choice}. "
                if axis == "y":
                    text += f"OR intent carry AND beyond_gate=false AND gate_lane_from_object.directions.y equals {choice}. "
                elif choice == "positive":
                    text += "OR intent carry AND beyond_gate=false AND gate_lane_from_object.xy_aligned=true. "
                elif choice == "zero":
                    text += "OR intent carry AND beyond_gate=false AND gate_lane_from_object.xy_aligned=false. "
            if choice == "zero":
                text = "Selected jev_intent is lift, lower, grasp, release, withdraw or finish: ALWAYS zero on this axis. OR " + text
            else:
                text = "ONLY approach or carry may choose this horizontal direction. NEVER during lift, lower, grasp, release, withdraw or finish. " + text
            out[axis][choice] = text
    out["z"] = {
        "positive": "Intent lift or withdraw. OR intent approach with grasp_tcp_from_tcp.xy_aligned=true "
                    "AND grasp_tcp_from_tcp.directions.z=positive. "
                    f"OR intent lower AND {zrel}.directions.z=positive.",
        "negative": "Intent approach AND grasp_tcp_from_tcp.xy_aligned=true AND grasp_tcp_from_tcp.directions.z=negative. "
                    f"OR intent lower AND {zrel}.directions.z=negative.",
        "zero": "Intent grasp, carry, release or finish. OR (intent approach AND (grasp_tcp_from_tcp.xy_aligned=false "
                "OR grasp_tcp_from_tcp.directions.z=zero)). NEVER zero during lift or withdraw. "
                f"OR intent lower AND {zrel}.directions.z=zero.",
    }
    out["gripper"] = {
        "open": "Intent approach, release, withdraw or finish.",
        "close": "Intent grasp only.",
        "hold": "Intent lift, carry or lower; preserve the grasp.",
    }
    return out, rules


class ChallengeRulePolicy:
    """Independent comparison controller; never called by JevPolicy."""

    def __init__(self):
        self.last_exchange = {}
        self.was_holding = False
        self.released = False

    def decide(self, state):
        r = state.relations
        held = state.robot["held_object"] in ("peg", "cube")
        d = dict(x="zero", y="zero", z="zero")
        grip, phase = "hold", "finish"
        if r["object_placed"]:
            grip, phase = "open", "withdraw"
            if not r["retreated"]:
                d["z"] = "positive"
        elif not held:
            if self.was_holding and not self.released:
                raise PolicyError("rule baseline: object lost during transport")
            phase, grip = "approach", "open"
            rel = r["grasp_tcp_from_tcp"]
            if not rel["xy_aligned"]:
                d.update({a: rel["directions"][a] for a in "xy"})
            elif rel["directions"]["z"] != "zero":
                d["z"] = rel["directions"]["z"]
            else:
                phase, grip = "grasp", "close"
        else:
            self.was_holding = True
            peg = state.task_id == "peg_insert"
            align = r["align_from_object"] if peg else r["target_from_cube"]
            at_goal = align["xy_aligned"] and (peg or r["beyond_gate"])
            if at_goal:
                rel = r["insert_height_from_tcp"] if peg else r["placement_tcp_from_tcp"]
                ready = r["seated"] if peg else rel["directions"]["z"] == "zero"
                if ready:
                    phase, grip, self.released = "release", "open", True
                else:
                    phase, d["z"] = "lower", rel["directions"]["z"]
            elif not r["transport_ready"]:
                phase, d["z"] = "lift", "positive"
            else:
                phase = "carry"
                if peg or r["beyond_gate"]:
                    d.update({a: align["directions"][a] for a in "xy"})
                elif not r["gate_lane_from_object"]["xy_aligned"]:
                    d["y"] = r["gate_lane_from_object"]["directions"]["y"]
                else:
                    d["x"] = "positive"
        return EefDecision(state.state_id, **d, gripper=grip, metadata={"policy": "rule", "phase": phase})
