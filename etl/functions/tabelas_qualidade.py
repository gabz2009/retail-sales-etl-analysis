"""
=====================================================================
 PASSO 6 - TABELAS DE QUALIDADE (PARA A PÁGINA 5 DO RELATÓRIO)
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   A página 5 do relatório tem de mostrar "até que ponto podemos
   confiar nos resultados". Para isso precisa de tabelas com:
     - quantas linhas entraram, ficaram e saíram (e porquê);
     - a reconciliação dos valores (nada se perdeu pelo caminho);
     - os problemas encontrados e a decisão tomada em cada um;
     - a cobertura das taxas de câmbio;
     - números de controlo para comparar o ETL com o Power BI;
     - as fontes, a data de obtenção e a data da última execução.
   Estas tabelas são gravadas na pasta dados/qualidade/.

 BIBLIOTECAS USADAS
   - pandas (pd): criar as tabelas.
     Usada nas linhas: 73, 102, 192, 197, 225, 264, 278, 287
       (importada na linha 36)
   - logging: avisar se faltar a data de obtenção das fontes.
     Usada nas linhas: 263  (importada na linha 32)
   - platform: saber a versão do Python (fica registada na execução).
     Usada nas linhas: 286  (importada na linha 33)
   - datetime: data e hora da execução.
     Usada nas linhas: 280  (importada na linha 34)
   - configuracao (cfg): caminhos, meses incompletos, amostras, etc.
     Usada nas linhas: 53, 137, 142, 169, 182, 186, 197, 206, 216, 217,
       218, 229, 245, 246, 247, 262, 266, 268, 270, 271, 272  (importada
       na linha 38)
=====================================================================
"""
import logging
import platform
from datetime import datetime

import pandas as pd

import configuracao as cfg


def calcular_indicadores(f):
    """Calcula os indicadores com as MESMAS regras das medidas DAX.
    Serve para comparar os números do ETL com os do Power BI."""
    vendas = f[f["TipoMovimento"] == "Venda"]
    estornos = f[f["TipoMovimento"] == "Estorno"]
    brutas_gbp = vendas["ValorGBP"].sum()
    estornos_gbp = abs(estornos["ValorGBP"].sum())     # estornos em valor positivo
    brutas_eur = vendas["ValorEUR"].sum()
    estornos_eur = abs(estornos["ValorEUR"].sum())
    encomendas = vendas["InvoiceNo"].nunique()         # faturas com pelo menos uma venda

    # Clientes identificados e recorrentes (2 ou mais encomendas)
    identificados = vendas[vendas["ClienteKey"] != cfg.CLIENTE_DESCONHECIDO]
    encomendas_por_cliente = identificados.groupby("ClienteKey")["InvoiceNo"].nunique()

    return {
        "VendasBrutasGBP": brutas_gbp,
        "EstornosGBP": estornos_gbp,
        "VendasLiquidasGBP": brutas_gbp - estornos_gbp,
        "VendasBrutasEUR": brutas_eur,
        "EstornosEUR": estornos_eur,
        "VendasLiquidasEUR": brutas_eur - estornos_eur,
        "EncomendasVenda": encomendas,
        "ValorMedioEncomendaGBP": brutas_gbp / encomendas if encomendas > 0 else None,
        "PesoEstornos": estornos_gbp / brutas_gbp if brutas_gbp > 0 else None,
        "ClientesIdentificados": len(encomendas_por_cliente),
        "ClientesRecorrentes": int((encomendas_por_cliente >= 2).sum()),
    }


def tabela_nulos(nulos):
    """nulos = dicionário {coluna: nº de valores em falta} (vem do controlo C02)."""
    return pd.DataFrame(list(nulos.items()), columns=["Coluna", "ValoresEmFalta"])


def tabela_resumo_estados(vendas):
    """Quantas linhas e que valor há em cada Estado/Motivo."""
    resumo = (vendas.groupby(["Estado", "Motivo"])
              .agg(Linhas=("LinhaOrigem", "count"), ValorGBP=("ValorGBP", "sum"))
              .reset_index())
    resumo["Motivo"] = resumo["Motivo"].replace("", "-")
    resumo["PercentagemLinhas"] = resumo["Linhas"] / len(vendas)
    return resumo


def tabela_reconciliacao(vendas, fvendas):
    """Do total do Excel até às vendas líquidas, passo a passo."""
    linhas = [["Linhas do ficheiro de origem", len(vendas), vendas["ValorGBP"].sum()]]
    fora = vendas[vendas["Estado"] != "Elegível"]
    for (estado, motivo), grupo in fora.groupby(["Estado", "Motivo"]):
        linhas.append([f"(-) {estado}: {motivo}", -len(grupo), -grupo["ValorGBP"].sum()])
    linhas.append(["= Base elegível (fVendas)", len(fvendas), fvendas["ValorGBP"].sum()])
    diferenca_linhas = len(vendas) - len(fora) - len(fvendas)
    diferenca_valor = vendas["ValorGBP"].sum() - fora["ValorGBP"].sum() - fvendas["ValorGBP"].sum()
    linhas.append(["Diferença (tem de ser zero)", diferenca_linhas, diferenca_valor])

    ind = calcular_indicadores(fvendas)
    linhas.append(["Vendas brutas", (fvendas["TipoMovimento"] == "Venda").sum(), ind["VendasBrutasGBP"]])
    linhas.append(["Estornos ou cancelamentos", (fvendas["TipoMovimento"] == "Estorno").sum(), ind["EstornosGBP"]])
    linhas.append(["Vendas líquidas", len(fvendas), ind["VendasLiquidasGBP"]])

    tabela = pd.DataFrame(linhas, columns=["Etapa", "Linhas", "ValorGBP"])
    tabela.insert(0, "Ordem", range(1, len(tabela) + 1))
    return tabela


def tabela_problemas_decisoes(vendas, fvendas, dproduto):
    """Lista de problemas encontrados e a decisão tomada em cada um."""
    def contar_motivo(motivo):
        grupo = vendas[vendas["Motivo"] == motivo]
        return len(grupo), grupo["ValorGBP"].sum()

    problemas = []

    def adicionar(problema, linhas, valor, decisao, justificacao):
        problemas.append({"Problema": problema, "Linhas": linhas, "ValorGBP": valor,
                          "Decisao": decisao, "Justificacao": justificacao})

    n, v = contar_motivo("Duplicado exato")
    adicionar("Linhas repetidas nas 8 colunas", n, v,
              "Removidas; fica a 1.ª ocorrência; lista em qa_linhas_fora_da_analise.csv",
              "Não há identificador de linha; uma cópia exata no mesmo minuto é provavelmente um registo repetido.")
    n, v = contar_motivo("Data inválida")
    adicionar("Data em falta ou inválida", n, v, "Excluídas", "Sem data não há mês, câmbio nem calendário.")
    n, v = contar_motivo("Fatura ou produto em falta")
    adicionar("InvoiceNo ou StockCode em falta", n, v, "Excluídas", "Regra da base elegível do enunciado.")
    n, v = contar_motivo("Quantidade nula ou zero")
    adicionar("Quantidade nula ou zero", n, v, "Excluídas", "Regra da base elegível do enunciado.")
    n, v = contar_motivo("Preço nulo, zero ou negativo")
    adicionar("Preço nulo, zero ou negativo", n, v, "Excluídas",
              "Regra da base elegível. Inclui acertos de stock sem valor e o ajuste de dívida com preço negativo.")
    n, v = contar_motivo("Fatura C com quantidade positiva")
    adicionar("Fatura C com quantidade positiva", n, v, "Anomalia, fora da análise",
              "O enunciado manda analisar estes casos separadamente.")
    n, v = contar_motivo("Movimento não comercial")
    adicionar("Comissões, taxas, ajustes e amostras", n, v, "Excluídas",
              "Não são vendas a clientes. Códigos: " + ", ".join(cfg.CODIGOS_EXCLUIR.keys()))
    n, v = contar_motivo("Prefixo de fatura desconhecido")
    adicionar("Fatura com prefixo diferente de C (ex.: A)", n, v, "Anomalia, fora da análise",
              "Só o prefixo C está documentado na fonte.")

    sem_cliente = fvendas[fvendas["ClienteKey"] == cfg.CLIENTE_DESCONHECIDO]
    adicionar("Vendas sem CustomerID", len(sem_cliente), sem_cliente["ValorGBP"].sum(),
              "Mantidas como cliente DESCONHECIDO",
              "O enunciado manda mantê-las nos indicadores comerciais e tirá-las só dos indicadores de clientes.")

    sem_descricao = vendas["Description"].isna()
    ficaram = int((sem_descricao & (vendas["Estado"] == "Elegível")).sum())
    adicionar("Descrição em falta", int(sem_descricao.sum()), vendas.loc[sem_descricao, "ValorGBP"].sum(),
              f"Não é motivo de exclusão ({ficaram} destas linhas ficaram elegíveis); o produto "
              "fica com a descrição mais frequente do mesmo código",
              "Quem identifica o produto é o StockCode; a descrição não faz parte da regra da base elegível.")

    sem_pais = vendas["Country"].isna()
    adicionar("País em falta", int(sem_pais.sum()), vendas.loc[sem_pais, "ValorGBP"].sum(),
              "Classificado como 'Unspecified' (Não especificado)",
              "Não se inventa o país; fica numa categoria própria, como os 'Unspecified' da origem.")

    estorno_sem_c = fvendas[(fvendas["TipoMovimento"] == "Estorno") & ~fvendas["PrefixoC"]]
    adicionar("Quantidade negativa sem prefixo C", len(estorno_sem_c), estorno_sem_c["ValorGBP"].sum(),
              "Tratadas como estorno", "O enunciado define estorno como quantidade negativa, com ou sem C.")

    categorias = fvendas.merge(dproduto[["StockCode", "Categoria"]], on="StockCode")
    for categoria, grupo in categorias[categorias["Categoria"] != "Mercadoria"].groupby("Categoria"):
        adicionar(f"Não é produto mas é valor cobrado: {categoria}", len(grupo), grupo["ValorGBP"].sum(),
                  "Mantidas com categoria própria (podem ser filtradas nos rankings de produtos)",
                  "É valor faturado ao cliente, por isso não foi excluído.")

    extremas = fvendas[fvendas["Quantidade"].abs() >= cfg.LIMITE_QUANTIDADE_EXTREMA]
    adicionar("Quantidades extremas", len(extremas), extremas["ValorGBP"].sum(),
              "Mantidas e listadas em qa_quantidades_extremas.csv",
              "Cumprem as regras. Apagá-las só para melhorar os números iria contra o enunciado.")

    alteradas = (vendas["Descricao"] != vendas["Description"]) & vendas["Description"].notna()
    adicionar("Descrições com espaços a mais ou minúsculas", int(alteradas.sum()), None,
              "Normalizadas; 1 descrição por código (a mais frequente)", "Evita o mesmo produto com nomes diferentes.")

    codigos_alterados = (vendas["StockCode"] != vendas["StockCodeOriginal"]) & vendas["StockCodeOriginal"].notna()
    adicionar("Códigos de produto com minúsculas", int(codigos_alterados.sum()), None,
              "Passados a maiúsculas", "Evita o mesmo produto com dois códigos.")

    paises_alterados = vendas["Country"].isin(cfg.CORRECAO_PAISES.keys())
    adicionar("Nomes de país diferentes (EIRE, RSA, USA)", int(paises_alterados.sum()), None,
              "Corrigidos para o nome oficial", "Nomes consistentes no relatório.")

    for mes in cfg.MESES_INCOMPLETOS:
        grupo = fvendas[fvendas["AnoMes"] == mes]
        adicionar(f"Mês incompleto: {mes}", len(grupo), grupo["ValorGBP"].sum(),
                  "Assinalado no calendário; sem variação mensal",
                  "As vendas terminam a 9/12/2011; comparar com meses completos seria enganador.")

    return pd.DataFrame(problemas)


def tabela_cobertura_cambio(taxas, fvendas):
    """Uma linha por mês: taxa, estado e volume de vendas convertido."""
    cobertura = pd.DataFrame({"AnoMes": cfg.MESES_ANALISE})
    cobertura = cobertura.merge(taxas, on="AnoMes", how="left")
    cobertura["Estado"] = "OK"
    cobertura.loc[cobertura["TaxaGBPporEUR"].isna(), "Estado"] = "EM FALTA"
    volume = (fvendas.groupby("AnoMes")
              .agg(Linhas=("LinhaOrigem", "count"), ValorGBP=("ValorGBP", "sum"), ValorEUR=("ValorEUR", "sum"))
              .reset_index())
    cobertura = cobertura.merge(volume, on="AnoMes", how="left")
    cobertura["Nota"] = ""
    for mes in cfg.MESES_INCOMPLETOS:
        cobertura.loc[cobertura["AnoMes"] == mes, "Nota"] = (
            "Vendas só até dia 9, mas a taxa é a média do mês completo")
    return cobertura


def tabela_amostras(fvendas):
    """Números de controlo para confirmar que o Power BI dá o mesmo que o ETL."""
    casos = [
        ("Total", "-", fvendas),
        ("Mês", cfg.AMOSTRA_MES, fvendas[fvendas["AnoMes"] == cfg.AMOSTRA_MES]),
        ("País", cfg.AMOSTRA_PAIS, fvendas[fvendas["PaisKey"] == cfg.AMOSTRA_PAIS]),
        ("Produto", cfg.AMOSTRA_PRODUTO, fvendas[fvendas["StockCode"] == cfg.AMOSTRA_PRODUTO]),
    ]
    linhas = []
    for filtro, valor, dados in casos:
        linha = {"Filtro": filtro, "Valor": valor, "LinhasFVendas": len(dados)}
        linha.update(calcular_indicadores(dados))
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabela_quantidades_extremas(fvendas, dproduto):
    extremas = fvendas[fvendas["Quantidade"].abs() >= cfg.LIMITE_QUANTIDADE_EXTREMA]
    extremas = extremas.merge(dproduto[["StockCode", "Descricao"]], on="StockCode", how="left")
    return extremas[["LinhaOrigem", "InvoiceNo", "DataHora", "StockCode", "Descricao", "ClienteKey",
                     "Quantidade", "PrecoUnitarioGBP", "ValorGBP", "TipoMovimento"]]


def tabela_codigos_fora_padrao(vendas):
    """Códigos que não parecem produtos normais (5 algarismos + letras opcionais).
    Serve para eu rever se falta alguma regra de movimento não comercial."""
    normal = vendas["StockCode"].str.match(r"^\d{5}[A-Z]{0,2}$").fillna(False).astype(bool)
    fora = vendas[~normal & vendas["StockCode"].notna()]
    resumo = (fora.groupby("StockCode")
              .agg(Exemplo=("Descricao", "first"), Linhas=("LinhaOrigem", "count"),
                   ValorGBP=("ValorGBP", "sum"))
              .reset_index())
    resumo["Decisao"] = "Mantido como mercadoria (sem regra)"
    resumo.loc[resumo["StockCode"].isin(cfg.CODIGOS_CATEGORIA.keys()), "Decisao"] = "Mantido com categoria própria"
    resumo.loc[resumo["StockCode"].str.startswith(cfg.PREFIXO_VALES), "Decisao"] = "Mantido com categoria própria"
    resumo.loc[resumo["StockCode"].isin(cfg.CODIGOS_EXCLUIR.keys()), "Decisao"] = "Excluído (não comercial)"
    return resumo.sort_values("Linhas", ascending=False)


def tabela_linhas_fora(vendas):
    """Evidência: todas as linhas que ficaram fora da análise, com os valores originais."""
    colunas = ["LinhaOrigem", "InvoiceNo", "StockCodeOriginal", "Description", "Quantity",
               "InvoiceDate", "UnitPrice", "CustomerID", "Country", "Estado", "Motivo",
               "LinhaPrimeiraOcorrencia", "ValorGBP"]
    return vendas.loc[vendas["Estado"] != "Elegível", colunas]


def tabela_fontes():
    """Fontes de dados, licença, endereço, período e data de obtenção.
    As datas de obtenção estão escritas no configuracao.py (download manual)."""
    if cfg.DATA_OBTENCAO_VENDAS == "AAAA-MM-DD" or cfg.DATA_OBTENCAO_CAMBIO == "AAAA-MM-DD":
        logging.warning("Falta preencher a data de obtenção das fontes no configuracao.py.")
    return pd.DataFrame([
        {"Fonte": "Online Retail - UCI Machine Learning Repository", "Autor": "Daqing Chen",
         "Licenca": "CC BY 4.0", "Pagina": cfg.URL_PAGINA_VENDAS, "Download": cfg.URL_VENDAS,
         "Periodo": "01/12/2010 a 09/12/2011",
         "DataObtencao": cfg.DATA_OBTENCAO_VENDAS, "Metodo": "Download manual"},
        {"Fonte": "Banco Central Europeu - série EXR.M.GBP.EUR.SP00.A", "Autor": "BCE",
         "Licenca": "Condições de reutilização do BCE", "Pagina": cfg.URL_PAGINA_CAMBIO,
         "Download": cfg.URL_CAMBIO, "Periodo": "2010-12 a 2011-12",
         "DataObtencao": cfg.DATA_OBTENCAO_CAMBIO, "Metodo": "Download manual"},
    ])


def tabela_execucao(inicio, total_linhas, linhas_fvendas, controlos):
    """Informação da última execução (aparece na página 5)."""
    return pd.DataFrame([{
        "Inicio": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "Fim": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "LinhasOrigem": total_linhas,
        "LinhasFVendas": linhas_fvendas,
        "ControlosOK": int((controlos["Resultado"] == "OK").sum()),
        "ControlosAviso": int((controlos["Resultado"] == "AVISO").sum()),
        "ControlosFalha": int((controlos["Resultado"] == "FALHA").sum()),
        "VersaoPython": platform.python_version(),
        "VersaoPandas": pd.__version__,
    }])
