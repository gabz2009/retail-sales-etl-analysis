"""
=====================================================================
 CONFIGURACAO DO ETL
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   Tudo o que pode mudar (caminhos das pastas, período, regras de
   negócio) está aqui, num só sítio. Assim:
     - o avaliador não tem de alterar código para correr o ETL;
     - se eu quiser mudar uma decisão (ex.: excluir outro código),
       mudo só aqui e volto a correr.
   Os caminhos são calculados a partir da localização deste ficheiro,
   por isso o projeto funciona em qualquer pasta do computador.

 BIBLIOTECAS USADAS
   - pathlib (Path): cria caminhos de pastas e ficheiros que funcionam
     em Windows, Mac e Linux.
     Usada nas linhas: 33  (importada na linha 26)
   - sys: permite parar o programa com uma mensagem de erro.
     Usada nas linhas: 149  (importada na linha 25)
   - logging: escreve mensagens no ecrã e no ficheiro de log.
     Usada nas linhas: 148  (importada na linha 24)
=====================================================================
"""
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------
# 1. PASTAS E FICHEIROS
# ---------------------------------------------------------------------
# __file__ é este ficheiro (etl/configuracao.py). Subindo duas vezes
# (.parent.parent) chegamos à pasta principal do projeto.
PASTA_PROJETO = Path(__file__).resolve().parent.parent

PASTA_ORIGEM = PASTA_PROJETO / "dados" / "origem"          # dados brutos (nunca alterados)
PASTA_TRATADOS = PASTA_PROJETO / "dados" / "tratados"      # dados prontos para o Power BI
PASTA_QUALIDADE = PASTA_PROJETO / "dados" / "qualidade"    # registos de qualidade
PASTA_LOGS = PASTA_PROJETO / "etl" / "logs"                # um log por execução

FICHEIRO_VENDAS = PASTA_ORIGEM / "Online Retail.xlsx"
FICHEIRO_CAMBIO = PASTA_ORIGEM / "data_cambio.csv"

# ---------------------------------------------------------------------
# 2. FONTES (endereços oficiais indicados no enunciado)
# ---------------------------------------------------------------------
DATA_OBTENCAO_VENDAS = "2026-09-11"   # dia em que descarreguei o Excel da UCI (download manual)
DATA_OBTENCAO_CAMBIO = "2026-09-11"   # dia em que descarreguei o CSV do BCE (download manual)
URL_PAGINA_VENDAS = "https://archive.ics.uci.edu/dataset/352/online+retail"
URL_VENDAS = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
URL_PAGINA_CAMBIO = "https://data.ecb.europa.eu/data/datasets/EXR/EXR.M.GBP.EUR.SP00.A"
URL_CAMBIO = ("https://dataapi.ecb.europa.eu/service/data/EXR/M.GBP.EUR.SP00.A"
              "?startPeriod=2010-12&endPeriod=2011-12&format=csvdata")

# ---------------------------------------------------------------------
# 3. PERÍODO DE ANÁLISE
# ---------------------------------------------------------------------
LINHAS_ESPERADAS = 541909    # nº de linhas indicado no enunciado

# Os 13 meses para os quais tem de existir uma taxa de câmbio
MESES_ANALISE = ["2010-12", "2011-01", "2011-02", "2011-03", "2011-04",
                 "2011-05", "2011-06", "2011-07", "2011-08", "2011-09",
                 "2011-10", "2011-11", "2011-12"]

# Dezembro de 2011 só tem vendas até dia 9, por isso é um mês incompleto
MESES_INCOMPLETOS = ["2011-12"]

# Calendário contínuo (todos os dias, mesmo sem vendas)
CALENDARIO_INICIO = "2010-12-01"
CALENDARIO_FIM = "2011-12-31"

# ---------------------------------------------------------------------
# 4. REGRAS DE NEGÓCIO: MOVIMENTOS NÃO COMERCIAIS
# ---------------------------------------------------------------------
# Códigos que NÃO são vendas a clientes -> excluídos da análise.
# (O impacto de cada exclusão fica registado na pasta de qualidade.)
CODIGOS_EXCLUIR = {
    "AMAZONFEE": "Comissão cobrada pela Amazon (é um custo, não uma venda)",
    "BANK CHARGES": "Encargos bancários (é um custo, não uma venda)",
    "CRUK": "Comissão CRUK (movimento financeiro, não uma venda)",
    "B": "Ajuste de dívida incobrável (movimento contabilístico)",
    "M": "Lançamento manual sem produto identificado e com valores extremos",
    "S": "Amostras (samples): não são vendas nem devoluções",
}

# Códigos que NÃO são produtos mas SÃO valor cobrado ao cliente ->
# ficam na análise, mas com uma categoria própria para poderem ser
# retirados dos rankings de produtos com um filtro no Power BI.
CODIGOS_CATEGORIA = {
    "POST": "Portes e transporte",
    "DOT": "Portes e transporte",
    "C2": "Portes e transporte",
    "D": "Descontos",
}
PREFIXO_VALES = "GIFT_0001"          # vales de oferta (ex.: gift_0001_20)
CATEGORIA_VALES = "Vales de oferta"

# ---------------------------------------------------------------------
# 5. PAÍSES
# ---------------------------------------------------------------------
# Nomes da origem que precisam de ser corrigidos
CORRECAO_PAISES = {
    "EIRE": "Ireland",
    "RSA": "South Africa",
    "USA": "United States",
}

# Nome em português para mostrar no relatório
NOMES_PAISES_PT = {
    "United Kingdom": "Reino Unido", "Ireland": "Irlanda", "France": "França",
    "Germany": "Alemanha", "Netherlands": "Países Baixos", "Belgium": "Bélgica",
    "Switzerland": "Suíça", "Spain": "Espanha", "Portugal": "Portugal",
    "Italy": "Itália", "Austria": "Áustria", "Denmark": "Dinamarca",
    "Norway": "Noruega", "Sweden": "Suécia", "Finland": "Finlândia",
    "Iceland": "Islândia", "Poland": "Polónia", "Czech Republic": "República Checa",
    "Lithuania": "Lituânia", "Greece": "Grécia", "Cyprus": "Chipre",
    "Malta": "Malta", "Channel Islands": "Ilhas do Canal",
    "European Community": "Comunidade Europeia (não especificado)",
    "Unspecified": "Não especificado", "Australia": "Austrália",
    "Japan": "Japão", "Singapore": "Singapura", "Hong Kong": "Hong Kong",
    "Israel": "Israel", "Lebanon": "Líbano", "Bahrain": "Barém",
    "United Arab Emirates": "Emirados Árabes Unidos", "Saudi Arabia": "Arábia Saudita",
    "Canada": "Canadá", "United States": "Estados Unidos", "Brazil": "Brasil",
    "South Africa": "África do Sul",
}

# ---------------------------------------------------------------------
# 6. OUTROS PARÂMETROS
# ---------------------------------------------------------------------
# Linhas com quantidade >= 10 000 (em valor absoluto) são listadas como
# valores extremos. NÃO são apagadas, só ficam identificadas.
LIMITE_QUANTIDADE_EXTREMA = 10000

# Casos usados para comparar os números do ETL com os do Power BI
AMOSTRA_MES = "2011-11"
AMOSTRA_PAIS = "France"
AMOSTRA_PRODUTO = "85123A"

# Texto usado para os clientes sem CustomerID
CLIENTE_DESCONHECIDO = "DESCONHECIDO"


# ---------------------------------------------------------------------
# 7. FUNÇÃO DE APOIO
# ---------------------------------------------------------------------
def parar_com_erro(mensagem):
    """Escreve o erro no log e no ecrã e termina o programa.
    É usada sempre que algo grave impede o ETL de continuar."""
    logging.error(mensagem)
    sys.exit(f"\nERRO: {mensagem}\nConsulte o log na pasta etl/logs/.\n")
