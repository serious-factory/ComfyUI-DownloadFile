# ComfyUI - Download File

Un seul nœud ComfyUI pour télécharger un fichier image ou audio via URL, l’enregistrer dans le dossier temporaire et le renvoyer sous forme de tenseur (`IMAGE`/`AUDIO`) ou chemin de fichier.

## Installation
1. Copier ce dépôt dans `ComfyUI/custom_nodes` :
   ```bash
   cd ComfyUI/custom_nodes
   git clone https://github.com/your-org/comfyui-downloadfile.git
   ```
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Relancer ComfyUI.

## Usage rapide
- Ajoutez le nœud **Download File**.
- Renseignez une URL HTTP/HTTPS pointant vers une image (`jpg/png/webp/gif`) ou un audio (`mp3/wav/flac/ogg/m4a`).
- Optionnel : `expect_type` (auto/image/audio) pour forcer le type attendu, `max_mb` pour limiter la taille (par défaut 50 MB).
- Branchez la sortie `IMAGE` vers vos nœuds image, ou `AUDIO` vers vos nœuds audio. La sortie `filepath` donne le fichier téléchargé dans le répertoire temporaire ComfyUI.

## Sécurité intégrée
- Filtrage HTTP/HTTPS uniquement, blocage des hôtes privés/loopback pour éviter le SSRF.
- Timeouts (connexion/lecture) et limite de taille configurable.
- Whitelist MIME/extension pour images et audio ; types non supportés rejetés.

## Dépendances principales
- `requests`, `torch`, `torchaudio`, `pillow`, `numpy` (ComfyUI fournit `folder_paths`).
