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
# --- MENU 1: DASHBOARD GERAL (COM FILTROS AVANÇADOS) ---
if menu == "📊 Dashboard Geral":
    st.title("📊 Dashboard Geral de Infraestrutura")
    st.caption(f"Visualizando escopo: **{opcao_filtro}**")
    st.markdown("---")
    
    df_ativos = carregar_dashboard_dados(empresa_selecionada_id)
    
    if df_ativos.empty:
        st.info("Nenhum equipamento cadastrado neste escopo. Vá até a aba de cadastros para começar!")
    else:
        # --- NOVO BLOCO: FILTROS AVANÇADOS NA TELA ---
        st.markdown("### 🔍 Filtros Avançados")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            # Lista os tipos únicos presentes no banco para aquele cliente
            tipos_disponiveis = sorted(df_ativos["tipo"].unique().tolist())
            tipos_selecionados = st.multiselect(
                "Filtrar por Tipo de Equipamento:", 
                options=tipos_disponiveis,
                placeholder="Todos os tipos"
            )
            
        with col_f2:
            # Lista os status únicos presentes no banco para aquele cliente
            status_disponiveis = sorted(df_ativos["status"].unique().tolist())
            status_selecionados = st.multiselect(
                "Filtrar por Status Operacional:", 
                options=status_disponiveis,
                placeholder="Todos os status"
            )
        
        # Aplicação dinâmica dos filtros no DataFrame em memória
        df_filtrado = df_ativos.copy()
        
        if tipos_selecionados:
            df_filtrado = df_filtrado[df_filtrado["tipo"].isin(tipos_selecionados)]
            
        if status_selecionados:
            df_filtrado = df_filtrado[df_filtrado["status"].isin(status_selecionados)]
            
        st.markdown("---")
        
        # Se os filtros zerarem o resultado, exibe um aviso amigável
        if df_filtrado.empty:
            st.warning("Nenhum ativo corresponde aos filtros selecionados acima.")
        else:
            # Tratamento de datas baseado no DataFrame já filtrado
            df_filtrado["fim_garantia"] = pd.to_datetime(df_filtrado["fim_garantia"])
            df_filtrado["data_compra"] = pd.to_datetime(df_filtrado["data_compra"])
            hoje = pd.Timestamp.now().normalize()
            
            # KPIs recalculados dinamicamente
            total_ativos = len(df_filtrado)
            em_producao = len(df_filtrado[df_filtrado["status"] == "Em Produção"])
            garantias_vencidas = len(df_filtrado[df_filtrado["fim_garantia"] < hoje])
            
            limite_obsolescencia = hoje - pd.DateOffset(years=5)
            equipamentos_antigos = len(df_filtrado[df_filtrado["data_compra"] < limite_obsolescencia])
            
            # Exibição dos KPIs atualizados
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ativos Filtrados", total_ativos)
            col2.metric("Em Produção", em_producao)
            col3.metric("🚨 Garantias Vencidas", garantias_vencidas, delta=f"{garantias_vencidas} pendente(s)" if garantias_vencidas > 0 else None, delta_color="inverse")
            col4.metric("⚠️ Ciclo Crítico (>5 anos)", equipamentos_antigos, delta="Substituição Recomendada" if equipamentos_antigos > 0 else None, delta_color="off")
            
            st.markdown("---")
            
            # Gráficos baseados nos dados filtrados
            cg1, cg2 = st.columns(2)
            with cg1:
                st.write("#### Equipamentos por Tipo")
                st.bar_chart(df_filtrado["tipo"].value_counts())
            with cg2:
                st.write("#### Status dos Ativos")
                st.bar_chart(df_filtrado["status"].value_counts())
                
            st.markdown("---")
            st.write("#### 📋 Inventário Filtrado")
            
            # Formatação final para exibição limpa da tabela
            df_exibicao = df_filtrado.copy()
            df_exibicao["fim_garantia"] = df_exibicao["fim_garantia"].dt.strftime('%d/%m/%Y')
            df_exibicao["data_compra"] = df_exibicao["data_compra"].dt.strftime('%d/%m/%Y')
            st.dataframe(df_exibicao, use_container_width=True)