# Aillustrate

AI-powered book illustration tool. Analyzes a story file (TXT, PDF, EPUB), extracts characters, environments and scenes using AI, and generates illustrations for each.

---

## Requirements

- Python 3.11 or newer
- A Google Cloud project with Vertex AI enabled
- A Vertex AI API key

---

## Setup

1. **Run `setup.bat`** — creates a virtual environment and installs all dependencies automatically.

2. **Configure API credentials** — rename `config_local_.py` to `config_local.py` and fill in your values:
   ```python
   VERTEX_API_KEY = "your-api-key-here"
   VERTEX_PROJECT = "your-gcp-project-id"
   ```

3. **Run the app** — double-click `run.bat`.

---

## Usage

### Start Screen

- **Left panel** — list of recent projects. Click a card to open it, or use the **OPEN PROJECT** button to browse to a project folder.
- **Right panel** — create a new project by uploading a story file.

### Creating a New Project

1. Click the drop zone and select a `.txt`, `.pdf`, or `.epub` file.
2. Enter a project name (auto-filled from filename).
3. Choose an art style.
4. Optionally set the **Character Threshold** — minimum percentage of chapters a character must appear in to be included. Characters referenced in scenes are always kept regardless of threshold.
5. Check **Generate all images after analysis** to automatically generate portraits, environments and scene illustrations right after analysis finishes.
6. Click **Analyze Book with AI**.

### Workspace Tabs

After a project is loaded, the workspace opens with four tabs accessible from the top navigation bar:

#### Characters
- Lists all extracted characters with their descriptions and portraits.
- Click a character card to expand it and view/edit the description.
- Click **Generate Image** to create or regenerate a portrait.
- Use the **+** button to add a character manually.

#### Environments
- Lists all extracted locations/environments.
- Same controls as Characters — view description, generate image, add manually.

#### Scenes
- Each scene card shows the scene title, involved characters and environment.
- Click **Generate Image** to illustrate a scene.
- Scenes reference characters and environments from the other tabs.

#### Export
- Exports the project as an illustrated PDF.
- Choose output type.
- Click **Export PDF** to generate the final illustrated book.

### Saving

- Project autosaves after every action
- **Save As** — creates a copy of the project under a new name.

### Navigation

- The active model for image generation can be changed from the model selector in the top bar (remembered for characters, environments and scenes separately).
- The active model for image generation can be changed from the model selector in the top bar (global).

---

## Configuration (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `MAX_ANALYZE_CHAPTERS` | `2` | How many chapters to analyze. `0` = all chapters. |
| `MAX_SCENES_PER_CHAPTER` | `2` | Max scenes extracted per chapter. `0` = no limit. |
| `ANALYZE_CHARACTERS` | `True` | Whether to extract characters during analysis. |
| `ANALYZE_SCENES` | `True` | Whether to extract scenes during analysis. |
| `ANALYZE_ENVIRONMENTS` | `True` | Whether to extract environments (requires `ANALYZE_SCENES = True`). |
| `TEXT_MODEL` | `gemini-3.1-pro-preview` | Vertex AI model used for text analysis. |
| `IMAGE_MODELS` | *(list)* | Available image generation models. First one is used by default. |

---

## Project Structure

```
Projects/
  <ProjectName>/
    project.json          # All project data (characters, scenes, environments)
    source/               # Copy of the original story file
    images/
      characters/
      environments/
      scenes/
```

Each project is a self-contained folder inside `Projects/`. You can open any project folder via **OPEN PROJECT**.
