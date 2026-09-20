# Physical task specifications

All tasks use a 4 cm, 50 g cube, a Panda with downward tool orientation, 1 cm normalized Cartesian steps, and MuJoCo time step 0.002 s. XYZ directions are robot-base axes. Joint control, action validation and contact parameters are shared between policies for each task.

| Task | Scene | Completion |
|---|---|---|
| `pick_place` | 12 cm square target, randomized separated object/target XY | Cube previously lifted at least 5 cm; full projected footprint inside target; bottom within 5 mm of table; release and settle |
| `push` | Random +X lane, 16–20 cm initial target separation, 12 cm target | Measured robot contact and at least 5 mm object movement; full footprint inside target; disengage and settle |
| `stack` | Fixed 8×8×4 cm pedestal at randomized target XY | Cube previously lifted at least 5 cm; full footprint over pedestal; bottom within 5 mm of support surface; actual support contact; release and settle |

Settling requires speed below 0.02 m/s and angular speed below 0.2 rad/s continuously for 0.5 s. Grasp tasks require jaw opening at least 6.5 cm and both fingers detached. Push requires no robot contact; lifting more than 1 cm or a two-finger grasp invalidates the trial. Falling off the table terminates a trial.

Push uses a lower tool height (22 mm) and an explicit cube/table friction coefficient of 0.3, compared with 1.0 for grasp tasks. This sliding surface prevents the cube tipping before it slides. Finger friction remains 1.0. Layout sampling and material parameters are identical for both policies and frozen before formal evaluation.

Grasp and stack have approach, grasp, lift, carry, lower, release, withdraw and finish intent choices. Push has approach, descend, push, withdraw and finish. These are task descriptions supplied to JEV; Python does not select the model's intent. Geometry helpers are engineered and exposed to the model, so this is not an unassisted spatial-reasoning benchmark.

Grasp contact is determined from the summed normal force on each finger, threshold 0.1 N. A close command is not proof of a grasp. Success uses physical measurements and history maintained separately from the policy. The intent named `finish` is never authoritative.

Episodes allow at most 200 decisions for pick/place and 250 for push/stack. Response choice must agree with the probability argmax; malformed or inconsistent answers terminate the episode without executing that decision. Transport and transient service errors receive at most two retries per stage. State IDs prevent stale or duplicate execution.
