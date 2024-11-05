import os
from flask import Flask, render_template, request
import openai
import json
from decimal import Decimal
from dotenv import load_dotenv
from flask_pymongo import PyMongo
from bson.objectid import ObjectId


load_dotenv('.cred')
app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# Configuração da API OpenAI
# openai.api_key = os.getenv('OPENAI_API_KEY')

# if not openai.api_key:
#     raise ValueError("A chave da API OpenAI não está definida. Defina a variável de ambiente 'OPENAI_API_KEY'.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/historico/<string:_id>', methods=['GET'])
def get_historico(_id):
    user = mongo.db.usuarios.find_one({"_id": ObjectId(_id)})

    if user is None:
        return {"erro": "Usuario não encontrado"}, 404
        
    return render_template('historico.html'), 200


@app.route('/gerar_guia', methods=['POST'])
def gerar_guia():
    dados_formulario = {
        "nome": request.form.get("nome"),
        "orcamento": float(request.form.get("orcamento")),
        "clima": request.form.get("clima"),
        "interesses": [interesse.strip() for interesse in request.form.get("interesses").split(",")],
        "data_inicio": request.form.get("data_inicio") if request.form.get("data_inicio") else None,
        "data_fim": request.form.get("data_fim") if request.form.get("data_fim") else None,
        "acomodacao": request.form.get("acomodacao"),
        "transporte": request.form.get("transporte"),
        "dietas": request.form.get("dietas") if request.form.get("dietas") else None,
        "companhia": request.form.get("companhia"),
        "atividade_fisica": request.form.get("atividade_fisica"),
        "idiomas": request.form.get("idiomas") if request.form.get("idiomas") else None,
        "acessibilidade": request.form.get("acessibilidade") if request.form.get("acessibilidade") else None,
        "faixa_etaria": request.form.get("faixa_etaria") if request.form.get("faixa_etaria") else None,
        "experiencias": request.form.get("experiencias") if request.form.get("experiencias") else None
    }

    mongo.db.planos_de_viagem.insert_one(dados_formulario)
    # Inicializar as variáveis
    dados_guia = None
    guia = None

    # Criar o prompt (conforme atualizado na seção anterior)
    prompt = f"""
        Você é um assistente de viagem especializado em fornecer planos de viagem personalizados e detalhados.

        Informações do usuário:
        - Nome: {dados_formulario["nome"]}
        - Orçamento total: {dados_formulario["orcamento"]} reais
        - Clima preferido: {dados_formulario["clima"]}
        - Interesses: {dados_formulario["interesses"]}
        - Data de início da viagem: {dados_formulario["data_inicio"]}
        - Data de fim da viagem: {dados_formulario["data_fim"]}
        - Tipo de acomodação preferida: {dados_formulario["acomodacao"]}
        - Meio de transporte preferido: {dados_formulario["transporte"]}
        - Dietas ou restrições alimentares: {dados_formulario["dietas"]}
        - Companhia de viagem: {dados_formulario["companhia"]}
        - Nível de atividade física: {dados_formulario["atividade_fisica"]}
        - Idiomas falados: {dados_formulario["idiomas"]}
        - Necessidades especiais ou acessibilidade: {dados_formulario["acessibilidade"]}
        - Faixa etária: {dados_formulario["faixa_etaria"]}
        - Destinos ou experiências anteriores: {dados_formulario["experiencias"]}

        Objetivo:
        - Fornecer um plano de viagem completo que se encaixe estritamente no orçamento do usuário.
        - O plano deve incluir:
        - Destinos recomendados
        - Itinerário diário (organizado por dia)
        - Opções de hospedagem (de acordo com a preferência)
        - Opções de transporte (de acordo com a preferência)
        - Atividades e atrações (considerando interesses e nível de atividade física)
        - Custos estimados para cada item
        - Dicas úteis para economizar e aproveitar ao máximo a viagem
        - Considerar dietas, necessidades especiais e idiomas falados

        Formato da resposta:
        Retorne a resposta no seguinte formato JSON:

        {{
        "plano_viagem": [
            {{
            "dia": 1,
            "data": "Data específica ou relativa",
            "destino": "Nome do Destino",
            "hospedagem": "Opção de hospedagem com custo estimado",
            "transporte": "Detalhes do transporte com custo estimado",
            "atividades": [
                {{
                "nome": "Nome da Atividade",
                "descrição": "Breve descrição",
                "custo": "Custo estimado"
                }},
                ... (outras atividades)
            ],
            "custo_total_dia": "Custo total estimado para o dia"
            }},
            ... (outros dias)
        ],
        "custo_total_viagem": "Custo total estimado para toda a viagem",
        "dicas": ["Dica 1", "Dica 2"]
        }}

        Certifique-se de que:

        - O custo total da viagem não exceda o orçamento de {dados_formulario["orcamento"]} reais.
        - Todos os campos estejam preenchidos corretamente.
        - O plano atenda às preferências e necessidades do usuário.
        - O JSON esteja bem formatado e válido.
        - Não inclua texto adicional fora do formato JSON.

        Se não for possível elaborar um plano dentro do orçamento ou atender às preferências, retorne uma mensagem de erro no seguinte formato JSON:

        {{
        "erro": "Desculpe, não é possível elaborar um plano de viagem completo dentro do orçamento e preferências fornecidos."
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

        # Tentar carregar o conteúdo como JSON
        dados_guia = json.loads(conteudo, parse_float=Decimal)

        # Verificar se há um erro na resposta
        if 'erro' in dados_guia:
            guia = dados_guia['erro']
            dados_guia = None
        else:
            # Verificar se o custo total não excede o orçamento
            custo_total_viagem = Decimal(dados_guia.get('custo_total_viagem', '0'))
            if Decimal(dados_formulario["orcamento"]) < custo_total_viagem:
                guia = "Desculpe, o plano de viagem excede o seu orçamento. Por favor, tente novamente com um orçamento maior."
                dados_guia = None

    except json.JSONDecodeError as e:
        guia = "Desculpe, ocorreu um erro ao processar o plano de viagem. Por favor, tente novamente mais tarde."
        print(f"Erro ao decodificar JSON: {e}")
    except Exception as e:
        guia = "Desculpe, ocorreu um erro ao gerar o plano de viagem. Por favor, tente novamente mais tarde."
        print(f"Erro ao chamar a API da OpenAI: {e}")

    return render_template('result.html', nome=dados_formulario["nome"], dados_guia=dados_guia, guia=guia)

if __name__ == '__main__':
    app.run(debug=True)