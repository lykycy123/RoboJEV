# Third-party components

| Component | Use | Source / license |
|---|---|---|
| MuJoCo | Rigid-body simulation | [google-deepmind/mujoco](https://github.com/google-deepmind/mujoco), Apache-2.0 |
| MuJoCo Menagerie Panda | Robot description and collision/visual meshes | [franka_emika_panda](https://github.com/google-deepmind/mujoco_menagerie/tree/822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7/franka_emika_panda), [Apache-2.0](assets/panda/LICENSE) |
| TypeSafe JEV | Hosted inference API | [typesafe.ai](https://typesafe.ai/); separate service terms and account required |
| NumPy, HTTPX, PyYAML, Pillow, ImageIO | Numerics, networking and media | Installed as dependencies; their distributions retain their own licenses |

The Panda MJCF derives from Franka's public description via MuJoCo Menagerie. Upstream assets are not edited on disk; RoboJEV constructs its task scenes and controller parameters in memory. Asset hashes and the pinned revision are recorded in `assets/panda/manifest.json`.

The original presentation artwork, page styles and media overlays in this repository belong to RoboJEV. This does not claim ownership of the rendered robot design or the underlying techniques. The project is not affiliated with or endorsed by upstream providers.
