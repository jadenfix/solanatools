# config/loaders.py
import yaml

def load_yaml_config(filepath: str) -> dict:
    with open(filepath, "r") as file:
        return yaml.safe_load(file)