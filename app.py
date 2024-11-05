import os
from flask import Flask, render_template, request
import openai
import json
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from flask_pymongo import PyMongo

# Carregar variáveis de ambiente
load_dotenv()
app = Flask(__name__)

# Configuração do MongoDB
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# Configuração da API OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("A chave da API OpenAI não está definida. Defina a variável de ambiente 'OPENAI_API_KEY'.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gerar_guia', methods=['POST'])
def gerar_guia():
    # Obter dados do formulário
    nome = request.form.get('nome')
    orcamento = Decimal(request.form.get('orcamento'))
    descricao_viagem = request.form.get('descricao_viagem')
    dias = request.form.get('dias')
    numero_viajantes = request.form.get('numero_viajantes')
    data_inicio = request.form.get('data_inicio')

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
       - Cada cidade deve ter um mínimo de 5 dias de estadia antes de sugerir uma mudança para outra cidade. Apenas sugira uma nova cidade após 5 dias no mesmo destino.
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
    Responda estritamente no formato JSON conforme especificado, sem qualquer texto adicional ou introdução

    {{
    "plano_viagem": [
        {{
        "dia": X (onde X vai até {dias}),
        "data": "Data específica ou relativa",
        "destino": "Nome do destino",
        "hospedagem": "Nome da hospedagem (mesmo para cada dia na cidade atual) e custo por noite, multiplicado pelo número de viajantes",
        "transporte": "Detalhes do transporte com custo estimado",
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

    try:
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

        # Extrair apenas o JSON da resposta
        json_start = conteudo.find('{')
        json_end = conteudo.rfind('}') + 1
        json_content = conteudo[json_start:json_end]

        dados_guia = json.loads(json_content, parse_float=Decimal)

        # Limpar e converter custo_total_viagem
        custo_total_viagem_str = dados_guia.get('custo_total_viagem', '0').replace("R$", "").strip()
        try:
            custo_total_viagem = Decimal(custo_total_viagem_str)
        except InvalidOperation:
            print(f"Erro ao converter custo_total_viagem: '{custo_total_viagem_str}'")
            custo_total_viagem = Decimal(0)

        # Verificar orçamento
        if custo_total_viagem > orcamento:
            guia = "Desculpe, o plano de viagem excede o seu orçamento. Por favor, tente novamente com um orçamento maior."
            dados_guia = None
        else:
            guia = None
            # Salvar o plano de viagem no MongoDB
            dados_guia["nome"] = nome
            dados_guia["orcamento"] = str(orcamento)
            dados_guia["data_inicio"] = data_inicio
            mongo.db.planos_de_viagem.insert_one(dados_guia)

    except json.JSONDecodeError as e:
        guia = "Desculpe, ocorreu um erro ao processar o plano de viagem. Por favor, tente novamente mais tarde."
        print(f"Erro ao decodificar JSON: {e}")
        dados_guia = None
    except Exception as e:
        guia = "Desculpe, ocorreu um erro ao gerar o plano de viagem. Por favor, tente novamente mais tarde."
        print(f"Erro ao chamar a API da OpenAI: {e}")
        dados_guia = None

    return render_template('result.html', nome=nome, dados_guia=dados_guia, guia=guia)

if __name__ == '__main__':
    app.run(debug=True)
