import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import openai
import json
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import os
from auth import requires_auth, hash_password, init_mongo, verify_password



# Carregar variáveis de ambiente
load_dotenv()
app = Flask(__name__)

# Configuração do MongoDB
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.secret_key = os.getenv("SECRET_KEY", "vicco")
mongo = PyMongo(app)

# Configuração da API OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("A chave da API OpenAI não está definida. Defina a variável de ambiente 'OPENAI_API_KEY'.")


# Inicialize o mongo no auth.py
init_mongo(mongo)

# Rota para a página principal
@app.route('/')
def home():
    return render_template('index_login.html') , 200

# Rota para a página de cadastro
@app.route('/signin')
def signin():
    return render_template('signin.html') , 200

@app.route('/usuarios', methods=['POST'])
def create_user():
    usuario = request.form.get('usuario')
    senha = request.form.get('senha')
    email = request.form.get('email')

    if not usuario or not senha or not email:
        return jsonify({"error": "Nome, usuário, senha e email são obrigatórios"}), 400

    if mongo.db.usuarios.find_one({"usuario": usuario}):
        return jsonify({"error": "Usuário já existe"}), 409

    if mongo.db.usuarios.find_one({"email": email}):
        return jsonify({"error": "E-mail já cadastrado"}), 409

    hashed_password = hash_password(senha)
    user_data = {"usuario": usuario, "senha": hashed_password, "email": email}
    mongo.db.usuarios.insert_one(user_data)

    return redirect(url_for('success')), 302

# Rota de sucesso
@app.route('/success')
def success():
    return render_template('sucesso.html'), 200 

# Rota para a página de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')  # Mudamos de 'usuario' para 'email'
        senha = request.form.get('senha')
        user = mongo.db.usuarios.find_one({"email": email})  # Buscar pelo e-mail
        if user and verify_password(user['senha'], senha):
            session['user'] = user['usuario']  # Armazena o usuário na sessão
            return redirect(url_for('profile')), 302
        return jsonify({"error": "E-mail ou senha incorretos"}), 401

    return render_template('login.html'), 200


@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove 'username' da sessão
    session.pop('user', None)       # Remove 'user' da sessão
    return redirect(url_for('home')) , 302


# Rota para a página de perfil
@app.route('/profile')
def profile():
    # Verifica se o usuário está autenticado
    if 'user' not in session:
        return redirect(url_for('login')), 302

    return render_template('home_login.html', user=session.get('user')), 200


@app.route('/plano')
def index():
    return render_template('index.html'), 200

@app.route('/historico/<string:_id>', methods=['GET'])
def get_historico(_id):
    user = mongo.db.usuarios.find_one({"_id": ObjectId(_id)})

    if user is None:
        return {"erro": "Usuario não encontrado"}, 404
        
    return render_template('historico.html'), 200

@app.route('/gerar_guia', methods=['POST'])
def gerar_guia():
    # Obter dados do formulário
    try:
        nome = request.form.get('nome')
        orcamento = Decimal(request.form.get('orcamento'))
        descricao_viagem = request.form.get('descricao_viagem')
        dias = request.form.get('dias')
        numero_viajantes = request.form.get('numero_viajantes')
        data_inicio = request.form.get('data_inicio')

        # Verificação de dados obrigatórios
        if not all([nome, orcamento, descricao_viagem, dias, numero_viajantes, data_inicio]):
            return jsonify({"error": "Todos os campos são obrigatórios."}), 400

        # Criar o prompt para a API
        prompt = f"""
        Você é um assistente de viagem especializado em criar planos de viagem completos e personalizados.

        **Informações do usuário:**
        - Nome: {nome}
        - Orçamento total: {orcamento} reais
        - Descrição da viagem: {descricao_viagem}
        - Número de dias planejados: {dias}
        - Número de viajantes: {numero_viajantes}
        - Data de início da viagem: {data_inicio}
        - Local de partida: São Paulo

        **Objetivo do plano de viagem:**
        Desenvolva um plano de viagem completo que seja realista e que caiba no orçamento total de {orcamento} reais. Respeite as preferências descritas e siga as seguintes orientações:

        1. **Estrutura da viagem:**
           - A viagem deve começar na data de início especificada ({data_inicio}).
           - Se nao for necessario ou comum trocar de uma cidade para outra, nao troque
           - As cidades devem ser próximas entre si e combinar com a descrição da viagem.

        2. **Planejamento de hospedagem:**
           - Mantenha a mesma hospedagem na mesma cidade por todos os dias de estadia. Evite trocar de acomodação sem necessidade enquanto o usuário estiver na mesma cidade.
           - Inclua o custo total da hospedagem por noite multiplicado pelo número de viajantes ({numero_viajantes}).

        3. **Planejamento diário:**
           - Para cada dia, forneça um itinerário com:
             - Opção de hospedagem (sem troca de hospedagem durante a estadia na mesma cidade)
             - Transporte (local e entre cidades, se aplicável)
             - Alimentação (custo estimado por dia)
             - Atividades ou atrações que combinem com o estilo de viagem, com breve descrição e custo estimado
           - Ajuste o custo total diário para incluir o número de viajantes ({numero_viajantes}).

        **Formato da resposta:**
        Responda estritamente no formato JSON conforme especificado, sem qualquer texto adicional ou introdução.

        {{
        "plano_viagem": [
            {{
            "dia": X (onde X vai até {dias}),
            "data": "Data específica ou relativa",
            "destino": "Nome do destino",
            "hospedagem": "Nome da hospedagem (mesmo para cada dia na cidade atual) e custo por noite, multiplicado pelo número de viajantes",
            "transporte": "Detalhes do transporte com custo estimado (incluindo passagem no primeiro e último dia, se necessário)",
            "alimentação": "Custo estimado para alimentação",
            "atividades": [
                {{
                "nome": "Nome da atividade",
                "descrição": "Breve descrição",
                "custo": "Custo estimado"
                }}
            ],
            "custo_total_dia": "Custo total estimado para o dia (multiplicado pelo número de viajantes)"
            }}
        ],
        "custo_total_viagem": "Custo total estimado para toda a viagem"
        }}
        """

        # Chamada para a API da OpenAI
        resposta = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[
                {"role": "system", "content": "Você é um assistente de viagem."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.5,
            n=1
        )

        conteudo = resposta.choices[0].message['content'].strip()
        print("Conteúdo da resposta:", conteudo)

        # Extrair JSON da resposta
        json_start = conteudo.find('{')
        json_end = conteudo.rfind('}') + 1
        json_content = conteudo[json_start:json_end]

        try:
            dados_guia = json.loads(json_content, parse_float=Decimal)
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {e}")
            return jsonify({"error": "Erro ao processar o plano de viagem."}), 500

        # Verificação do orçamento
        custo_total_viagem_str = dados_guia.get('custo_total_viagem', '0').replace("R$", "").strip()
        try:
            custo_total_viagem = Decimal(custo_total_viagem_str)
        except InvalidOperation:
            print(f"Erro ao converter custo_total_viagem: '{custo_total_viagem_str}'")
            custo_total_viagem = Decimal(0)

        if custo_total_viagem > orcamento:
            guia = "O plano de viagem excede o orçamento fornecido. Tente novamente com um orçamento maior."
            return jsonify({"message": guia}), 400

        # Salvar plano de viagem no MongoDB
        dados_guia["nome"] = nome
        dados_guia["orcamento"] = str(orcamento)
        dados_guia["data_inicio"] = data_inicio
        mongo.db.planos_de_viagem.insert_one(dados_guia)

        # Retornar sucesso com o guia
        return jsonify({
            "message": "Plano de viagem gerado com sucesso.",
            "dados_guia": dados_guia
        }), 200

    except Exception as e:
        print(f"Erro ao chamar a API da OpenAI: {e}")
        return jsonify({"error": "Erro interno ao gerar o plano de viagem."}), 500


if __name__ == '__main__':
    app.run(debug=True)
