from __future__ import annotations

import time
from pathlib import Path

from .config import Config
from .recording import EpisodeLog, write_json
from .types import PolicyError


def run_episode(backend, policy, cfg: Config, run: Path, policy_name: str, seed: int, video: bool):
    episode_id = f"{cfg.task}_{policy_name}_seed_{seed:04d}"
    log = EpisodeLog(run/episode_id, video, cfg.video_fps, policy_name)
    backend.frame_sink = log.frame if video else None
    start = time.perf_counter()
    success, reason, decisions, executed, requests, tokens = False, "max_decisions", 0, 0, 0, 0
    rejected, stalls, empty_grasps, oscillations = 0, 0, 0, 0
    state_ms, api_ms, physics_ms, render_ms = 0., 0., 0., 0.
    output_tokens = 0
    last_delta = None
    try:
        state = backend.reset(seed, episode_id)
        log.set_context(state)
        write_json(log.directory/"initial_state.json", state.to_dict())
        for _ in range(cfg.max_decisions):
            started = time.perf_counter()
            state = backend.observe()
            state_ms += (time.perf_counter()-started)*1000
            record = {"state": state.to_dict()}
            decision_recorded = False
            started = time.perf_counter()
            try:
                decisions += 1
                decision = policy.decide(state)
                api_ms += (time.perf_counter()-started)*1000
                record["exchange"] = policy.last_exchange
                requests += policy.last_exchange.get("attempts", 0)
                tokens += decision.metadata.get("usage", {}).get("input_tokens", 0)
                output_tokens += decision.metadata.get("usage", {}).get("output_tokens", 0)
                record["decision"] = decision.action_dict()
                record["decision_metadata"] = decision.metadata
                record["event"] = "decision"
                log.set_context(state, decision, policy.last_exchange)
                # Persist BEFORE any physical mutation. Replays consume this event exactly once.
                log.append(record)
                decision_recorded = True
                record = {"event": "execution", "state_id": state.state_id}
                outcome = backend.execute(decision)
                record["execution"] = outcome.to_dict()
                executed += outcome.executed
                rejected += not outcome.executed
                stalls += outcome.reason == "tracking_timeout"
                physics_ms += outcome.physics_ms
                render_ms += outcome.render_ms
                after = backend.observe()
                record["next_state"] = after.to_dict()
                if cfg.task != "push" and decision.gripper == "close" and after.robot["held_object"] is None:
                    empty_grasps += 1
                delta = tuple(outcome.delta_requested_m)
                if last_delta is not None and any(delta) and all(abs(a+b) < 1e-8 for a, b in zip(delta, last_delta)):
                    oscillations += 1
                last_delta = delta
                success = outcome.success
                if success or outcome.failure:
                    reason = "success" if success else outcome.failure
                    log.append(record)
                    break
            except PolicyError as exc:
                reason = "policy_error"
                exchange = policy.last_exchange
                if not decision_recorded:
                    api_ms += (time.perf_counter()-started)*1000
                    requests += exchange.get("attempts", 0)
                    record["exchange"] = exchange
                    for stage in ("intent", "motor"):
                        usage = exchange.get(stage, {}).get("response", {}).get("usage", {})
                        tokens += usage.get("input_tokens", 0)
                        output_tokens += usage.get("output_tokens", 0)
                record["error"] = str(exc)
                log.append(record)
                break
            except Exception:
                # The decision may have executed partially. Log it, then propagate: never retry a mutation.
                record["error"] = "execution_exception_after_decision; inspect process error log"
                log.append(record)
                raise
            log.append(record)
    except Exception as exc:
        reason = "runtime_error"
        log.append({"error_type": type(exc).__name__, "error": str(exc)})
        raise
    finally:
        result = {"episode_id": episode_id, "task": cfg.task, "seed": seed, "policy": policy_name,
                  "success": bool(success), "end_reason": reason, "decisions": decisions,
                  "executed": executed, "rejected": rejected, "tracking_timeouts": stalls,
                  "empty_grasps": empty_grasps, "direction_reversals": oscillations,
                  "api_requests": requests, "input_tokens": tokens, "output_tokens": output_tokens, "wall_s": time.perf_counter()-start,
                  "state_ms": state_ms, "decision_ms": api_ms, "physics_ms": physics_ms,
                  "render_ms": render_ms, "simulation_time_s": backend.tick*cfg.physics_dt}
        write_json(log.directory/"result.json", result)
        backend.frame_sink = None
        log.close()
        policy.close()
    return result
