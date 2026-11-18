# Testing Checklist

Status: PASS = is project mein actual output se verify hua, TO TEST = abhi khud karna hai.

| # | Test | Kaise check karein | Status |
|---|---|---|---|
| 1 | Model loading | `python src\inspect_gnm.py` -> `LOAD_OK`, 17,821 vertices; Blender mein 6 objects (`build_head.py`) | PASS |
| 2 | Texture compatibility | `make_textures.py` -> `TEXTURES_DONE`; `_debug_uv_masks.png` mein hont/bhaunhein/aankh sahi jagah | PASS |
| 3 | UV mapping / seams | 8 stills mein chehre par seam nahi; left-right wrap noise | PASS (visual) |
| 4 | Left eye movement | `left_movement.mp4`: dono aankhein screen-left | PASS |
| 5 | Right eye movement | `right_movement.mp4` | PASS (video render hui; frames contact sheet se dekhe) |
| 6 | Upward movement | `up_movement.mp4`, upper lid saath uthti hai, bhaunhein halki upar | PASS (video render hui) |
| 7 | Downward movement | `down_movement.mp4` | PASS (video render hui) |
| 8 | Eyelid closure | `rig_test/blink_full` mein palkein poori band, lid crease | PASS |
| 9 | Blinking | videos mein har ~2-3 sec par blink (close ~2 frames, open ~4 frames) | PASS |
| 10 | Natural motion | Smooth saccade (~6 frames), overshoot+settle, micro-drift, blinks | PASS (subjective) |
| 11 | Video rendering | 5 videos, har ek < 15 sec, `eye_control` ka OpenCV check | PASS |
| 12 | Blender scene portability | `SyntheticEyes_final.blend` ko doosre folder/PC par kholo; textures packed hain, texture dikhni chahiye | TO TEST |
| 13 | Python script execution (naye PC par) | Naye folder mein README ke steps; `python src\eye_control.py left --quality draft` | TO TEST |
| 14 | Control panel | `python ui\control_panel.py` -> 5 buttons; Start Render se draft video bane | PARTIAL (window khuli; render panel se test karna baaki) |
| 15 | .blend mein animation (Timeline) | `make_final_blend.py` chalao, file kholo, Space dabao | TO TEST |

## PPT requirements ke saamne
| PPT requirement | Kahan |
|---|---|
| GNM/FLAME head load | GNM v3 (`assets/gnm_neutral.npz`, `blend/*.blend`) |
| 5-10 UV texture maps (face + eyes) | `textures/skin_01..08` + `iris_*` (+ `skin_bump.png`) |
| Alag left/right iris | `iris_<color>_left.png`, `iris_<color>_right.png` |
| 5-10 rendered images, alag textures | `renders/images/` (8) |
| Python script (3 inputs, frames -> video) | `src/eye_control.py` (+ UP, DOWN) |
| 3 rendered videos (< 15 s) | `renders/videos/` (left, right, generate; + up, down) |
| .blend + Timeline animation | `blend/SyntheticEyes_final.blend` |
| Eyelids, iris, eyebrows animate | shape keys + eye rotation + brow keys |
| Photorealistic textures | **Procedural, scanned nahi** (limitation README mein) |