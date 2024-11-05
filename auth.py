from flask import request, Response
from functools import wraps
import hashlib

mongo = None 

def init_mongo(mongo_instance):
    global mongo
    mongo = mongo_instance

def hash_password(password):
    """Gera um hash SHA-256 da senha."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_auth(username, password):
    """Verifica se as credenciais de usuário e senha são válidas."""
    # Verifica se o usuário existe
    user = mongo.db.usuarios.find_one({"usuario": username})
    if not user:
        print("Usuário não encontrado.")
        return False

    # Exibe o hash armazenado e o hash da senha fornecida
    stored_password_hash = user['senha']
    provided_password_hash = hash_password(password)
    print(f"Hash armazenado: {stored_password_hash}")
    print(f"Hash da senha fornecida: {provided_password_hash}")

    # Verifica se os hashes coincidem
    if verify_password(stored_password_hash, password):
        print("Login bem-sucedido!")
        return True
    else:
        print("Senha incorreta.")
        return False

def authenticate():
    """Envia uma resposta que solicita autenticação ao usuário.""" 
    return Response(
        'Acesso negado. Por favor, autentique-se.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """Decorador que protege rotas específicas com autenticação básica.""" 
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Verifica se a senha fornecida corresponde ao hash da senha armazenada
def verify_password(stored_password_hash, provided_password):
    provided_password_hash = hash_password(provided_password)
    return stored_password_hash == provided_password_hash
