import os
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import subprocess
import time

# --- Partie 1 : Authentification et accès à Google Drive ---
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate_google_drive():
    """Authentifie l'utilisateur et retourne un service Google Drive."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("L'authentification a échoué, veuillez vous reconnecter.")
                exit()
        else:
            print("Aucune connexion valide. Veuillez vous connecter.")
            exit()
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def list_files_in_drive(service):
    """Liste les fichiers disponibles dans Google Drive."""
    results = service.files().list(fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    if not items:
        print("Aucun fichier trouvé dans Google Drive.")
        return []
    print("\nFichiers disponibles dans Google Drive :")
    for i, item in enumerate(items):
        print(f"{i + 1}. {item['name']} (ID: {item['id']}) - Type: {item['mimeType']}")
    return items

def download_file(service, file_id, file_name, local_folder):
    """Télécharge un fichier spécifique depuis Google Drive."""
    os.makedirs(local_folder, exist_ok=True)
    local_path = os.path.join(local_folder, file_name)
    request = service.files().get_media(fileId=file_id)
    with open(local_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Téléchargement de {file_name} : {int(status.progress() * 100)}% terminé.")
    return local_path

# --- Partie 2 : Lecture des fichiers texte ---
def read_text_file(file_path):
    """Lit le contenu d'un fichier texte."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.strip():  # Vérifie si le fichier contient du texte
                return content
            else:
                print(f"Le fichier {file_path} ne contient pas de texte valide.")
                return None
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier {file_path} : {e}")
        return None

# --- Partie 3 : Interaction avec Ollama ---
def interact_with_ollama(text, user_question):
    """Envoie le texte à Ollama via la commande 'run' et récupère la réponse."""
    try:
        full_text = f"Texte : {text}\nQuestion : {user_question}"
        
        print("Envoi de la question à Ollama...")
        start_time = time.time()  # Enregistre l'heure de début
        result = subprocess.run(
            ['ollama', 'run', 'llama2', full_text],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Utilisation de text=True pour éviter les problèmes de décodage
            timeout=300,  # Délai d'attente plus long pour éviter les timeouts
            encoding='utf-8'  # Forcer l'encodage UTF-8 pour éviter les erreurs de décodage
        )
        end_time = time.time()  # Enregistre l'heure de fin
        print(f"Temps de réponse d'Ollama : {end_time - start_time:.2f} secondes")

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Erreur lors de l'interaction avec Ollama : {result.stderr.strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("Le délai d'attente pour l'interaction avec Ollama a expiré.")
        return None
    except Exception as e:
        print(f"Erreur lors de l'interaction avec Ollama : {e}")
        return None

# --- Main : Choix et traitement des fichiers ---
if __name__ == '__main__':
    # Authentification et accès à Google Drive
    service = authenticate_google_drive()
    
    # Liste les fichiers disponibles
    files = list_files_in_drive(service)
    if not files:
        exit()
    
    # Demande à l'utilisateur de choisir un fichier texte
    file_index = int(input("\nEntrez le numéro du fichier texte à télécharger : ")) - 1
    if file_index < 0 or file_index >= len(files):
        print("Numéro de fichier invalide.")
        exit()
    
    selected_file = files[file_index]
    file_id = selected_file['id']
    file_name = selected_file['name']
    
    # Télécharge le fichier sélectionné
    print(f"Téléchargement du fichier : {file_name}")
    local_folder = "documents_google_drive"
    local_path = download_file(service, file_id, file_name, local_folder)
    
    # Vérifie si le fichier est un fichier texte (type MIME "text/plain")
    if selected_file['mimeType'] == 'text/plain':
        content = read_text_file(local_path)
        if content:
            print("\nContenu extrait du fichier texte :")
            print(content[:500])  # Affiche les 500 premiers caractères
            print("\n")
            
            # Interaction avec Ollama
            while True:
                user_question = input("\nPosez votre question (ou tapez 'exit' pour quitter) : ")
                if user_question.lower() == 'exit':
                    print("Au revoir !")
                    break
                
                # Diviser le texte en parties plus petites pour éviter de surcharger Ollama
                max_length = 500  # Limiter la longueur des morceaux de texte envoyés à Ollama
                text_parts = [content[i:i+max_length] for i in range(0, len(content), max_length)]
                
                responses = []
                for part in text_parts:
                    ollama_response = interact_with_ollama(part, user_question)
                    if ollama_response:
                        responses.append(ollama_response)

                # Combiner toutes les réponses et les afficher
                if responses:
                    final_response = " ".join(responses)
                    print("\nRéponse d'Ollama :")
                    print(final_response)
                else:
                    print("Aucune réponse reçue d'Ollama.")
        else:
            print(f"Le fichier {file_name} ne contient pas de texte valide.")
    else:
        print(f"Le fichier {file_name} n'est pas un fichier texte.")
