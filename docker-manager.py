#!/usr/bin/env python3

import logging
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

import docker

logging.basicConfig(filename='docker-manager.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class DockerManagerApp:
    # noinspection PyShadowingNames
    def __init__(self, root):
        self.root = root
        self.root.title("Docker Manager")
        self.root.geometry("500x200")
        self.root.resizable(False, False)
        try:
            self.root.iconphoto(True, tk.PhotoImage(file="docker-manager.png"))
        except Exception as e:
            logging.warning(f"Impossible de charger l'icône: {e}")

        # Barre de statut avec police 8
        self.status_bar = tk.Label(self.root, text="Prêt", bd=1, relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 8))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Initialiser le client
        self.client = self.get_client()

        # Treeview avec police 8 pour les en-têtes
        self.tree = ttk.Treeview(self.root, columns=("ID", "Name", "Status"), show="headings", height=6)
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Nom")
        self.tree.heading("Status", text="Statut")
        self.tree.column("ID", width=80)
        self.tree.column("Name", width=150)
        self.tree.column("Status", width=70)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Appliquer une police globale au Treeview via un style
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 8))
        style.configure("Treeview.Heading", font=("Arial", 8))

        # Cadre des boutons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=2)

        # Boutons avec police 8
        tk.Button(btn_frame, text="Actualiser", command=self.refresh_list, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Démarrer/Arrêter", command=self.toggle_container, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Supprimer", command=self.delete_container, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Ouvrir Shell", command=self.open_shell, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Quitter", command=self.root.quit, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)

        self.root.bind('<F5>', lambda e: self.refresh_list())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

        self.refresh_list()

    def get_client(self):
        # noinspection PyUnresolvedReferences
        try:
            client = docker.from_env()
            self.status_bar.config(text="Connexion à Docker réussie")
            logging.info("Connected to Docker")
            return client
        except docker.errors.DockerException as e:
            self.status_bar.config(text=f"Erreur: {e}")
            # messagebox.showerror("Erreur", f"Connexion à Docker échouée: {e}")
            logging.error(f"Docker connection failed: {e}")
            sys.exit(1)

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        containers = sorted(self.client.containers.list(all=True), key=lambda c: c.name)
        for container in containers:
            status = "Running" if container.status == "running" else "Stopped"
            item = self.tree.insert("", tk.END, values=(container.short_id, container.name, status))
            if status == "Running":
                self.tree.item(item, tags=('running',))
            else:
                self.tree.item(item, tags=('stopped',))
        self.tree.tag_configure('running', foreground='green')
        self.tree.tag_configure('stopped', foreground='red')
        self.status_bar.config(text="Liste actualisée")
        logging.info("Container list refreshed")

    def get_selected_container(self):
        selected = self.tree.selection()
        if not selected:
            # messagebox.showwarning("Attention", "Veuillez sélectionner un container.")
            self.status_bar.config(text="Aucun container sélectionné")
            return None
        item = self.tree.item(selected[0])
        return item["values"][0]

    def toggle_container(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        container = self.client.containers.get(container_id)
        # noinspection PyUnresolvedReferences
        try:
            if container.status == "running":
                container.stop()
                # messagebox.showinfo("Succès", f"Container {container_id} arrêté.")
                self.status_bar.config(text=f"Container {container_id} arrêté")
                logging.info(f"Stopped container {container_id}")
            else:
                container.start()
                # messagebox.showinfo("Succès", f"Container {container_id} démarré.")
                self.status_bar.config(text=f"Container {container_id} démarré")
                logging.info(f"Started container {container_id}")
            self.refresh_list()
        except docker.errors.APIError as e:
            # messagebox.showerror("Erreur", f"Échec de l'opération: {e}")
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to toggle container {container_id}: {e}")

    def delete_container(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        # if messagebox.askyesno("Confirmer", f"Supprimer le container {container_id} ?"):
        # noinspection PyUnresolvedReferences
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            # messagebox.showinfo("Succès", f"Container {container_id} supprimé.")
            self.status_bar.config(text=f"Container {container_id} supprimé")
            logging.info(f"Deleted container {container_id}")
            self.refresh_list()
        except docker.errors.APIError as e:
            # messagebox.showerror("Erreur", f"Échec de la suppression: {e}")
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to delete container {container_id}: {e}")

    def open_shell(self):
        container_id = self.get_selected_container()
        if not container_id:
            return
        container = self.client.containers.get(container_id)
        if container.status != "running":
            # messagebox.showwarning("Attention", "Le container doit être en cours d'exécution.")
            self.status_bar.config(text="Container non démarré")
            return

        shells = ["bash", "sh"]
        shell = None
        for s in shells:
            # noinspection PyUnresolvedReferences
            try:
                result = container.exec_run(f"{s} -c 'exit 0'", stdout=False, stderr=True)
                if result.exit_code == 0:
                    shell = s
                    break
            except docker.errors.APIError:
                continue

        if not shell:
            # messagebox.showerror("Erreur", "Aucun shell disponible (bash/sh) dans ce container.")
            self.status_bar.config(text="Aucun shell trouvé")
            logging.error(f"No shell available in container {container_id}")
            return

        try:
            cmd = ["xterm", "-e", f"docker exec -it {container_id} {shell}"]
            subprocess.Popen(cmd)
            self.status_bar.config(text=f"Shell ({shell}) ouvert pour {container_id}")
            logging.info(f"Opened {shell} in container {container_id}")
        except FileNotFoundError:
            # messagebox.showerror("Erreur", "xterm non trouvé sur le système.")
            self.status_bar.config(text="xterm non trouvé")
            logging.error("xterm not found")
        except Exception as e:
            # messagebox.showerror("Erreur", f"Échec de l'ouverture du shell: {e}")
            self.status_bar.config(text=f"Erreur: {e}")
            logging.error(f"Failed to open shell in {container_id}: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = DockerManagerApp(root)
    root.mainloop()
