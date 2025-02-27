* pyinstaller --onefile --icon=docker-manager.png docker-manager.py
* sudo mv ./dist/docker-manager /usr/local/bin/docker-manager

# Compilation

Votre script est écrit en Python, et Python est un langage interprété, pas compilé. Cela signifie qu'il n'y a pas de processus de "compilation" au sens classique (comme
pour C ou Java), mais plutôt une exécution directe par l'interpréteur Python. Cependant, je suppose que vous voulez peut-être savoir comment **exécuter** ce script ou
éventuellement le **transformer en un exécutable** (par exemple, un fichier `.exe` sous Windows ou un binaire autonome sous Linux/Mac) pour le distribuer ou l'utiliser
sans avoir besoin d'installer Python manuellement.

Je vais vous expliquer les deux options principales : **exécuter le script** et **créer un exécutable**.

---

### 1. **Exécuter le script directement**

Pour exécuter le script tel quel, suivez ces étapes :

#### Prérequis :

- **Python 3 installé** : Assurez-vous que Python 3 est installé sur votre système. Vous pouvez vérifier avec `python3 --version` ou `python --version` dans un terminal.
- **Dépendances installées** :
    - Installez les bibliothèques nécessaires avec pip :
      ```bash
      pip3 install docker tkinter
      ```
    - Note : Sous Linux, `tkinter` peut nécessiter une installation supplémentaire via le gestionnaire de paquets (par exemple, `sudo apt-get install python3-tk` sur
      Debian/Ubuntu). Sous Windows/Mac, il est généralement inclus avec Python.

#### Exécution :

1. Enregistrez le script dans un fichier, par exemple `docker-manager.py`.
2. Ouvrez un terminal dans le dossier contenant le fichier.
3. Exécutez le script avec :
   ```bash
   python3 docker-manager.py
   ```
   ou, si `python3` n’est pas reconnu (par exemple sous Windows) :
   ```bash
   python docker-manager.py
   ```

#### Remarques :

- Assurez-vous que Docker est en cours d’exécution sur votre système (`docker info` pour tester).
- Le script doit avoir les permissions d’exécution sous Linux/Mac. Si nécessaire, ajoutez :
  ```bash
  chmod +x docker-manager.py
  ```
  Ensuite, vous pouvez le lancer avec `./docker-manager.py` si la première ligne (`#!/usr/bin/env python3`) est présente.

---

### 2. **Créer un exécutable (optionnel)**

Si vous voulez "compiler" le script en un fichier exécutable autonome (sans avoir besoin d’installer Python ou les dépendances sur la machine cible), vous pouvez utiliser
un outil comme **PyInstaller**.

#### Prérequis :

- Installez PyInstaller :
  ```bash
  pip3 install pyinstaller
  ```

#### Étapes pour créer un exécutable :

1. Enregistrez le script dans un fichier, par exemple `docker-manager.py`.
2. Ouvrez un terminal dans le dossier contenant le fichier.
3. Exécutez PyInstaller avec cette commande :
   ```bash
   pyinstaller --onefile docker-manager.py
   ```
    - `--onefile` : Crée un seul fichier exécutable (plus simple à distribuer).
    - Si vous avez une icône (par exemple, `docker-manager.png`), ajoutez-la avec :
      ```bash
      pyinstaller --onefile --icon=docker-manager.png docker-manager.py
      ```

4. Une fois terminé, PyInstaller génère :
    - Un dossier `dist/` contenant l’exécutable (`docker-manager` ou `docker-manager.exe` sous Windows).
    - Des dossiers temporaires (`build/`, `__pycache__/`) et un fichier `.spec` que vous pouvez ignorer ou supprimer.

5. Testez l’exécutable :
    - Sous Linux/Mac : `./dist/docker-manager`
    - Sous Windows : Double-cliquez sur `dist/docker-manager.exe` ou lancez-le via le terminal.

#### Remarques :

- **Taille** : L’exécutable inclut Python et toutes les dépendances, donc il peut faire plusieurs Mo (10-20 Mo typiquement).
- **Dépendances externes** : Docker doit toujours être installé et en cours d’exécution sur la machine cible, car PyInstaller ne peut pas empaqueter le daemon Docker
  lui-même.
- **Icône** : Si `docker-manager.png` n’est pas trouvé ou au mauvais format, supprimez l’option `--icon` ou convertissez l’image en `.ico` pour Windows (avec un outil
  comme GIMP ou un convertisseur en ligne).

---

### Résolution des problèmes courants

- **Erreur "No module named 'docker'"** : Assurez-vous que `docker` est installé via `pip3 install docker`.
- **Erreur Tkinter** : Installez `python3-tk` si nécessaire (voir Prérequis).
- **Docker non accessible** : Vérifiez que Docker est lancé (`sudo systemctl start docker` sous Linux) et que l’utilisateur a les permissions (ajoutez-le au groupe
  `docker` avec `sudo usermod -aG docker $USER` puis redémarrez la session).

---

### Quelle option choisir ?

- Si vous voulez juste **tester ou utiliser le script localement**, exécutez-le directement avec `python3 docker-manager.py`.
- Si vous voulez **distribuer l’application** à des utilisateurs sans Python, utilisez PyInstaller pour créer un exécutable.

Dites-moi si vous avez besoin d’aide pour une étape spécifique ou si vous voulez un script compilé pour un OS particulier (je peux vous guider davantage) !