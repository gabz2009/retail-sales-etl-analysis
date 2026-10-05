"""
=====================================================================
 PASSO 4 - CRIAR AS TABELAS DO MODELO (ESQUEMA EM ESTRELA)
=====================================================================
 PORQUE EXISTE ESTE FICHEIRO?
   O Power BI funciona melhor com um modelo em estrela:
     - uma tabela de FACTOS no centro (fVendas), com os números;
     - tabelas de DIMENSÃO à volta, com as descrições para filtrar:
       dCalendario (datas), dProduto, dCliente e dPais.
     - dCambio liga-se ao calendário pelo mês (AnoMes).
   Granularidade da fVendas: 1 linha = 1 linha elegível do Excel
   (uma linha de fatura, depois de tirar duplicados e exclusões).

   Também criamos duas tabelas pequenas para o relatório:
     - dMoeda: para o botão de escolher GBP ou EUR;
     - dFaixaEncomendas: para agrupar clientes por nº de encomendas.

 O QUE FAZ
   Uma função para cada tabela: criar_fvendas(), criar_dproduto(),
   criar_dcliente(), criar_dpais(), criar_dcalendario(),
   criar_dcambio() e criar_tabelas_auxiliares().

 BIBLIOTECAS USADAS
   - pandas (pd): criar tabelas novas e a lista contínua de datas.
     Usada nas linhas: 46, 93, 101, 112, 113, 138, 139  (importada na
       linha 33)
   - configuracao (cfg): categorias de códigos, nomes de países,
     datas do calendário e meses incompletos.
     Usada nas linhas: 68, 69, 70, 71, 94, 103, 112, 120  (importada na
       linha 35)
=====================================================================
"""
import pandas as pd

import configuracao as cfg

MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
            "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]


def criar_fvendas(elegiveis):
    # Escolhemos só as colunas necessárias e damos-lhes nomes claros
    fvendas = pd.DataFrame({
        "LinhaOrigem": elegiveis["LinhaOrigem"],
        "InvoiceNo": elegiveis["InvoiceNo"],
        "DataHora": elegiveis["InvoiceDate"],
        "Data": elegiveis["Data"],
        "AnoMes": elegiveis["AnoMes"],
        "StockCode": elegiveis["StockCode"],
        "ClienteKey": elegiveis["ClienteKey"],
        "PaisKey": elegiveis["PaisKey"],
        "Quantidade": elegiveis["Quantity"].astype(int),
        "PrecoUnitarioGBP": elegiveis["UnitPrice"],
        "ValorGBP": elegiveis["ValorGBP"],
        "TaxaGBPporEUR": elegiveis["TaxaGBPporEUR"],
        "ValorEUR": elegiveis["ValorEUR"],
        "TipoMovimento": elegiveis["TipoMovimento"],
        "PrefixoC": elegiveis["PrefixoC"],
    })
    return fvendas.sort_values("LinhaOrigem")


def categoria_do_codigo(codigo):
    """Diz se um código é mercadoria ou outra coisa (portes, descontos, vales)."""
    if codigo in cfg.CODIGOS_CATEGORIA:
        return cfg.CODIGOS_CATEGORIA[codigo]
    if codigo.startswith(cfg.PREFIXO_VALES):
        return cfg.CATEGORIA_VALES
    return "Mercadoria"


def criar_dproduto(elegiveis):
    # O mesmo código pode aparecer com descrições diferentes.
    # Escolhemos a descrição mais frequente (a "moda") de cada código.
    def descricao_mais_frequente(descricoes):
        descricoes = descricoes.dropna()
        if len(descricoes) == 0:
            return "(SEM DESCRIÇÃO)"
        return descricoes.mode().iloc[0]

    dproduto = (elegiveis.groupby("StockCode")["Descricao"]
                .agg(descricao_mais_frequente)
                .reset_index())
    dproduto["Categoria"] = dproduto["StockCode"].apply(categoria_do_codigo)
    dproduto["ProdutoLabel"] = dproduto["StockCode"] + " - " + dproduto["Descricao"]
    return dproduto


def criar_dcliente(elegiveis):
    dcliente = pd.DataFrame({"ClienteKey": elegiveis["ClienteKey"].unique()})
    dcliente["Identificado"] = dcliente["ClienteKey"] != cfg.CLIENTE_DESCONHECIDO
    dcliente["ClienteNome"] = "Cliente " + dcliente["ClienteKey"]
    dcliente.loc[~dcliente["Identificado"], "ClienteNome"] = "Cliente desconhecido"
    return dcliente.sort_values("ClienteKey")


def criar_dpais(elegiveis):
    dpais = pd.DataFrame({"PaisKey": elegiveis["PaisKey"].unique()})
    # Nome em português (se não estiver na lista, fica o nome original)
    dpais["PaisPT"] = dpais["PaisKey"].map(cfg.NOMES_PAISES_PT).fillna(dpais["PaisKey"])
    # Mercado: Reino Unido vs. restantes (usado na página 2)
    dpais["Mercado"] = "Outros mercados"
    dpais.loc[dpais["PaisKey"] == "United Kingdom", "Mercado"] = "Reino Unido"
    return dpais.sort_values("PaisKey")


def criar_dcalendario(elegiveis):
    # Todos os dias entre o início e o fim, mesmo os dias sem vendas
    datas = pd.date_range(cfg.CALENDARIO_INICIO, cfg.CALENDARIO_FIM, freq="D")
    cal = pd.DataFrame({"Data": datas})
    cal["Ano"] = cal["Data"].dt.year
    cal["NumMes"] = cal["Data"].dt.month
    cal["AnoMes"] = cal["Data"].dt.strftime("%Y-%m")
    cal["AnoMesNum"] = cal["Ano"] * 100 + cal["NumMes"]           # para ordenar (201012, 201101...)
    cal["NomeMes"] = cal["NumMes"].apply(lambda m: MESES_PT[m - 1])
    cal["MesAno"] = cal["NumMes"].apply(lambda m: MESES_ABREV[m - 1]) + " " + cal["Ano"].astype(str)
    cal["MesCompleto"] = ~cal["AnoMes"].isin(cfg.MESES_INCOMPLETOS)
    # Rótulo com * nos meses incompletos (ex.: "dez 2011*")
    cal["RotuloMes"] = cal["MesAno"]
    cal.loc[~cal["MesCompleto"], "RotuloMes"] = cal["MesAno"] + "*"
    cal["NumDiaSemana"] = cal["Data"].dt.dayofweek + 1            # 1 = segunda-feira
    cal["DiaSemana"] = cal["Data"].dt.dayofweek.apply(lambda d: DIAS_SEMANA[d])
    cal["TemVendas"] = cal["Data"].isin(elegiveis["Data"])
    return cal


def criar_dcambio(taxas):
    dcambio = taxas.sort_values("AnoMes").copy()
    dcambio["Serie"] = "EXR.M.GBP.EUR.SP00.A (BCE)"
    dcambio["Explicacao"] = "Média mensal de libras por 1 euro. EUR = GBP / taxa"
    return dcambio


def criar_tabelas_auxiliares():
    dmoeda = pd.DataFrame({"Moeda": ["GBP", "EUR"], "Simbolo": ["£", "€"], "Ordem": [1, 2]})
    dfaixas = pd.DataFrame({
        "Faixa": ["1", "2", "3 a 5", "6 a 10", "11 a 20", "21 a 50", "Mais de 50"],
        "Min": [1, 2, 3, 6, 11, 21, 51],
        "Max": [1, 2, 5, 10, 20, 50, 1000000],
        "Ordem": [1, 2, 3, 4, 5, 6, 7],
    })
    return dmoeda, dfaixas
