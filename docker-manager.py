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

logging.basicConfig(filename='docker-manager.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

COMMAND_FILE = "container-commands.json"


# noinspection PyShadowingNames,PyUnresolvedReferences,PyMethodMayBeStatic,PyTypeChecker,PyUnusedLocal
class DockerManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Docker Manager")
        self.root.geometry("700x500")
        self.root.resizable(False, False)
        try:
            self.root.iconphoto(True, tk.PhotoImage(file="docker-manager.png"))
        except Exception as e:
            logging.warning(f"Impossible de charger l'icône: {e}")

        self.status_bar = tk.Label(self.root, text="Prêt", bd=1, relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 10))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.client = self.get_client()

        # Ajout de la colonne "Ports" dans le Treeview
        self.tree = ttk.Treeview(self.root, columns=("ID", "Name", "Status", "Ports"), show="headings", height=4)
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Nom")
        self.tree.heading("Status", text="Statut")
        self.tree.heading("Ports", text="Ports")
        self.tree.column("ID", width=80)
        self.tree.column("Name", width=150)
        self.tree.column("Status", width=70)
        self.tree.column("Ports", width=150)  # Largeur pour la nouvelle colonne
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10))

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=2)

        tk.Button(btn_frame, text="Actualiser", command=self.refresh_list, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Démarrer/Arrêter", command=self.toggle_container, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Supprimer", command=self.delete_container, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Ouvrir Shell", command=self.open_shell, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Logs", command=self.open_logs, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)  # Nouveau bouton
        tk.Button(btn_frame, text="Quitter", command=self.root.quit, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)

        # Liste cliquable pour lancer (lecture seule, avec survol)
        self.launch_cmds_text = tk.Text(self.root, height=12, font=("Arial", 10), wrap=tk.WORD, cursor="hand2")
        self.launch_cmds_text.pack(fill=tk.X, padx=5, pady=5)
        self.launch_cmds_text.config(state=tk.DISABLED)
        self.launch_cmds_text.tag_configure("highlight", background="lightblue")
        self.launch_cmds_text.bind('<Motion>', self.highlight_line)
        self.launch_cmds_text.bind('<Leave>', self.clear_highlight)
        self.launch_cmds_text.bind('<Button-1>', self.launch_container_from_cmd)

        # Ajout des tags pour alternance pair/impair
        self.launch_cmds_text.tag_configure("even", background="#F4CFDF")  # Gris clair pour lignes paires
        self.launch_cmds_text.tag_configure("odd", background="#B6D8F2")  # Blanc pour lignes impaires

        self.root.bind('<F5>', lambda e: self.refresh_list())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

        self.commands = self.load_commands()
        self.refresh_list()
        self.update_commands_text()

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
            # Inverser le dictionnaire : commandes comme clés, IDs comme valeurs
            # Cela écrase automatiquement les anciennes clés par les nouvelles (dernier vu gagne)
            reversed_dict = {}
            for cid, cmd in self.commands.items():
                reversed_dict[cmd] = cid

            # Revenir au format original : IDs comme clés, commandes comme valeurs
            deduplicated_commands = {cid: cmd for cmd, cid in reversed_dict.items()}

            # Sauvegarder le dictionnaire dédoublonné
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
            tag = "even" if i % 2 == 0 else "odd"  # Pair ou impair
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

    def launch_container_from_cmd(self, event):
        line_num = self.launch_cmds_text.index("@%d,%d" % (event.x, event.y)).split('.')[0]
        line = self.launch_cmds_text.get(f"{line_num}.0", f"{line_num}.end").strip()
        if line:
            try:
                cmd = line.split(":", 1)[1].strip()
                # Extraire le nom du conteneur s'il existe dans la commande
                cmd_parts = cmd.split()
                container_name = None
                for i, part in enumerate(cmd_parts):
                    if part == "--name" and i + 1 < len(cmd_parts):
                        container_name = cmd_parts[i + 1]
                        break

                # Si un nom est spécifié, vérifier et supprimer un conteneur existant avec ce nom
                if container_name:
                    try:
                        existing_container = self.client.containers.get(container_name)
                        logging.info(f"Conteneur existant '{container_name}' trouvé, suppression en cours...")
                        existing_container.remove(force=True)
                        self.status_bar.config(text=f"Conteneur existant {container_name} supprimé avant relance")
                    except docker.errors.NotFound:
                        pass  # Le conteneur n'existe pas, on peut continuer

                # Lancer la commande
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

            # Mise à jour de l'interface dans le thread principal
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

            # Récupérer les logs initiaux
            logs = container.logs(tail=1000).decode('utf-8')  # 100 dernières lignes

            # Lancer docker logs --follow dans un terminal externe (xterm)
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
    root = tk.Tk()
    app = DockerManagerApp(root)
    root.mainloop()
