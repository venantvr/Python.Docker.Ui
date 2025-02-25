# Compilation

Je vais compiler ce code Python en un exécutable standalone pour Ubuntu en utilisant PyInstaller. Voici les étapes détaillées que je vais suivre pour te fournir un
exécutable fonctionnel. Comme je ne peux pas te donner directement le fichier binaire ici, je vais te guider pour que tu puisses le faire toi-même sur ta machine Ubuntu.

### Étapes pour compiler

#### 1. Préparer l’environnement

Puisque tu es sur Ubuntu et que tu as eu des problèmes avec la gestion des paquets système, utilisons un environnement virtuel pour éviter les conflits :

```bash
# Supprime tout ancien environnement ou fichiers de build
rm -rf docker_env dist build *.spec

# Crée un environnement virtuel
python3 -m venv docker_env
source docker_env/bin/activate
```

#### 2. Installer les dépendances

Installe les dépendances nécessaires dans l’environnement virtuel et au niveau système :

```bash
# Dépendances système
sudo apt update
sudo apt install python3-dev python3-tk xterm -y

# Dépendances Python
pip install --upgrade pip
pip install docker pyinstaller
```

#### 3. Sauvegarder le code

Assure-toi que le code est dans un fichier nommé `docker-manager.py` :

```bash
nano docker-manager.py
```

Copie-colle le code que tu as fourni, puis sauvegarde (Ctrl+O, Enter, Ctrl+X).

#### 4. Compiler avec PyInstaller

Compile le script en un fichier exécutable unique :

```bash
pyinstaller --onefile docker-manager.py
```

- `--onefile` : Crée un seul fichier exécutable contenant tout (Python, Tkinter, docker-py, etc.).

#### 5. Récupérer et tester l’exécutable

Une fois la compilation terminée :

```bash
# Déplace l’exécutable dans le dossier courant
mv dist/docker-manager .
chmod +x docker-manager

# Teste
./docker-manager
```

### Résultat attendu

- Tu obtiens un fichier `docker-manager` (~10-20 Mo) dans ton dossier.
- En lançant `./docker-manager`, une fenêtre Tkinter de 600x400 pixels (non redimensionnable) s’ouvre avec la liste des containers Docker et les boutons demandés.

### Dépendances système sur la machine cible

L’exécutable inclut Python et les bibliothèques Python, mais certaines dépendances système doivent être présentes sur la machine où tu l’exécutes :

- **Docker** : Le daemon Docker doit être installé et en marche :
  ```bash
  sudo apt install docker.io -y
  sudo systemctl start docker
  sudo systemctl enable docker
  sudo usermod -aG docker $USER  # Relogue-toi après
  ```
- **xterm** : Nécessaire pour ouvrir le shell :
  ```bash
  sudo apt install xterm -y
  ```
- **Tkinter** : Normalement inclus via PyInstaller, mais si des erreurs graphiques surviennent :
  ```bash
  sudo apt install python3-tk -y
  ```

### Script complet pour automatiser

Voici un script bash pour tout faire d’un coup :

```bash
#!/bin/bash

# Préparer l’environnement
rm -rf docker_env dist build *.spec
python3 -m venv docker_env
source docker_env/bin/activate

# Installer les dépendances
sudo apt update
sudo apt install python3-dev python3-tk xterm -y
pip install --upgrade pip
pip install docker pyinstaller

# Sauvegarder le code (remplace cette partie par ton nano ou autre méthode)
cat << 'EOF' > docker-manager.py
#!/usr/bin/env python3

import docker
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

class DockerManagerApp:
    def __init__(self, root):
        self.client = self.get_client()
        self.root = root
        self.root.title("Docker Manager")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        self.tree = ttk.Treeview(self.root, columns=("ID", "Name", "Status"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Nom")
        self.tree.heading("Status", text="Statut")
        self.tree.column("ID", width=100)
        self.tree.column("Name", width=200)
        self.tree.column("Status", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Actualiser", command=self.refresh_list).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Démarrer/Arrêter", command=self.toggle_container).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Supprimer", command=self.delete_container).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Ouvrir Shell", command=self.open_shell).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Quitter", command=self.root.quit).pack(side=tk.LEFT, padx=5)

        self.refresh_list()

    def get_client(self):
        try:
            return docker.from_env()
        except docker.errors.DockerException as e:
            messagebox.showerror("Erreur", f"Connexion à Docker échouée: {e}")
            sys.exit(1)

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        containers = self.client.containers.list(all=True)
        for container in containers:
            status = "Running" if container.status == "running" else "Stopped"
            self.tree.insert("", tk.END, values=(container.short_id, container.name, status))

    def get_selected_container(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Attention", "Veuillez sélectionner un container.")
            return None
        item = self.tree.item(selected[0])
        return item["values"][0]

    def toggle_container(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        container = self.client.containers.get(container_id)
        try:
            if container.status == "running":
                container.stop()
                messagebox.showinfo("Succès", f"Container {container_id} arrêté.")
            else:
                container.start()
                messagebox.showinfo("Succès", f"Container {container_id} démarré.")
            self.refresh_list()
        except docker.errors.APIError as e:
            messagebox.showerror("Erreur", f"Échec: {e}")

    def delete_container(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        if messagebox.askyesno("Confirmer", f"Supprimer le container {container_id} ?"):
            try:
                container = self.client.containers.get(container_id)
                container.remove(force=True)
                messagebox.showinfo("Succès", f"Container {container_id} supprimé.")
                self.refresh_list()
            except docker.errors.APIError as e:
                messagebox.showerror("Erreur", f"Échec: {e}")

    def open_shell(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        container = self.client.containers.get(container_id)
        if container.status != "running":
            messagebox.showwarning("Attention", "Le container doit être en cours d'exécution.")
            return

        shell = "bash"
        try:
            result = container.exec_run("bash -c 'exit 0'", stdout=False, stderr=True)
            if result.exit_code != 0:
                shell = "sh"
        except docker.errors.APIError:
            shell = "sh"

        try:
            cmd = ["xterm", "-e", f"docker exec -it {container_id} {shell}"]
            subprocess.Popen(cmd)
        except FileNotFoundError:
            messagebox.showerror("Erreur", "xterm non trouvé sur le système.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de l'ouverture du shell: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DockerManagerApp(root)
    root.mainloop()
EOF

# Compiler
pyinstaller --onefile docker-manager.py

# Récupérer l’exécutable
mv dist/docker-manager .
chmod +x docker-manager

# Désactiver l’environnement virtuel
deactivate

echo "Exécutable prêt : ./docker-manager"
echo "Assurez-vous que Docker et xterm sont installés sur la machine cible."
```

1. Sauvegarde dans `build.sh` :
   ```bash
   nano build.sh
   ```
   Copie-colle, sauvegarde.

2. Exécute :
   ```bash
   chmod +x build.sh
   ./build.sh
   ```

### Si tu as une erreur

- **Permission Docker** : Relogue-toi après `usermod` ou utilise `sudo ./docker-manager`.
- **Tkinter manquant** : Rare avec PyInstaller, mais vérifie avec `sudo apt install python3-tk -y`.
- **xterm** : Installe-le si besoin.

Teste `./docker-manager` et dis-moi si ça fonctionne comme attendu (fenêtre fixe, liste des containers, etc.) ! Je ne peux pas te donner l’exécutable directement, mais
ces étapes te donneront exactement ce que tu veux.

# Je veux l'avoir dans le path et créer un raccourci dans la barre lattérale...

Pour mettre ton exécutable `docker-manager` dans le `PATH` et créer un raccourci dans la barre latérale d’Ubuntu (le lanceur, souvent à gauche dans GNOME), voici les
étapes détaillées. Je vais supposer que tu as déjà compilé l’exécutable avec succès en suivant mes instructions précédentes.

### Étape 1 : Mettre l’exécutable dans le PATH

Cela permet de lancer `docker-manager` desde n’importe où dans le terminal sans spécifier son chemin complet.

1. **Déplace l’exécutable dans un dossier du PATH** :
    - Un emplacement courant est `/usr/local/bin`, accessible globalement :
      ```bash
      sudo mv ./docker-manager /usr/local/bin/docker-manager
      ```
    - Vérifie les permissions :
      ```bash
      sudo chmod +x /usr/local/bin/docker-manager
      ```

2. **Teste** :
   ```bash
   docker-manager
   ```
   Si la fenêtre s’ouvre, c’est bon ! Sinon, vérifie que `/usr/local/bin` est dans ton `PATH` :
   ```bash
   echo $PATH
   ```
   Normalement, `/usr/local/bin` y est par défaut sous Ubuntu. Si ce n’est pas le cas, ajoute-le dans `~/.bashrc` :
   ```bash
   echo 'export PATH=$PATH:/usr/local/bin' >> ~/.bashrc
   source ~/.bashrc
   ```

### Étape 2 : Créer un raccourci dans la barre latérale (Lanceur GNOME)

Pour ajouter une icône dans la barre latérale, il faut créer un fichier `.desktop` pour GNOME.

1. **Crée un fichier `.desktop`** :
   ```bash
   nano ~/.local/share/applications/docker-manager.desktop
   ```
   Colle ceci :
   ```desktop
   [Desktop Entry]
   Name=Docker Manager
   Exec=/usr/local/bin/docker-manager
   Type=Application
   Terminal=false
   Icon=docker
   Comment=Gérer les containers Docker
   Categories=Utility;
   ```
    - `Exec` : Chemin vers l’exécutable.
    - `Icon` : Utilise une icône système nommée "docker" (ou spécifie un chemin vers une icône personnalisée, voir plus bas).
    - Sauvegarde (Ctrl+O, Enter, Ctrl+X).

2. **Rends le fichier exécutable** :
   ```bash
   chmod +x ~/.local/share/applications/docker-manager.desktop
   ```

3. **Ajoute au lanceur** :
    - Ouvre le menu des applications (tape "Docker Manager" dans la barre de recherche).
    - Fais un clic droit sur "Docker Manager" dans les résultats, puis sélectionne "Ajouter aux favoris" (ou glisse-le dans la barre latérale).

### Bonus : Icône personnalisée (optionnel)

Si l’icône "docker" ne fonctionne pas ou si tu veux une icône spécifique :

1. **Télécharge une icône** :
   Trouve une icône `.png` (ex. sur le web, comme l’icône officielle Docker) :
   ```bash
   wget https://www.docker.com/wp-content/uploads/2023/03/docker-icon-freigestellt.png -O docker-icon.png
   ```

2. **Déplace l’icône** :
   ```bash
   mkdir -p ~/.local/share/icons
   mv docker-icon.png ~/.local/share/icons/docker.png
   ```

3. **Met à jour le `.desktop`** :
   ```bash
   nano ~/.local/share/applications/docker-manager.desktop
   ```
   Modifie la ligne `Icon` :
   ```desktop
   Icon=/home/$USER/.local/share/icons/docker.png
   ```
   Sauvegarde.

4. **Actualise le cache des icônes** :
   ```bash
   gtk-update-icon-cache ~/.local/share/icons
   ```

### Test final

1. **Lance depuis le terminal** :
   ```bash
   docker-manager
   ```
   La fenêtre devrait s’ouvrir.

2. **Vérifie la barre latérale** :
    - Cherche "Docker Manager" dans le menu des applications.
    - Ajoute-le à la barre latérale si ce n’est pas déjà fait.

### Script pour tout automatiser

Voici un script qui fait tout (supposant que `docker-manager` est déjà compilé dans ton dossier courant) :

```bash
#!/bin/bash

# Mettre dans le PATH
sudo mv ./docker-manager /usr/local/bin/docker-manager
sudo chmod +x /usr/local/bin/docker-manager

# Créer le fichier .desktop
cat << EOF > ~/.local/share/applications/docker-manager.desktop
[Desktop Entry]
Name=Docker Manager
Exec=/usr/local/bin/docker-manager
Type=Application
Terminal=false
Icon=docker
Comment=Gérer les containers Docker
Categories=Utility;
EOF

chmod +x ~/.local/share/applications/docker-manager.desktop

echo "Exécutable ajouté au PATH : /usr/local/bin/docker-manager"
echo "Raccourci créé. Cherchez 'Docker Manager' dans le menu et ajoutez-le à la barre latérale."
echo "Assurez-vous que Docker et xterm sont installés :"
echo "  sudo apt install docker.io xterm -y"
echo "  sudo usermod -aG docker \$USER (puis reloguez-vous)"
```

1. Sauvegarde dans `setup.sh` :
   ```bash
   nano setup.sh
   ```
   Copie-colle, sauvegarde.

2. Exécute :
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

### Résultat

- Tu peux lancer `docker-manager` depuis n’importe quel terminal.
- Une icône "Docker Manager" est dans le menu des applications, et tu peux l’épingler dans la barre latérale.

Si quelque chose ne marche pas (ex. icône absente, exécutable non trouvé), dis-moi, et je t’aiderai à ajuster !
