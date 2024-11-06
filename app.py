import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import openai
import json
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from auth import requires_auth, hash_password, init_mongo, verify_password

# Carregar variáveis de ambiente
load_dotenv()
app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.secret_key = os.getenv("SECRET_KEY", "vicco")
mongo = PyMongo(app)

# Configuração da API OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("A chave da API OpenAI não está definida. Defina a variável de ambiente 'OPENAI_API_KEY'.")

# Inicializar o MongoDB
init_mongo(mongo)

@app.route('/')
def home():
    return render_template('index_login.html'), 200

@app.route('/signin')
def signin():
    return render_template('signin.html'), 200

@app.route('/usuarios', methods=['POST'])
def create_user():
    usuario = request.form.get('usuario')
    senha = request.form.get('senha')
    email = request.form.get('email')

    if not usuario or not senha or not email:
        return render_template('signin.html', error="Nome, usuário, senha e email são obrigatórios"), 400

    if mongo.db.usuarios.find_one({"usuario": usuario}):
        return render_template('signin.html', error="Usuário já está sendo usado"), 409

    if mongo.db.usuarios.find_one({"email": email}):
        return render_template('signin.html', error="E-mail já cadastrado"), 409

    hashed_password = hash_password(senha)
    user_data = {"usuario": usuario, "senha": hashed_password, "email": email}
    mongo.db.usuarios.insert_one(user_data)

    return redirect(url_for('success')), 302

@app.route('/success')
def success():
    return render_template('sucesso.html'), 200 

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')  
        senha = request.form.get('senha')
        user = mongo.db.usuarios.find_one({"email": email})  
        if user and verify_password(user['senha'], senha):
            session['user'] = user['usuario']  
            return redirect(url_for('profile')), 302
        
        error = "E-mail ou senha incorretos"

    return render_template('login.html', error=error), 200

@app.route('/logout')
def logout():
    session.pop('username', None)  
    session.pop('user', None)       
    return redirect(url_for('home')), 302

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login')), 302
    return render_template('home_login.html', user=session.get('user')), 200

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = mongo.db.usuarios.find_one({"email": email})

        if user:
            return redirect(url_for('reset_password', email=email))
        else:
            error_message = "E-mail não encontrado. Verifique seu e-mail ou cadastre-se."
            return render_template('forgot_password.html', error_message=error_message)

    return render_template('forgot_password.html')

@app.route('/confirm_email', methods=['POST'])
def confirm_email():
    email = request.form.get('email')
    user = mongo.db.usuarios.find_one({"email": email})

    if user:
        return redirect(url_for('reset_password', email=email))
    else:
        return jsonify({"error": "E-mail não encontrado"}), 404

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')

        if nova_senha != confirmar_senha:
            error_message = "As senhas não coincidem."
            return render_template('reset_password.html', email=email, error_message=error_message)

        nova_senha_hash = hash_password(nova_senha)
        result = mongo.db.usuarios.update_one(
            {"email": email}, 
            {"$set": {"senha": nova_senha_hash}}
        )

        if result.modified_count == 1:
            return redirect(url_for('success_senha'))
        else:
            error_message = "Não foi possível atualizar a senha."
            return render_template('reset_password.html', email=email, error_message=error_message)

    email = request.args.get('email')
    return render_template('reset_password.html', email=email)

@app.route('/success_senha')
def success_senha():
    return render_template('sucesso_senha.html')

@app.route('/plano')
def index():
    return render_template('index.html'), 200

@app.route('/historico')
def historico():
    if 'user' not in session:
        return redirect(url_for('login')), 302
    user = mongo.db.usuarios.find_one({"usuario": session['user']})
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404
    planos = user.get("planos_de_viagem", [])
    return render_template('historico.html', planos=planos), 200

@app.route('/gerar_guia', methods=['POST'])
def gerar_guia():
    if 'user' not in session:
        return redirect(url_for('login')), 302
    user = mongo.db.usuarios.find_one({"usuario": session['user']})
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    try:
        # Obter dados do formulário
        nome = request.form.get('nome')
        orcamento = Decimal(request.form.get('orcamento'))
        descricao_viagem = request.form.get('descricao_viagem')
        dias = request.form.get('dias')
        numero_viajantes = request.form.get('numero_viajantes')
        data_inicio = request.form.get('data_inicio')

        if not all([nome, orcamento, descricao_viagem, dias, numero_viajantes, data_inicio]):
            return jsonify({"error": "Todos os campos são obrigatórios."}), 400

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
            ], (em atividades tente sempre que possivel recomendar algum nao muito generico mas algo que exista de verdade com o nome do local/estabelecimento...)
            "custo_total_dia": "Custo total estimado para o dia (multiplicado pelo número de viajantes)"
            }}
        ], ( no plano de viagem tente usar todo o orcamento, {orcamento}, que o usuario colocou, tudo bem passar um pouco)
        "custo_total_viagem": "Custo total estimado para toda a viagem"
        }}
        """

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
        json_start = conteudo.find('{')
        json_end = conteudo.rfind('}') + 1
        json_content = conteudo[json_start:json_end]

        try:
            dados_guia = json.loads(json_content, parse_float=Decimal)
        except json.JSONDecodeError as e:
            print("Erro de decodificação JSON:", e)
            print("Conteúdo recebido:", conteudo)  # Adicionado para depuração
            return jsonify({"error": "Erro ao processar o plano de viagem."}), 500

        custo_total_viagem_str = dados_guia.get('custo_total_viagem', '0').replace("R$", "").strip()
        try:
            custo_total_viagem = Decimal(custo_total_viagem_str)
        except InvalidOperation:
            custo_total_viagem = Decimal(0)
            print(f"Erro ao converter custo_total_viagem: '{custo_total_viagem_str}'")  # Adicionado para depuração

        if custo_total_viagem > orcamento:
            guia = "O plano de viagem excede o orçamento fornecido. Tente novamente com um orçamento maior."
            return jsonify({"message": guia}), 400

        dados_guia["_id"] = ObjectId()
        dados_guia["nome"] = nome
        dados_guia["orcamento"] = str(orcamento)
        dados_guia["data_inicio"] = data_inicio
        mongo.db.planos_de_viagem.insert_one(dados_guia)
        
        mongo.db.usuarios.update_one(
            {"_id": user['_id']},
            {"$push": {"planos_de_viagem": dados_guia}}
        )

        return render_template('result.html', dados_guia=dados_guia)

    except InvalidOperation:
        return jsonify({"error": "Erro ao processar valores numéricos. Verifique o orçamento ou valores numéricos."}), 400
    except Exception as e:
        print("Erro interno:", e)  # Adicionado para depuração
        return jsonify({"error": "Erro interno ao gerar o plano de viagem."}), 500

@app.route('/meus_roteiros')
def meus_roteiros():
    if 'user' not in session:
        return redirect(url_for('login')), 302
    user = mongo.db.usuarios.find_one({"usuario": session['user']})
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404
    planos = user.get("planos_de_viagem", [])
    return render_template('meus_roteiros.html', planos=planos)

@app.route('/roteiro/<id>')
def roteiro(id):
    if 'user' not in session:
        return redirect(url_for('login')), 302
    user = mongo.db.usuarios.find_one({"usuario": session['user']})
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    planos = user.get("planos_de_viagem", [])
    try:
        roteiro = next((plano for plano in planos if "_id" in plano and str(plano["_id"]) == id), None)
    except KeyError:
        roteiro = None
    
    if not roteiro:
        return jsonify({"error": "Roteiro não encontrado"}), 404

    return render_template('result.html', dados_guia=roteiro)

if __name__ == '__main__':
    app.run(debug=True)
