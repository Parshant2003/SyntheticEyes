# Synthetic Head Modeling & Texturing – Realistic Eye Motion

**Samsung PRISM Hackathon 2026**  
XR Perception Group | 3D Assets Track

A Google GNM v3 head model with Python-controlled eyes, eyelids, and eyebrows. Procedural skin and iris textures are applied using GNM's UV coordinates, and videos are rendered using Blender.

## Project Structure

| Folder / File | Description |
|---|---|
| `blend/SyntheticEyes_final.blend` | Final Blender file containing the GNM head, textures, and "generate motion" animation. Play it using the Timeline. |
| `blend/gnm_head_v3_rig.blend` | Rig containing eye pivots, eyelid/brow shape keys, and drivers, without animation. |
| `textures/` | 8 skin maps (4096x4096), `skin_bump.png`, 6 iris maps (2048x2048, separate left/right maps), and debug sheets. |
| `renders/images/` | 8 rendered images featuring 8 different skin textures. |
| `renders/videos/` | Left, right, up, down, and generate motion videos (each under 15 seconds). |
| `src/eye_control.py` | **Python control wrapper:** `move_left()`, `move_right()`, `move_up()`, `move_down()`, `generate_motion()`. |
| `ui/control_panel.py` | Simple Tkinter control panel with 5 buttons. |
| `assets/gnm_neutral.npz` | GNM neutral head data (mesh, UV coordinates, and vertex groups). |
| `assets/GNM_LICENSE` | GNM license information. |

## Project Documentation

- [Hackathon Presentation – Submission Final](docs/Submission_Final_AlphaCoders.pptx)
- [AI Usage Disclosure – AlphaCoders](docs/AlphaCoders_AI_Disclosure.docx)

## Requirements

- Windows 11
- Blender 5.3
- Python 3.13
- FFmpeg

The project was developed and tested using this software configuration.

### Environment Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

If Blender is installed at a different location, specify its path in PowerShell:

```powershell
$env:BLENDER_EXE = "C:\path\to\blender.exe"
```

## How to Run

### Command-Line Controls

```bash
python src\eye_control.py left
```

Available commands:

- `left`
- `right`
- `up`
- `down`
- `generate`

### Additional Options

```bash
python src\eye_control.py generate --quality draft
python src\eye_control.py left --cpu
python ui\control_panel.py
```

- `--quality draft`: Generates a smaller, faster test render.
- `--cpu`: Uses the CPU instead of the GPU.
- `python ui\control_panel.py`: Launches the button-based control panel.

### Using Python Directly

```python
import eye_control
eye_control.move_left()
```

Make sure the `src` directory is included in the Python path.

Rendered videos are saved in `renders/videos/`. Temporary frame files are stored in a temporary directory, which can be customized using `EYES_FRAMES_DIR`.

## Viewing Animation in Blender

1. Open `blend/SyntheticEyes_final.blend`.
2. Press `Space` in the Timeline to play the animation.
3. Eye gaze keyframes are controlled through the rotation of:
   - `GNM_left_eye`
   - `GNM_right_eye`
4. Blinking and eyebrow movements are controlled through shape keys on `GNM_skin`:
   - `Blink_L/R`
   - `BrowUp_*`
   - `BrowDown_*`
5. Keyframes and interpolation (Bezier) can be edited using the Dope Sheet or Graph Editor.

### Coordinate Conventions

- Positive yaw (+) = Screen RIGHT.
- Positive pitch (+) = DOWN.
- LEFT/RIGHT directions are defined from the viewer's perspective.

## Rebuilding the Entire Pipeline

Run the following commands in sequence to rebuild the project from scratch:

```bash
python src/export_gnm.py          # Optional; requires GNM installation
python src/make_textures.py       # Generate textures

blender --factory-startup --background --python src/build_head.py
blender --factory-startup --background --python src/add_groups.py

python src/render_stills.py       # Render 8 stills and generate blend/gnm_head_v2_textured.blend

blender --factory-startup --background --python src/build_rig.py

python src/render_all.py          # Generate 5 videos

blender --factory-startup --background --python src/make_final_blend.py
```

## Important Technical Notes

- **Procedural Textures:** All textures are procedurally generated using NumPy/OpenCV noise and masks derived from GNM UV regions. They are NOT scanned or photographic textures. GNM only provides a UV wireframe; it does not include skin textures.
- **Hair and Eyelashes:** The head model does not include hair or eyelashes. Eyebrows are painted directly onto the skin texture.
- **Eyelid Deformation:** Eyelid deformation is implemented using vertex-math-based shape keys. These are not original GNM eyelid blendshapes. No dedicated blink control was found in the GNM model.
- **Rendering Performance:** Tested on Intel Arc 130T at 720x720 resolution with 32 samples:
  - GPU: Approximately 5 seconds per frame.
  - CPU: Approximately 10 seconds per frame.
- **Testing Environment:** The project has only been tested on one machine running Windows 11, Blender 5.3.0, and Python 3.13.

## Licenses and Credits

### Head Model – Google GNM

The head model is based on **GNM (Google)**, licensed under the Apache License 2.0.

- GitHub Repository: https://github.com/google/GNM
- GNM v3 Model Weights: https://huggingface.co/google/gnm-v3
- License Information: `assets/GNM_LICENSE`
- `assets/gnm_neutral.npz` contains data exported from the GNM model.

### Project Code and Textures

All remaining code and textures were developed as part of this project.
