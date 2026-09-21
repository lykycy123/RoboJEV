# Challenge Evaluation

Frozen source: `d5a76ee31cd893072c2a54a41f5b0d151c4a2789c9cff4af029b9d15a7f8afdd`.

Seeds 0-9 per task and policy. Every completed failure remains in the denominator.

Videos render the exact recorded physical states of these trials, without another API call.

| Task | JEV | Rule | JEV Wilson 95% |
|---|---:|---:|---|
| Peg insertion | 10/10 | 10/10 | 72.2% - 100.0% |
| Gate pick & place | 5/10 | 8/10 | 23.7% - 76.3% |

## Results and observed limits / 结果与失败边界

The new campaign completed all 40 trials: two tasks × two policies × seeds 0–9. JEV uses `jev-1.13.0`; the independent rule policy is never a fallback. The original 60 trials retain their own frozen source. All 100 published trials remain in the denominator.

| 任务 / Task | JEV | 规则 / Rule | JEV Wilson 95% |
|---|---:|---:|---|
| 宽松插销 / Loose-fit insertion | 10/10 | 10/10 | 72.2%–100.0% |
| 跨障碍抓放 / Gate pick & place | 5/10 | 8/10 | 23.7%–76.3% |

插销直径 20 mm、插孔直径 30 mm，名义径向余量 5 mm。成功要求插入至少 30 mm、中心线两端偏移不超过 5 mm、倾角不超过 5°，并接触孔底、松爪、稳定 0.5 s。JEV 与规则各 10 次均成功，没有自然失败录像，也没有通过这十次试验定位出插销的经验失败极限。

跨障碍任务要求 40 mm 方块在 70 mm 门宽内越过 120 mm 横梁，通过时底部净空至少 5 mm；机器人或物体对门框的接触力总和超过 0.05 N 即失败。最终必须放入目标区并稳定 0.5 s。成功 JEV 种子为 2、3、4、5、6。

| 策略 / Policy | Seed | 决策 / Decision | 观测原因与触发边界 / Observed cause and boundary |
|---|---:|---:|---|
| JEV | 0 | 120 | 放低时 link5 碰 gate_post_1，44.00 N > 0.05 N；方块已过门 |
| JEV | 1 | 350 | 抓取方向为 −Y，仍请求 +Y；302 次工作空间拒绝，仅执行 48 次，耗尽 350 次决策且未抓到物体 |
| JEV | 7 | 75 | Y 选择 positive 的概率 0.49，小于另一选项 0.50；严格 argmax 校验失败，该次动作未执行 |
| JEV | 8 | 350 | 抓取方向为 −Y，仍请求 +Y；305 次工作空间拒绝，仅执行 45 次，耗尽 350 次决策且未抓到物体 |
| JEV | 9 | 120 | 放低时 link5 碰 gate_post_1，26.59 N > 0.05 N；方块已过门 |
| Rule | 0 | 240 | 放低时 link5 碰 gate_post_1，17.39 N > 0.05 N |
| Rule | 4 | 130 | 放低时 link5 碰 gate_post_1，15.03 N > 0.05 N |

These are three observed failure mechanisms: arm-link collision while lowering after the object crossed; repeated +Y requests against a measured −Y grasp direction until the 350-decision budget was exhausted; and one inconsistent model choice rejected before execution. Terminal contact reconstruction identifies `link5` against `gate_post_1`, and its force matches the original record. In JEV seeds 0 and 9, lowering also began with remaining target X errors of 32.2 mm and 28.8 mm respectively. Rule collisions occurred even with target XY alignment. Object clearance and TCP alignment therefore do not establish clearance for every arm link.

失败暴露了当前控制器的全臂避障不足，以及模型方向选择和响应一致性的限制。终止时方块已在门后下降，报告中的负净空不是“过门时净空不足”的证据；碰撞位置由原始终帧接触重建确认。每项仅十次试验，以上数值是本次协议的判定边界和观测值，不能视为普适的最大可通过障碍尺寸。正式测试后未调整控制代码、阈值或替换失败回合。

## Original-trial videos / 原始回合录像

| 内容 / Outcome | Seed | 视频 / Video |
|---|---:|---|
| 插销成功 / Insertion success | 0 | [MP4](../site/media/peg_insert-success.mp4) |
| 插销失败 / Insertion failure | — | 无自然失败 / No natural failure |
| 跨障碍成功 / Gate success | 2 | [MP4](../site/media/obstacle_pick_place-success.mp4) |
| 跨障碍失败 / Gate failure | 0 | [MP4](../site/media/obstacle_pick_place-failure.mp4) |

Each video uses the lowest-seed available JEV outcome, rendered directly from captured original physical states at 30 fps, without another policy/API call or physics rollout. API waits are omitted; the last two seconds are a labeled still. The selected gate success had 59.96 mm minimum crossing clearance and zero gate contact. The manifest records video and capture hashes. Raw captures and model responses remain in the private experiment archive.

Validation: 113 tests passed and Ruff passed on Python 3.11; 25 independent rule development probes (five tasks × seeds 1000–1004) succeeded before the formal campaign. The insertion cylinder uses shared rotational damping and contact parameters described in [task specifications](tasks.md).

## Failure Evidence

Failures describe observed limits under this fixed protocol; ten trials do not locate a universal failure threshold.

### obstacle_pick_place / jev / seed 0

- Termination: `obstacle_collision`; diagnostic: `obstacle_collision`.
- Boundary: robot or object gate contact force > 0.05 N
- Decision: 120; executed actions: 120.
- Rejected actions: 0; tracking timeouts: 1.
- Actual contacting bodies: gate / link5 (43.996 N).
- Attribution: these contacts were reconstructed from the exact terminal state; the summed force matches the recorded failure.

```json
{
  "object_bottom_m": 0.010102682052977693,
  "contact_force_n": 43.99629640384023,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.1098973179470223,
  "lateral_clearance_m": 0.004356040050735428,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.5886276533706185,
  "object_max_x_m": 0.6287335736074897,
  "linear_speed_m_s": 0.0603849857804344,
  "angular_speed_rad_s": 0.02684147231782439,
  "support_contact": false,
  "max_gate_contact_force_n": 43.99629640384023
}
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 116,
    "intent": "lift",
    "action": {
      "x": "positive",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.047635382784399063,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.005373537605238954,
          -7.68610661871158e-05,
          0.0021269990529968336
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.03783232381860169,
          0.0020107621501322774,
          -0.0678114156614074
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.03783232381860169,
          0.0020107621501322774,
          -0.04263538278439906
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        0.006034847419583378,
        -1.1844511765463778e-05,
        -0.006265369768423401
      ]
    }
  },
  {
    "decision": 117,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.041370841569808206,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.005387105408188653,
          -7.736881766980466e-05,
          0.002122719015911531
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.03178390859606861,
          0.00202311441338043,
          -0.06154176585589869
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.03178390859606861,
          0.00202311441338043,
          -0.0363708415698082
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014000159611182728,
        -8.33898884145326e-06,
        -0.008849748768291477
      ]
    }
  },
  {
    "decision": 118,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.0325271214218148,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.00538017706957572,
          -7.688473750286709e-05,
          0.0021334381680993553
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.03193083853079337,
          0.0020309693220549457,
          -0.05270273623979504
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.03193083853079337,
          0.0020309693220549457,
          -0.0275271214218148
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014381504960470082,
        -7.759500225568844e-06,
        -0.008852448033269164
      ]
    }
  },
  {
    "decision": 119,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.02367508484215618,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.005386945071118476,
          -7.690260735829235e-05,
          0.0021334092717676806
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.032067885578855315,
          0.00203874669213594,
          -0.0438502593101942
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.032067885578855315,
          0.00203874669213594,
          -0.01867508484215618
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.0001454946938298507,
        -7.870264958808465e-06,
        -0.008851655932816782
      ]
    }
  },
  {
    "decision": 120,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.014823649884974026,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.0053935204750386045,
          -7.694662723842921e-05,
          0.002133407836136067
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.03220680486876504,
          0.002046660976974885,
          -0.034998601941745804
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.03220680486876504,
          0.002046660976974885,
          -0.009823649884974025
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "tracking_timeout",
      "delta_measured_m": [
        4.83595725961905e-05,
        5.54544144903274e-06,
        -0.0046446644442452445
      ]
    }
  }
]
```

### obstacle_pick_place / rule / seed 0

- Termination: `obstacle_collision`; diagnostic: `obstacle_collision`.
- Boundary: robot or object gate contact force > 0.05 N
- Decision: 240; executed actions: 240.
- Rejected actions: 0; tracking timeouts: 1.
- Actual contacting bodies: gate / link5 (17.385 N).
- Attribution: these contacts were reconstructed from the exact terminal state; the summed force matches the recorded failure.

```json
{
  "object_bottom_m": 0.006116256791620332,
  "contact_force_n": 17.38538177254206,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.11388374320837966,
  "lateral_clearance_m": -0.00034643892525806214,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.6179183035573913,
  "object_max_x_m": 0.6579607688142927,
  "linear_speed_m_s": 0.0286209298704688,
  "angular_speed_rad_s": 0.00946280320542416,
  "support_contact": false,
  "max_gate_contact_force_n": 17.38538177254206
}
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 236,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.04912008304115066,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.006100006747063569,
          -7.828246215278375e-05,
          0.0019610589113845944
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.0019913523009905676,
          -0.0027057956697980334,
          -0.06928650396026442
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.0019913523009905676,
          -0.0027057956697980334,
          -0.04412008304115066
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.0001423812959605586,
        -8.647442188331605e-06,
        -0.008868910478708358
      ]
    }
  },
  {
    "decision": 237,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.04025111065046941,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.006106553345860188,
          -7.832087033817978e-05,
          0.001960832099396334
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.0021271869981545066,
          -0.002697109819424306,
          -0.06041736666956781
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.0021271869981545066,
          -0.002697109819424306,
          -0.0352511106504694
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014434664385842844,
        -8.769514328009487e-06,
        -0.008868265127036784
      ]
    }
  },
  {
    "decision": 238,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.03138287823384453,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.006113001288891695,
          -7.836358369784843e-05,
          0.0019606926879075434
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.0022650856989814283,
          -0.0026882975917366277,
          -0.051548962131042236
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.0022650856989814283,
          -0.0026882975917366277,
          -0.026382878233844526
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014628638713609643,
        -8.889812463653418e-06,
        -0.008867617555372756
      ]
    }
  },
  {
    "decision": 239,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.022515384710286957,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.006119353739952205,
          -7.841074012366125e-05,
          0.001960637170085877
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.002405019635057015,
          -0.0026793606228471614,
          -0.042681289057847814
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.002405019635057015,
          -0.0026793606228471614,
          -0.017515384710286956
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.0001482024326405762,
        -9.008414957267785e-06,
        -0.008866969791166107
      ]
    }
  },
  {
    "decision": 240,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.013648626280821557,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.006125614155365056,
          -7.846245592253373e-05,
          0.001960661366040492
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.0025469616522847405,
          -0.002670300492091021,
          -0.03381434346263632
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.0025469616522847405,
          -0.002670300492091021,
          -0.008648626280821557
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "tracking_timeout",
      "delta_measured_m": [
        -0.00012600307554155865,
        -7.240994712682386e-06,
        -0.007511900025079968
      ]
    }
  }
]
```

### obstacle_pick_place / jev / seed 1

- Termination: `max_decisions`; diagnostic: `obstacle_crossing_timeout`.
- Boundary: decision budget exhausted before valid crossing, released containment and 0.5 s stability
- Decision: 350; executed actions: 48.
- Rejected actions: 302; tracking timeouts: 0.

```json
{
  "object_bottom_m": -0.00021551084043238203,
  "contact_force_n": 0.0,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.12021551084043237,
  "lateral_clearance_m": 0.0007663845090040387,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.36851391088977803,
  "object_max_x_m": 0.40851391088977806,
  "linear_speed_m_s": 5.722320271571353e-16,
  "angular_speed_rad_s": 1.0436740460881002e-15,
  "support_contact": false,
  "max_gate_contact_force_n": 0.0,
  "crossed_gate": false,
  "min_crossing_clearance_m": null
}
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 346,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0018725634790870416,
          -0.35859922311736564,
          -0.43425391620077
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.27994557252433927,
          0.006706873571415381,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.27807300904525223,
          -0.3518923495459503,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 347,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0018725634790870416,
          -0.35859922311736564,
          -0.43425391620077
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.27994557252433927,
          0.006706873571415381,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.27807300904525223,
          -0.3518923495459503,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 348,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0018725634790870416,
          -0.35859922311736564,
          -0.43425391620077
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.27994557252433927,
          0.006706873571415381,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.27807300904525223,
          -0.3518923495459503,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 349,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0018725634790870416,
          -0.35859922311736564,
          -0.43425391620077
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.27994557252433927,
          0.006706873571415381,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.27807300904525223,
          -0.3518923495459503,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 350,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0018725634790870416,
          -0.35859922311736564,
          -0.43425391620077
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.27994557252433927,
          0.006706873571415381,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.27807300904525223,
          -0.3518923495459503,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  }
]
```

### obstacle_pick_place / rule / seed 4

- Termination: `obstacle_collision`; diagnostic: `obstacle_collision`.
- Boundary: robot or object gate contact force > 0.05 N
- Decision: 130; executed actions: 130.
- Rejected actions: 0; tracking timeouts: 1.
- Actual contacting bodies: gate / link5 (15.027 N).
- Attribution: these contacts were reconstructed from the exact terminal state; the summed force matches the recorded failure.

```json
{
  "object_bottom_m": 0.004681802344721226,
  "contact_force_n": 15.026677177719117,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.11531819765527877,
  "lateral_clearance_m": 0.014567847442030948,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.6226573432392756,
  "object_max_x_m": 0.6628019623879108,
  "linear_speed_m_s": 0.02995889659487302,
  "angular_speed_rad_s": 0.010032126651845743,
  "support_contact": false,
  "max_gate_contact_force_n": 15.026677177719117
}
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 126,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.047593953659384375,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.00029703219584242824,
          4.957333591938673e-06,
          0.002219356223117336
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          -0.0008558289462738955,
          0.0038366267980410873,
          -0.06766171475994266
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          -0.0008558289462738955,
          0.0038366267980410873,
          -0.04259395365938437
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014228394093729335,
        -1.0611794720782886e-05,
        -0.008873449194135047
      ]
    }
  },
  {
    "decision": 127,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.038720623751131514,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.0003034931982891509,
          4.946992484815282e-06,
          0.0022192404724697967
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          -0.0007200060077833248,
          0.0038472489338689936,
          -0.058788149815160076
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          -0.0007200060077833248,
          0.0038472489338689936,
          -0.033720623751131516
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.0001443193586770919,
        -1.066592135311184e-05,
        -0.008872865495367546
      ]
    }
  },
  {
    "decision": 128,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.029847962491599014,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.00030985931399274413,
          4.927928372727708e-06,
          0.002219207080298928
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          -0.0005820527648098262,
          0.003857933919334193,
          -0.049915250927621654
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          -0.0005820527648098262,
          0.003857933919334193,
          -0.024847962491599013
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.000146331802995725,
        -1.0715948598916114e-05,
        -0.008872279850558898
      ]
    }
  },
  {
    "decision": 129,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.020975968193789357,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.00031613390193574453,
          4.8996595575084845e-06,
          0.0022192521308446594
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          -0.00044199554975710154,
          0.0038686781367483283,
          -0.04104301612760849
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          -0.00044199554975710154,
          0.0038686781367483283,
          -0.015975968193789356
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014832313445700684,
        -1.0762319578243307e-05,
        -0.008871694277486047
      ]
    }
  },
  {
    "decision": 130,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.012104636546180988,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.00032232063502080077,
          4.861815865168928e-06,
          0.002219371052956623
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          -0.00029985914838515093,
          0.003879478300018911,
          -0.032171440772234404
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          -0.00029985914838515093,
          0.003879478300018911,
          -0.007104636546180987
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      }
    },
    "execution": {
      "executed": true,
      "reason": "tracking_timeout",
      "delta_measured_m": [
        -0.00012061466826385203,
        -8.34350646339993e-06,
        -0.00739872922181746
      ]
    }
  }
]
```

### obstacle_pick_place / jev / seed 7

- Termination: `policy_error`; diagnostic: `policy_error`.
- Boundary: episode terminated: policy_error
- Decision: 75; executed actions: 74.
- Rejected actions: 0; tracking timeouts: 0.
- Detail: invalid TypeSafe choice response; no action executed

```json
{
  "object_bottom_m": -0.00021551084043238203,
  "contact_force_n": 0.0,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.12021551084043237,
  "lateral_clearance_m": 0.003972572390192261,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.36691641402908726,
  "object_max_x_m": 0.4069164140290873,
  "linear_speed_m_s": 5.596296869787568e-16,
  "angular_speed_rad_s": 1.1170748134830743e-15,
  "support_contact": false,
  "max_gate_contact_force_n": 0.0,
  "crossed_gate": false,
  "min_crossing_clearance_m": null
}
```

Recorded model-choice validation:

```json
[
  {
    "stage": "intent",
    "head": "intent",
    "choice": "approach",
    "selected_probability": 0.99,
    "maximum_probability": 0.99
  },
  {
    "stage": "motor",
    "head": "x",
    "choice": "zero",
    "selected_probability": 1.0,
    "maximum_probability": 1.0
  },
  {
    "stage": "motor",
    "head": "y",
    "choice": "positive",
    "selected_probability": 0.49,
    "maximum_probability": 0.5
  },
  {
    "stage": "motor",
    "head": "z",
    "choice": "zero",
    "selected_probability": 0.97,
    "maximum_probability": 0.97
  },
  {
    "stage": "motor",
    "head": "gripper",
    "choice": "open",
    "selected_probability": 0.87,
    "maximum_probability": 0.87
  }
]
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 70,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0034238341890807655,
          0.00956116388395461,
          -0.19294315216396085
        ],
        "directions": {
          "x": "zero",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2598398016706305,
          -0.019020776213358723,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2564159674815497,
          -0.009459612329404114,
          0.005215510840432369
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -3.223835225996119e-07,
        0.009944142972832632,
        6.836169438861894e-08
      ]
    }
  },
  {
    "decision": 71,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "negative",
      "z": "negative",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.003423511805558166,
          -0.00038297908887802157,
          -0.1929432205256552
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.2598398016706305,
          -0.019020776213358723,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2564162898650723,
          -0.019403755302236744,
          0.005215510840432369
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -7.1868196631630354e-06,
        -0.007031907220067444,
        -0.007034749413214525
      ]
    }
  },
  {
    "decision": 72,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.003416324985895003,
          0.006648928131189422,
          -0.1859084711124407
        ],
        "directions": {
          "x": "zero",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2598398016706305,
          -0.019020776213358723,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2564234766847355,
          -0.012371848082169302,
          0.005215510840432369
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -3.642479714516256e-07,
        0.009944154713164396,
        6.518346171158207e-08
      ]
    }
  },
  {
    "decision": 73,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "negative",
      "z": "negative",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0034159607379235513,
          -0.0032952265819749735,
          -0.18590853629590243
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.2598398016706305,
          -0.019020776213358723,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2564238409327069,
          -0.022316002795333696,
          0.005215510840432369
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -7.293244583206349e-06,
        -0.007031995663393256,
        -0.007034719254151917
      ]
    }
  },
  {
    "decision": 74,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "negative",
      "z": "negative",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.00021551084043238203,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.003408667493340345,
          0.0037367690814182827,
          -0.17887381704175048
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.2598398016706305,
          -0.019020776213358723,
          -0.01978448915956762
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.25643113417729013,
          -0.015284007131940442,
          0.005215510840432369
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -7.487762208713278e-06,
        -0.007031922146729461,
        -0.00703467847257902
      ]
    }
  }
]
```

### obstacle_pick_place / jev / seed 8

- Termination: `max_decisions`; diagnostic: `obstacle_crossing_timeout`.
- Boundary: decision budget exhausted before valid crossing, released containment and 0.5 s stability
- Decision: 350; executed actions: 45.
- Rejected actions: 305; tracking timeouts: 0.

```json
{
  "object_bottom_m": -0.0002155108404323751,
  "contact_force_n": 0.0,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.12021551084043237,
  "lateral_clearance_m": 0.007748433539201998,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.36961830530013845,
  "object_max_x_m": 0.4096183053001385,
  "linear_speed_m_s": 4.784470005372279e-16,
  "angular_speed_rad_s": 9.39450228262475e-16,
  "support_contact": false,
  "max_gate_contact_force_n": 0.0,
  "crossed_gate": false,
  "min_crossing_clearance_m": null
}
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 346,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.0002155108404323751,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0007748704437333109,
          -0.3604429432091023,
          -0.4483196284258527
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2740381627744624,
          0.02204742692864665,
          -0.019784489159567625
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2732632923307291,
          -0.3383955162804556,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 347,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.0002155108404323751,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0007748704437333109,
          -0.3604429432091023,
          -0.4483196284258527
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2740381627744624,
          0.02204742692864665,
          -0.019784489159567625
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2732632923307291,
          -0.3383955162804556,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 348,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.0002155108404323751,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0007748704437333109,
          -0.3604429432091023,
          -0.4483196284258527
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2740381627744624,
          0.02204742692864665,
          -0.019784489159567625
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2732632923307291,
          -0.3383955162804556,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 349,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.0002155108404323751,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0007748704437333109,
          -0.3604429432091023,
          -0.4483196284258527
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2740381627744624,
          0.02204742692864665,
          -0.019784489159567625
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2732632923307291,
          -0.3383955162804556,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  },
  {
    "decision": 350,
    "intent": "approach",
    "action": {
      "x": "zero",
      "y": "positive",
      "z": "zero",
      "gripper": "open"
    },
    "held_object": null,
    "measured_before_action": {
      "object_bottom_m": -0.0002155108404323751,
      "transport_ready": false,
      "beyond_gate": false,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          -0.0007748704437333109,
          -0.3604429432091023,
          -0.4483196284258527
        ],
        "directions": {
          "x": "zero",
          "y": "negative",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "target_from_cube": {
        "delta_m": [
          0.2740381627744624,
          0.02204742692864665,
          -0.019784489159567625
        ],
        "directions": {
          "x": "positive",
          "y": "positive",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.2732632923307291,
          -0.3383955162804556,
          0.005215510840432425
        ],
        "directions": {
          "x": "positive",
          "y": "negative",
          "z": "zero"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": false,
      "reason": "workspace_rejected",
      "delta_measured_m": [
        0.0,
        0.0,
        0.0
      ]
    }
  }
]
```

### obstacle_pick_place / jev / seed 9

- Termination: `obstacle_collision`; diagnostic: `obstacle_collision`.
- Boundary: robot or object gate contact force > 0.05 N
- Decision: 120; executed actions: 120.
- Rejected actions: 0; tracking timeouts: 1.
- Actual contacting bodies: gate / link5 (26.586 N).
- Attribution: these contacts were reconstructed from the exact terminal state; the summed force matches the recorded failure.

```json
{
  "object_bottom_m": 0.009074754528177038,
  "contact_force_n": 26.585714345820772,
  "socket_force_n": 0.0,
  "gate_clearance_m": -0.11092524547182296,
  "lateral_clearance_m": 0.007850521316643065,
  "gate_x_m": 0.51,
  "object_min_x_m": 0.6146362329942486,
  "object_max_x_m": 0.654753136232925,
  "linear_speed_m_s": 0.045735342518486856,
  "angular_speed_rad_s": 0.018318627419976505,
  "support_contact": false,
  "max_gate_contact_force_n": 26.585714345820772
}
```

Last decision requests (including rejected requests; measured state before each action):

```json
[
  {
    "decision": 116,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.05058236351961079,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.004624957307362898,
          6.364050987821973e-05,
          0.0021788316381144424
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.028269463044958587,
          0.0015893903978860882,
          -0.07075964087999898
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.028269463044958587,
          0.0015893903978860882,
          -0.04558236351961079
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014149781161498787,
        -1.0816765748725143e-05,
        -0.008867694118742733
      ]
    }
  },
  {
    "decision": 117,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.04171467136363005,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.004631605917239656,
          6.364281082260614e-05,
          0.002178592503027335
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.028404312246696817,
          0.001600204862690427,
          -0.06189170762616915
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.028404312246696817,
          0.001600204862690427,
          -0.03671467136363005
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014345333733722931,
        -1.0897176450308521e-05,
        -0.008867050811840693
      ]
    }
  },
  {
    "decision": 118,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.03284768543109652,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.004638121639732984,
          6.363417427571183e-05,
          0.0021784342460864983
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.02854124986154072,
          0.0016111106756876298,
          -0.05302449855738761
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.02854124986154072,
          0.0016111106756876298,
          -0.027847685431096524
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014538185202228604,
        -1.0974401986989235e-05,
        -0.008866403739863818
      ]
    }
  },
  {
    "decision": 119,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.023981429687613735,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.0046445342481624685,
          6.361610301317683e-05,
          0.002178358462502146
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.02868021910513352,
          0.001622103148937154,
          -0.04415801903393944
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.02868021910513352,
          0.001622103148937154,
          -0.018981429687613734
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "executed",
      "delta_measured_m": [
        -0.00014728641337713455,
        -1.1048126778448464e-05,
        -0.008865756093946423
      ]
    }
  },
  {
    "decision": 120,
    "intent": "lower",
    "action": {
      "x": "zero",
      "y": "zero",
      "z": "negative",
      "gripper": "hold"
    },
    "held_object": "cube",
    "measured_before_action": {
      "object_bottom_m": 0.01511590416564041,
      "transport_ready": false,
      "beyond_gate": true,
      "grasp_tcp_from_tcp": {
        "delta_m": [
          0.004650850369484205,
          6.358849993792076e-05,
          0.0021783618155806067
        ],
        "directions": {
          "x": "zero",
          "y": "zero",
          "z": "zero"
        },
        "xy_aligned": true
      },
      "target_from_cube": {
        "delta_m": [
          0.028821189397188918,
          0.0016331788787908585,
          -0.03529226629307148
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      },
      "placement_tcp_from_tcp": {
        "delta_m": [
          0.028821189397188918,
          0.0016331788787908585,
          -0.01011590416564041
        ],
        "directions": {
          "x": "positive",
          "y": "zero",
          "z": "negative"
        },
        "xy_aligned": false
      }
    },
    "execution": {
      "executed": true,
      "reason": "tracking_timeout",
      "delta_measured_m": [
        -4.4544170946458905e-05,
        -1.9749951517891717e-06,
        -0.005992933946139825
      ]
    }
  }
]
```
