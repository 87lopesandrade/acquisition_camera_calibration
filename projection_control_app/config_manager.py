import json
import os
import numpy as np

class ConfigManager:
    """
    Gerencia a persistência das configurações do painel de controle.
    """
    
    def __init__(self, save_dir="."):
        self.save_dir = save_dir
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def save_config(self, config_dict, filename="config"):
        """
        Salva o dicionário de configuração em JSON e em NPY.
        
        Args:
            config_dict (dict): Dicionário contendo os parâmetros coletados da GUI.
            filename (str): Nome base do arquivo (sem extensão).
            
        Returns:
            tuple: (Caminho do JSON salvo, Caminho do NPY salvo)
        """
        json_path = os.path.join(self.save_dir, f"{filename}.json")
        npy_path = os.path.join(self.save_dir, f"{filename}.npy")

        # Salvar em JSON
        with open(json_path, 'w') as f:
            json.dump(config_dict, f, indent=4)

        # Salvar em NPY
        # np.save aceita dicionários se setarmos allow_pickle=True ou estruturarmos como array de objetos
        np.save(npy_path, np.array([config_dict]))
        
        return json_path, npy_path

    def load_config(self, filename="config.json"):
        """
        Carrega a configuração a partir de um JSON.
        """
        file_path = os.path.join(self.save_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return {}
