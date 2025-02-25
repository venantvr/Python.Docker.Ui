#!/usr/bin/env python3

import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import docker


class DockerManagerApp:
    # noinspection PyShadowingNames
    def __init__(self, root):
        self.client = self.get_client()
        self.root = root
        self.root.title("Docker Manager")
        self.root.geometry("600x400")
        self.root.resizable(False, False)  # Interdit le redimensionnement (largeur, hauteur)

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

    # noinspection PyMethodMayBeStatic
    def get_client(self):
        # noinspection PyUnresolvedReferences
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
        # noinspection PyUnresolvedReferences
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
            # noinspection PyUnresolvedReferences
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
        # noinspection PyUnresolvedReferences
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
