import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="TI Asset Manager - MSP",
    page_icon="🖥️",
    layout="wide"
)

# --- CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"Erro de configuração: {e} não encontrado em st.secrets.")
        st.stop()

supabase = init_connection()

# --- FUNÇÕES DE BANCO DE DADOS ---

def listar_empresas() -> pd.DataFrame:
    try:
        response = supabase.table("empresas").select("id, nome_fantasia, status_contrato").order("nome_fantasia").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao carregar empresas: {e}")
        return pd.DataFrame()

def listar_locais(empresa_id: str) -> pd.DataFrame:
    try:
        response = supabase.table("locais").select("id, nome").eq("empresa_id", empresa_id).order("nome").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao carregar locais: {e}")
        return pd.DataFrame()

def carregar_dashboard_dados(empresa_id: str = None) -> pd.DataFrame:
    try:
        # MELHORIA: Incluindo explicitamente os campos adicionais para filtros temporais futuros
        query = supabase.table("ativos").select(
            "id, tipo, fabricante, modelo, numero_serie, status, data_compra, fim_garantia, locais(nome)"
        )
        if empresa_id:
            query = query.eq("empresa_id", empresa_id)
            
        response = query.execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty and "locais" in df.columns:
            df["local"] = df["locais"].apply(lambda x: x["nome"] if isinstance(x, dict) else "Não Alocado")
            df = df.drop(columns=["locais"])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar ativos: {e}")
        return pd.DataFrame()

# --- NAVEGAÇÃO PRINCIPAL (SIDEBAR) ---
st.sidebar.title("🛠️ TI Asset Navigation")
menu = st.sidebar.radio("Navegar para:", ["📊 Dashboard Geral", "🏢 Cadastrar Cliente/Local", "🖥️ Cadastrar Equipamento"])

st.sidebar.markdown("---")

df_empresas = listar_empresas()
df_empresas_ativas = df_empresas[df_empresas["status_contrato"] == "Ativo"] if not df_empresas.empty else pd.DataFrame()

empresa_selecionada_id = None
opcao_filtro = "Todos"

if menu == "📊 Dashboard Geral" and not df_empresas_ativas.empty:
    st.sidebar.subheader("Filtro do Dashboard")
    opcoes_empresas = ["Todos os Contratos"] + df_empresas_ativas["nome_fantasia"].tolist()
    opcao_filtro = st.sidebar.selectbox("Selecione o Cliente:", opcoes_empresas)
    
    if opcao_filtro != "Todos os Contratos":
        empresa_selecionada_id = df_empresas_ativas[df_empresas_ativas["nome_fantasia"] == opcao_filtro]["id"].values[0]

# --- MENU 1: DASHBOARD GERAL (MELHORADO) ---
if menu == "📊 Dashboard Geral":
    st.title("📊 Dashboard Geral de Infraestrutura")
    st.caption(f"Visualizando escopo: **{opcao_filtro}**")
    st.markdown("---")
    
    df_ativos = carregar_dashboard_dados(empresa_selecionada_id)
    
    if df_ativos.empty:
        st.info("Nenhum equipamento cadastrado neste escopo. Vá até a aba de cadastros para começar!")
    else:
        # Tratamento de datas
        df_ativos["fim_garantia"] = pd.to_datetime(df_ativos["fim_garantia"])
        hoje = pd.Timestamp.now().normalize()
        
        # KPIs Existentes
        total_ativos = len(df_ativos)
        em_producao = len(df_ativos[df_ativos["status"] == "Em Produção"])
        garantias_vencidas = len(df_ativos[df_ativos["fim_garantia"] < hoje])
        
        # MELHORIA: Nova Métrica - Equipamentos obsoletos ou críticos cadastrados há mais de 5 anos
        df_ativos["data_compra"] = pd.to_datetime(df_ativos["data_compra"])
        limite_obsolescencia = hoje - pd.DateOffset(years=5)
        equipamentos_antigos = len(df_ativos[df_ativos["data_compra"] < limite_obsolescencia])
        
        # Layout de 4 colunas atualizado com a melhoria técnica
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Ativos", total_ativos)
        col2.metric("Em Produção", em_producao)
        col3.metric("🚨 Garantias Vencidas", garantias_vencidas, delta=f"{garantias_vencidas} pendente(s)" if garantias_vencidas > 0 else None, delta_color="inverse")
        col4.metric("⚠️ Ciclo Crítico (>5 anos)", equipamentos_antigos, delta="Substituição Recomendada" if equipamentos_antigos > 0 else None, delta_color="off")
        
        st.markdown("---")
        
        # Gráficos
        cg1, cg2 = st.columns(2)
        with cg1:
            st.write("#### Equipamentos por Tipo")
            st.bar_chart(df_ativos["tipo"].value_counts())
        with cg2:
            st.write("#### Status dos Ativos")
            st.bar_chart(df_ativos["status"].value_counts())
            
        st.markdown("---")
        st.write("#### 📋 Inventário Atualizado")
        df_exibicao = df_ativos.copy()
        df_exibicao["fim_garantia"] = df_exibicao["fim_garantia"].dt.strftime('%d/%m/%Y')
        df_exibicao["data_compra"] = df_exibicao["data_compra"].dt.strftime('%d/%m/%Y')
        st.dataframe(df_exibicao, use_container_width=True)

# [Manter o restante do arquivo igual: menus 2 e 3 de cadastros]