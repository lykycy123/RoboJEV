# Physical task specifications

The three original tasks use a 4 cm, 50 g cube. All tasks use a Panda with downward tool orientation and a MuJoCo time step of 0.002 s. XYZ directions are robot-base axes. Joint control, action validation and contact parameters are shared between policies for each task. Translation is normally 1 cm; the insertion task uses 4 mm steps within 25 mm of the socket axis while grasped.

| Task | Scene | Completion |
|---|---|---|
| `pick_place` | 12 cm square target, randomized separated object/target XY | Cube previously lifted at least 5 cm; full projected footprint inside target; bottom within 5 mm of table; release and settle |
| `push` | Random +X lane, 16–20 cm initial target separation, 12 cm target | Measured robot contact and at least 5 mm object movement; full footprint inside target; disengage and settle |
| `stack` | Fixed 8×8×4 cm pedestal at randomized target XY | Cube previously lifted at least 5 cm; full footprint over pedestal; bottom within 5 mm of support surface; actual support contact; release and settle |
| `peg_insert` | Upright 20 mm diameter, 60 mm long, 35 g cylinder; fixed 30 mm socket, 40 mm rim height and 8 mm floor | Previously lifted; depth >=30 mm; centerline end offsets <=5 mm; tilt <=5 degrees; actual floor support; release and settle |
| `obstacle_pick_place` | 40 mm cube; 70 mm opening between 200 mm posts, 120 mm crossbar, 24 mm obstacle thickness; randomized lane/start/target | Carry the whole cube through the opening above the crossbar with >=5 mm bottom clearance; no robot/object gate contact >0.05 N; release in the 120 mm target and settle |
| `double_gate_pick_place` | 40 mm cube; two 90 mm openings with 100/120 mm crossbars, 90 mm lane offset, randomized seed-mirrored layout | Cross gate_1 then change lane and cross gate_2 with >=5 mm clearance, no gate contact >0.05 N, then release in the target and settle |

Settling requires speed below 0.02 m/s and angular speed below 0.2 rad/s continuously for 0.5 s. Grasp tasks require jaw opening at least 6.5 cm and both fingers detached. Push requires no robot contact; lifting more than 1 cm or a two-finger grasp invalidates the trial. Falling off the table terminates a trial.

Push uses a lower tool height (22 mm) and an explicit cube/table friction coefficient of 0.3, compared with 1.0 for grasp tasks. This sliding surface prevents the cube tipping before it slides. Finger friction remains 1.0. Layout sampling and material parameters are identical for both policies and frozen before formal evaluation.

Grasp and stack have approach, grasp, lift, carry, lower, release, withdraw and finish intent choices. Push has approach, descend, push, withdraw and finish. These are task descriptions supplied to JEV; Python does not select the model's intent. Geometry helpers are engineered and exposed to the model, so this is not an unassisted spatial-reasoning benchmark.

Grasp contact is determined from the summed normal force on each finger, threshold 0.1 N. A close command is not proof of a grasp. Success uses physical measurements and history maintained separately from the policy. The intent named `finish` is never authoritative.

Episodes allow at most 200 decisions for pick/place and 250 for push/stack. Response choice must agree with the probability argmax; malformed or inconsistent answers terminate the episode without executing that decision. Transport and transient service errors receive at most two retries per stage. State IDs prevent stale or duplicate execution.

## Challenge boundaries

Insertion allows 450 decisions and gate transport 350. Both use approach, grasp, lift, carry, lower, release, withdraw and finish intentions, with task-specific physical descriptions. Insertion is deliberately a loose-fit task: 5 mm nominal radial clearance, not an industrial precision-fit benchmark. The circular cavity uses 48 fixed wall segments and a physical floor. Cylinder rolling/torsional friction and rotational viscous damping of 0.005 N m s/rad suppress contact chatter; no translational damping is added. Both policies share these physical parameters. No object is welded, teleported or scripted.

Gate transport means over the low crossbar and between the higher posts, not over the whole gate. The preferred transport bottom height is 180 mm to accommodate the Panda fingers; the mandatory clearance boundary remains 5 mm above the 120 mm crossbar. Object footprint containment in the 70 mm lane is checked while crossing the entire 24 mm gate slab. Going around the gate does not satisfy the crossing history.

| Diagnostic | Measured boundary |
|---|---|
| `peg_released_before_insert` | After a grasp and lift, fingers opened before reaching 30 mm insertion depth |
| `peg_jammed` | Socket wall force >0.5 N and object speed <1 mm/s continuously for 2 s before seating |
| `peg_radial_misalignment` | Decision limit reached with centerline end offset >5 mm |
| `peg_insertion_timeout` | Decision limit reached without all insertion, release and stability conditions |
| `obstacle_collision` | Summed robot/object contact force against gate >0.05 N |
| `obstacle_clearance_insufficient` | Object overlaps gate slab with bottom clearance <5 mm |
| `obstacle_lane_violation` | Object footprint extends beyond the 70 mm opening while crossing |
| `object_dropped` | Object below table by >50 mm, or grasp lost during gate crossing |
| `obstacle_crossing_timeout` / `target_miss` | Decision limit reached before valid crossing / after crossing without settled placement |
| `policy_error` | API or response validation fails before the requested action executes |

`failure` includes the diagnostic code, explicit boundary, first failing decision and measurements. Budget-exhaustion diagnostics describe the final unmet conditions, not a proven causal explanation of all preceding behavior. `final_measurements` also records gate traversal, minimum crossing clearance, maximum gate force, support, speed, insertion depth and alignment as applicable. Evaluator history never enters the model observations.

Scene schema version 3 adds optional obstacle geometry. The peg is identified as `peg` in the observation; legacy `cube_*` relation keys remain aliases for the manipulated object. Both policies use the same measured-state step selection and axis alignment tolerances.
