import os
from flask import Flask, render_template, request
import openai
import json
from decimal import Decimal
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)

# Configuração da API OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

if not openai.api_key:
    raise ValueError("A chave da API OpenAI não está definida. Defina a variável de ambiente 'OPENAI_API_KEY'.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gerar_guia', methods=['POST'])
def gerar_guia():
    # Campos obrigatórios
    nome = request.form.get('nome')
    orcamento = request.form.get('orcamento')
    clima = request.form.get('clima')
    interesses = request.form.get('interesses')

    # Novos campos opcionais
    data_inicio = request.form.get('data_inicio') or 'não especificada'
    data_fim = request.form.get('data_fim') or 'não especificada'
    acomodacao = request.form.get('acomodacao')
    transporte = request.form.get('transporte')
    dietas = request.form.get('dietas') or 'nenhuma'
    companhia = request.form.get('companhia')
    atividade_fisica = request.form.get('atividade_fisica')
    idiomas = request.form.get('idiomas') or 'não especificado'
    acessibilidade = request.form.get('acessibilidade') or 'nenhuma'
    faixa_etaria = request.form.get('faixa_etaria') or 'não especificada'
    experiencias = request.form.get('experiencias') or 'nenhuma'

    # Inicializar as variáveis
    dados_guia = None
    guia = None

    # Criar o prompt (conforme atualizado na seção anterior)
    prompt = f"""
        Você é um assistente de viagem especializado em fornecer planos de viagem personalizados e detalhados.

        Informações do usuário:
        - Nome: {nome}
        - Orçamento total: {orcamento} reais
        - Clima preferido: {clima}
        - Interesses: {interesses}
        - Data de início da viagem: {data_inicio}
        - Data de fim da viagem: {data_fim}
        - Tipo de acomodação preferida: {acomodacao}
        - Meio de transporte preferido: {transporte}
        - Dietas ou restrições alimentares: {dietas}
        - Companhia de viagem: {companhia}
        - Nível de atividade física: {atividade_fisica}
        - Idiomas falados: {idiomas}
        - Necessidades especiais ou acessibilidade: {acessibilidade}
        - Faixa etária: {faixa_etaria}
        - Destinos ou experiências anteriores: {experiencias}

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

        - O custo total da viagem não exceda o orçamento de {orcamento} reais.
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
            if Decimal(orcamento) < custo_total_viagem:
                guia = "Desculpe, o plano de viagem excede o seu orçamento. Por favor, tente novamente com um orçamento maior."
                dados_guia = None

    except json.JSONDecodeError as e:
        guia = "Desculpe, ocorreu um erro ao processar o plano de viagem. Por favor, tente novamente mais tarde."
        print(f"Erro ao decodificar JSON: {e}")
    except Exception as e:
        guia = "Desculpe, ocorreu um erro ao gerar o plano de viagem. Por favor, tente novamente mais tarde."
        print(f"Erro ao chamar a API da OpenAI: {e}")

    return render_template('result.html', nome=nome, dados_guia=dados_guia, guia=guia)

if __name__ == '__main__':
    app.run(debug=True)