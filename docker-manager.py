#!/usr/bin/env python3

import json
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

import docker
from ttkthemes import ThemedTk

logging.basicConfig(filename='docker-manager.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

COMMAND_FILE = "container-commands.json"
LOCK_FILE = "/tmp/docker_manager.lock"  # Fichier de verrouillage pour le singleton


# noinspection PyShadowingNames,PyUnresolvedReferences,PyMethodMayBeStatic,PyTypeChecker,PyUnusedLocal
class DockerManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Docker Manager")
        self.root.geometry("700x500")
        self.root.resizable(False, False)
        self.selected_line = None
        self.edit_popup_open = False  # Variable pour suivre l'état de la popup
        try:
            self.root.iconphoto(True, tk.PhotoImage(file="docker-manager.png"))
        except Exception as e:
            logging.warning(f"Impossible de charger l'icône: {e}")

        self.status_bar = ttk.Label(self.root, text="Prêt", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.client = self.get_client()

        # Ajout de la colonne "Ports" dans le Treeview
        self.tree = ttk.Treeview(self.root, columns=("ID", "Name", "Status", "Ports"), show="headings", height=4, selectmode="browse")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Nom")
        self.tree.heading("Status", text="Statut")
        self.tree.heading("Ports", text="Ports")
        self.tree.column("ID", width=80)
        self.tree.column("Name", width=150)
        self.tree.column("Status", width=70)
        self.tree.column("Ports", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configuration du style pour le Treeview
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
        style.map("Treeview",
                  background=[('selected', '#4a6984')],
                  foreground=[('selected', 'white')])

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=2)

        self.refresh_btn = ttk.Button(btn_frame, text="Actualiser", command=self.refresh_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)
        self.toggle_btn = ttk.Button(btn_frame, text="Démarrer/Arrêter", command=self.toggle_container)
        self.toggle_btn.pack(side=tk.LEFT, padx=2)
        self.delete_btn = ttk.Button(btn_frame, text="Supprimer", command=self.delete_container)
        self.delete_btn.pack(side=tk.LEFT, padx=2)
        self.shell_btn = ttk.Button(btn_frame, text="Ouvrir Shell", command=self.open_shell)
        self.shell_btn.pack(side=tk.LEFT, padx=2)
        self.logs_btn = ttk.Button(btn_frame, text="Logs", command=self.open_logs)
        self.logs_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Quitter", command=self.root.quit)

        self.toggle_btn.config(state=tk.DISABLED)
        self.delete_btn.config(state=tk.DISABLED)
        self.shell_btn.config(state=tk.DISABLED)
        self.logs_btn.config(state=tk.DISABLED)

        # Lier la vérification de sélection et le double-clic
        self.tree.bind('<<TreeviewSelect>>', self.check_selection)
        self.tree.bind('<Double-1>', lambda e: self.open_shell())  # Ajout du double-clic

        self.launch_cmds_text = tk.Text(self.root, height=12, wrap=tk.WORD, cursor="hand2")
        self.launch_cmds_text.pack(fill=tk.X, padx=5, pady=5)
        self.launch_cmds_text.config(state=tk.DISABLED)
        self.launch_cmds_text.tag_configure("highlight", background="lightblue")
        self.launch_cmds_text.bind('<Motion>', self.highlight_line)
        self.launch_cmds_text.bind('<Leave>', self.clear_highlight)
        # self.launch_cmds_text.bind('<Button-1>', self.launch_container_from_cmd)
        self.launch_cmds_text.bind('<Double-1>', self.launch_container_from_cmd)

        # Ajout du menu contextuel (clic droit)
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.launch_cmds_text.bind('<Button-3>', self.show_context_menu)  # Clic droit sur la liste

        # Binding global pour supprimer "Modifier" avec un clic gauche n'importe où
        self.root.bind('<Button-1>', self.remove_modify_option)

        self.launch_cmds_text.tag_configure("even", background="#F4CFDF")
        self.launch_cmds_text.tag_configure("odd", background="#B6D8F2")

        self.root.bind('<F5>', lambda e: self.refresh_list())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

        self.commands = self.load_commands()
        self.refresh_list()
        self.update_commands_text()

    def check_selection(self, event):
        selected = self.tree.selection()
        state = tk.NORMAL if selected else tk.DISABLED
        self.toggle_btn.config(state=state)
        self.delete_btn.config(state=state)
        self.shell_btn.config(state=state)
        self.logs_btn.config(state=state)

    def load_commands(self):
        try:
            if os.path.exists(COMMAND_FILE):
                with open(COMMAND_FILE, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Erreur lors du chargement des commandes: {e}")
            return {}

    def save_commands(self):
        try:
            reversed_dict = {}
            for cid, cmd in self.commands.items():
                reversed_dict[cmd] = cid
            deduplicated_commands = {cid: cmd for cmd, cid in reversed_dict.items()}
            with open(COMMAND_FILE, 'w') as f:
                json.dump(deduplicated_commands, f, indent=2)
            self.update_commands_text()
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des commandes: {e}")

    def update_commands_text(self):
        cmd_dict = {}
        for key, cmd in self.commands.items():
            cmd_dict[cmd] = key

        self.launch_cmds_text.config(state=tk.NORMAL)
        self.launch_cmds_text.delete(1.0, tk.END)
        for i, (cmd, key) in enumerate(cmd_dict.items()):
            line = f"{key}: {cmd}\n"
            tag = "even" if i % 2 == 0 else "odd"
            self.launch_cmds_text.insert(tk.END, line, tag)
        self.launch_cmds_text.config(state=tk.DISABLED)

    def highlight_line(self, event):
        self.launch_cmds_text.tag_remove("highlight", "1.0", tk.END)
        line_num = self.launch_cmds_text.index("@%d,%d" % (event.x, event.y)).split('.')[0]
        start = f"{line_num}.0"
        end = f"{line_num}.end"
        self.launch_cmds_text.tag_add("highlight", start, end)

    def clear_highlight(self, event):
        self.launch_cmds_text.tag_remove("highlight", "1.0", tk.END)

    def show_context_menu(self, event):
        """Affiche le menu contextuel au clic droit sur la liste et réinitialise 'Modifier' si nécessaire"""
        line_num = self.launch_cmds_text.index("@%d,%d" % (event.x, event.y)).split('.')[0]
        self.selected_line = line_num  # Stocker la ligne sélectionnée

        # Vérifie si "Modifier" existe, sinon le recrée
        try:
            self.context_menu.entrycget("Modifier", "label")  # Teste si "Modifier" existe
        except tk.TclError:
            self.context_menu.delete(0, tk.END)  # Nettoie le menu
            self.context_menu.add_command(label="Modifier", command=self.edit_command)  # Recrée "Modifier"

        self.context_menu.post(event.x_root, event.y_root)

    def remove_modify_option(self, event):
        """Supprime l'option 'Modifier' du menu contextuel après un clic gauche, sauf si la popup est ouverte"""
        if not self.edit_popup_open:  # Ne supprime que si la popup n'est pas active
            try:
                self.context_menu.delete("Modifier")
            except tk.TclError:
                pass  # Ignore si "Modifier" n'existe pas déjà dans le menu

    def create_edit_popup(self, title, prompt, initialvalue, cid):
        self.edit_popup_open = True  # Marque la popup comme ouverte
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("600x300")  # Plus grande pour accueillir les améliorations
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        # Assure que la popup se ferme correctement et met à jour l'état
        popup.protocol("WM_DELETE_WINDOW", lambda: self.on_popup_close(popup))

        # Style personnalisé
        style = ttk.Style()
        style.configure("Popup.TFrame", relief="flat", borderwidth=0)
        style.configure("Popup.TLabel", font=('Helvetica', 12, 'bold'))

        # Frame principal
        frame = ttk.Frame(popup, style="Popup.TFrame", padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        # Titre
        ttk.Label(frame, text=prompt, style="Popup.TLabel").pack(anchor=tk.W, pady=(0, 10))

        # Zone de texte multiligne
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        entry = tk.Text(text_frame, height=5, width=80, font=('Helvetica', 11), wrap=tk.WORD, relief="flat", borderwidth=1)
        entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        entry.insert("1.0", initialvalue)
        entry.focus_set()

        # Indicateur de longueur
        char_count = tk.StringVar(value=f"Caractères : {len(initialvalue)}")
        ttk.Label(frame, textvariable=char_count, font=('Helvetica', 9)).pack(anchor=tk.W, pady=(0, 10))

        # Mise à jour dynamique du compteur de caractères
        def update_char_count(*args):
            char_count.set(f"Caractères : {len(entry.get('1.0', tk.END)) - 1}")  # -1 pour retirer le '\n' final

        entry.bind('<KeyRelease>', update_char_count)

        # Boutons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=2)

        ttk.Button(btn_frame, text="Valider", command=lambda: self.save_popup_command(popup, entry, cid)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Copier", command=lambda: self.root.clipboard_append(entry.get("1.0", tk.END).strip())).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Annuler", command=lambda: self.on_popup_close(popup)).pack(side=tk.LEFT, padx=5)

        return popup

    def save_popup_command(self, popup, entry, cid):
        new_cmd = entry.get("1.0", tk.END).strip()
        if new_cmd and new_cmd != self.commands.get(cid, ""):
            self.commands[cid] = new_cmd
            self.save_commands()
            self.status_bar.config(text=f"Commande pour {cid} mise à jour")
            logging.info(f"Commande mise à jour pour {cid}: {new_cmd}")
        self.on_popup_close(popup)

    def on_popup_close(self, popup):
        """Ferme la popup et met à jour l'état"""
        self.edit_popup_open = False
        popup.destroy()

    def edit_command(self):
        """Modifie la commande sélectionnée et sauvegarde"""
        if not hasattr(self, 'selected_line'):
            return

        line_num = self.selected_line
        line = self.launch_cmds_text.get(f"{line_num}.0", f"{line_num}.end").strip()
        if not line:
            return

        try:
            cid, current_cmd = line.split(":", 1)
            cid = cid.strip()
            current_cmd = current_cmd.strip()

            # Nouvelle popup personnalisée
            self.create_edit_popup("Modifier Commande", "Entrez la nouvelle commande:", current_cmd, cid)
        except ValueError:
            self.status_bar.config(text="Erreur: Ligne mal formée")
            logging.error(f"Ligne mal formée: {line}")

    def launch_container_from_cmd(self, event):
        line_num = self.launch_cmds_text.index("@%d,%d" % (event.x, event.y)).split('.')[0]
        line = self.launch_cmds_text.get(f"{line_num}.0", f"{line_num}.end").strip()
        if line:
            try:
                cmd = line.split(":", 1)[1].strip()
                cmd_parts = cmd.split()
                container_name = None
                for i, part in enumerate(cmd_parts):
                    if part == "--name" and i + 1 < len(cmd_parts):
                        container_name = cmd_parts[i + 1]
                        break

                if container_name:
                    try:
                        existing_container = self.client.containers.get(container_name)
                        logging.info(f"Conteneur existant '{container_name}' trouvé, suppression en cours...")
                        existing_container.remove(force=True)
                        self.status_bar.config(text=f"Conteneur existant {container_name} supprimé avant relance")
                    except docker.errors.NotFound:
                        pass

                subprocess.Popen(cmd, shell=True)
                self.status_bar.config(text=f"Lancement de: {cmd}")
                logging.info(f"Lancement de la commande: {cmd}")
                self.root.after(1000, self.refresh_list)
            except IndexError:
                self.status_bar.config(text="Erreur: Commande mal formée")
                logging.error(f"Commande mal formée: {line}")
            except docker.errors.APIError as e:
                self.status_bar.config(text=f"Erreur API Docker: {e}")
                logging.error(f"Erreur API lors du lancement: {e}")
            except Exception as e:
                self.status_bar.config(text=f"Erreur de lancement: {e}")
                logging.error(f"Erreur lors du lancement: {e}")

    def get_client(self):
        try:
            client = docker.from_env()
            self.status_bar.config(text="Connexion à Docker réussie")
            logging.info("Connected to Docker")
            return client
        except docker.errors.DockerException as e:
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Docker connection failed: {e}")
            sys.exit(1)

    def refresh_list(self):
        self.status_bar.config(text="Chargement...")
        self.root.update()

        def refresh_in_background():
            containers = sorted(self.client.containers.list(all=True), key=lambda c: c.name)
            port_data = []
            for container in containers:
                status = "Running" if container.status == "running" else "Stopped"
                ports = container.attrs.get('NetworkSettings', {}).get('Ports', {})
                port_list = []
                for container_port, host_bindings in ports.items():
                    if host_bindings:
                        for binding in host_bindings:
                            host_port = binding.get('HostPort', '')
                            if host_port:
                                port_list.append(f"{host_port}->{container_port}")
                ports_str = ", ".join(port_list) if port_list else "N/A"
                port_data.append((container.short_id, container.name, status, ports_str, status == "Running"))
                if container.short_id not in self.commands:
                    cmd = self.get_container_command(container)
                    if cmd:
                        self.commands[container.short_id] = cmd
                        self.save_commands()

            self.root.after(0, lambda: self.__update_tree(port_data))

        threading.Thread(target=refresh_in_background, daemon=True).start()

    def __update_tree(self, port_data):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for short_id, name, status, ports_str, is_running in port_data:
            item = self.tree.insert("", tk.END, values=(short_id, name, status, ports_str))
            self.tree.item(item, tags=('running' if is_running else 'stopped',))
        self.tree.tag_configure('running', foreground='green')
        self.tree.tag_configure('stopped', foreground='red')
        self.status_bar.config(text="Liste actualisée")
        logging.info("Container list refreshed")

    def get_container_command(self, container):
        try:
            container_info = self.client.api.inspect_container(container.id)
            config = container_info.get('Config', {})
            host_config = container_info.get('HostConfig', {})
            network_settings = container_info.get('NetworkSettings', {})
            name = container_info.get('Name', '').lstrip('/')
            image = config.get('Image', '')
            cmd = config.get('Cmd', [])

            command_parts = ["docker", "run"]
            if host_config.get('AutoRemove', False):
                command_parts.append("--rm")
            if name:
                command_parts.append(f"--name {name}")
            ports = network_settings.get('Ports', {}) or host_config.get('PortBindings', {})
            for container_port, host_bindings in ports.items():
                if host_bindings:
                    for binding in host_bindings:
                        host_ip = binding.get('HostIp', '')
                        host_port = binding.get('HostPort', '')
                        port_proto = container_port.split('/')
                        container_port_num = port_proto[0]
                        if host_ip and host_port:
                            port_mapping = f"{host_ip}:{host_port}:{container_port_num}"
                        elif host_port:
                            port_mapping = f"{host_port}:{container_port_num}"
                        else:
                            port_mapping = container_port_num
                        command_parts.append(f"-p {port_mapping}")
            mounts = host_config.get('Binds', []) or []
            for mount in mounts:
                if mount:
                    command_parts.append(f"-v {mount}")
            networks = network_settings.get('Networks', {})
            for network_name in networks.keys():
                if network_name != "bridge":
                    command_parts.append(f"--network {network_name}")
            command_parts.append(image)
            if cmd:
                command_parts.append(" ".join(cmd))
            return " ".join(command_parts).strip()
        except Exception as e:
            logging.error(f"Erreur lors de la récupération de la commande pour {container.short_id}: {e}")
            return None

    def get_selected_container(self):
        selected = self.tree.selection()
        if not selected:
            self.status_bar.config(text="Aucun container sélectionné")
            return None
        item = self.tree.item(selected[0])
        return item["values"][0]

    def toggle_container(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        try:
            container = self.client.containers.get(container_id)
            if container.status == "running":
                container.stop()
                self.status_bar.config(text=f"Container {container_id} arrêté")
                logging.info(f"Stopped container {container_id}")
            else:
                container.start()
                self.status_bar.config(text=f"Container {container_id} démarré")
                logging.info(f"Started container {container_id}")
            self.refresh_list()
        except docker.errors.NotFound:
            self.status_bar.config(text=f"Container {container_id} introuvable")
            logging.warning(f"Container {container_id} not found")
            self.refresh_list()
        except docker.errors.APIError as e:
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to toggle container {container_id}: {e}")

    def delete_container(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            self.status_bar.config(text=f"Container {container_id} supprimé")
            logging.info(f"Deleted container {container_id}")
            self.refresh_list()
        except docker.errors.NotFound:
            self.status_bar.config(text=f"Container {container_id} introuvable")
            logging.warning(f"Container {container_id} not found")
            self.refresh_list()
        except docker.errors.APIError as e:
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to delete container {container_id}: {e}")

    def open_shell(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        try:
            container = self.client.containers.get(container_id)
            if container.status != "running":
                self.status_bar.config(text="Container non démarré")
                return
            shells = ["bash", "sh"]
            shell = None
            for s in shells:
                try:
                    result = container.exec_run(f"{s} -c 'exit 0'", stdout=False, stderr=True)
                    if result.exit_code == 0:
                        shell = s
                        break
                except docker.errors.APIError:
                    continue
            if not shell:
                self.status_bar.config(text="Aucun shell trouvé")
                logging.error(f"No shell available in container {container_id}")
                return
            cmd = ["xterm", "-e", f"docker exec -it {container_id} {shell}"]
            subprocess.Popen(cmd)
            self.status_bar.config(text=f"Shell ({shell}) ouvert pour {container_id}")
            logging.info(f"Opened {shell} in container {container_id}")
        except docker.errors.NotFound:
            self.status_bar.config(text=f"Container {container_id} introuvable")
            logging.warning(f"Container {container_id} not found")
            self.refresh_list()
        except FileNotFoundError:
            self.status_bar.config(text="xterm non trouvé")
            logging.error("xterm not found")
        except Exception as e:
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to open shell in {container_id}: {e}")

    def open_logs(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=1000).decode('utf-8')
            cmd = ["xterm", "-e", f"docker logs --follow {container_id}"]
            subprocess.Popen(cmd)
            self.status_bar.config(text=f"Logs ouverts pour {container_id}")
            logging.info(f"Opened logs for container {container_id}")
        except docker.errors.NotFound:
            self.status_bar.config(text=f"Container {container_id} introuvable")
            logging.warning(f"Container {container_id} not found")
            self.refresh_list()
        except FileNotFoundError:
            self.status_bar.config(text="xterm non trouvé")
            logging.error("xterm not found")
        except Exception as e:
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to open logs for {container_id}: {e}")


if __name__ == "__main__":
    # Vérification du singleton
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            # Vérifier si le processus existe encore
            if os.path.exists(f"/proc/{pid}"):
                # Ramener la fenêtre au premier plan en cherchant par titre
                subprocess.run(["xdotool", "search", "--name", "Docker Manager", "windowactivate"])
                sys.exit(0)
            else:
                os.remove(LOCK_FILE)  # Nettoyer si le processus n'existe plus
        except (ValueError, IOError):
            os.remove(LOCK_FILE)  # Nettoyer si le fichier est corrompu

    # Créer le fichier de verrouillage avec le PID actuel
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

    try:
        root = ThemedTk(theme="ubuntu")
        app = DockerManagerApp(root)
        root.mainloop()
    finally:
        # Supprimer le fichier de verrouillage à la fermeture
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
