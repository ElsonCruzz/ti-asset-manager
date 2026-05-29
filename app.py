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
    """Inicializa e cacheia a conexão com o Supabase."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"Erro de configuração: {e} não encontrado em st.secrets.")
        st.stop()

supabase = init_connection()

# --- FUNÇÕES DE BANCO DE DADOS (QUERIES E INSERÇÕES) ---

def listar_empresas() -> pd.DataFrame:
    """Busca todas as empresas para os filtros e cadastros."""
    try:
        response = supabase.table("empresas").select("id, nome_fantasia, status_contrato").order("nome_fantasia").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao carregar empresas: {e}")
        return pd.DataFrame()

def listar_locais(empresa_id: str) -> pd.DataFrame:
    """Busca locais filtrados por uma empresa específica."""
    try:
        response = supabase.table("locais").select("id, nome").eq("empresa_id", empresa_id).order("nome").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao carregar locais: {e}")
        return pd.DataFrame()

def carregar_dashboard_dados(empresa_id: str = None) -> pd.DataFrame:
    """Busca ativos aplicando o filtro mestre de empresa, se houver."""
    try:
        query = supabase.table("ativos").select(
            "id, tipo, fabricante, modelo, numero_serie, status, fim_garantia, locais(nome)"
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

# Filtro Mestre de Empresa (Aparece apenas se houver empresas cadastradas)
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

# --- MENU 1: DASHBOARD GERAL ---
if menu == "📊 Dashboard Geral":
    st.title("📊 Dashboard Geral de Infraestrutura")
    st.caption(f"Visualizando escopo: **{opcao_filtro}**")
    st.markdown("---")
    
    df_ativos = carregar_dashboard_dados(empresa_selecionada_id)
    
    if df_ativos.empty:
        st.info("Nenhum equipamento cadastrado neste escopo. Vá até a aba de cadastros para começar!")
    else:
        # KPIs
        total_ativos = len(df_ativos)
        em_producao = len(df_ativos[df_ativos["status"] == "Em Produção"])
        em_manutencao = len(df_ativos[df_ativos["status"] == "Manutenção"])
        
        df_ativos["fim_garantia"] = pd.to_datetime(df_ativos["fim_garantia"])
        hoje = pd.Timestamp.now().normalize()
        garantias_vencidas = len(df_ativos[df_ativos["fim_garantia"] < hoje])
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Ativos", total_ativos)
        col2.metric("Em Produção", em_producao)
        col3.metric("🚨 Garantias Vencidas", garantias_vencidas, delta=f"{garantias_vencidas} pendente(s)" if garantias_vencidas > 0 else None, delta_color="inverse")
        col4.metric("🔧 Em Manutenção", em_manutencao)
        
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
        st.dataframe(df_exibicao, use_container_width=True)

# --- MENU 2: CADASTRO DE CLIENTE E LOCAL ---
elif menu == "🏢 Cadastrar Cliente/Local":
    st.title("🏢 Gestão de Contratos e Locais")
    
    aba_empresa, aba_local = st.tabs(["➕ Nova Empresa/Contrato", "📍 Novo Local/Site"])
    
    with aba_empresa:
        st.subheader("Cadastrar Novo Cliente Contratante")
        with st.form("form_empresa", clear_on_submit=True):
            nome_fantasia = st.text_input("Nome Fantasia:*")
            razao_social = st.text_input("Razão Social:")
            cnpj = st.text_input("CNPJ:")
            status = st.selectbox("Status do Contrato:", ["Ativo", "Inativo", "Suspenso"])
            
            if st.form_submit_button("Salvar Empresa"):
                if nome_fantasia.strip():
                    try:
                        dados = {"nome_fantasia": nome_fantasia.strip(), "razao_social": razao_social.strip(), "cnpj": cnpj.strip(), "status_contrato": status}
                        supabase.table("empresas").insert(dados).execute()
                        st.success(f"Empresa '{nome_fantasia}' cadastrada com sucesso! Recarregue a página.")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.warning("O campo Nome Fantasia é obrigatório.")
                    
    with aba_local:
        st.subheader("Cadastrar Local Físico (Onde os equipamentos ficam)")
        if df_empresas.empty:
            st.warning("Cadastre uma empresa primeiro antes de criar um local.")
        else:
            with st.form("form_local", clear_on_submit=True):
                empresa_nome = st.selectbox("Vincular à Empresa:", df_empresas["nome_fantasia"].tolist())
                emp_id = df_empresas[df_empresas["nome_fantasia"] == empresa_nome]["id"].values[0]
                
                nome_local = st.text_input("Nome do Local:* (Ex: DataCenter 1, Filial Centro, CPD)")
                descricao_local = st.text_area("Descrição/Observações:")
                
                if st.form_submit_button("Salvar Local"):
                    if nome_local.strip():
                        try:
                            dados = {"empresa_id": emp_id, "nome": nome_local.strip(), "descricao": descricao_local.strip()}
                            supabase.table("locais").insert(dados).execute()
                            st.success(f"Local '{nome_local}' vinculado à empresa com sucesso!")
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                    else:
                        st.warning("O campo Nome do Local é obrigatório.")

# --- MENU 3: CADASTRO DE EQUIPAMENTO ---
elif menu == "🖥️ Cadastrar Equipamento":
    st.title("🖥️ Cadastro de Ativos de Infraestrutura")
    
    if df_empresas.empty:
        st.warning("Você precisa cadastrar pelo menos uma Empresa e um Local antes de inserir equipamentos.")
    else:
        # Seleção dinâmica de Empresa e seus respectivos Locais
        col_emp, col_loc = st.columns(2)
        with col_emp:
            emp_escolhida = st.selectbox("Equipamento pertence à qual cliente?", df_empresas["nome_fantasia"].tolist())
            id_da_empresa = df_empresas[df_empresas["nome_fantasia"] == emp_escolhida]["id"].values[0]
        
        df_locais_filtrados = listar_locais(id_da_empresa)
        
        with col_loc:
            if df_locais_filtrados.empty:
                st.error("⚠️ Este cliente não tem nenhum local cadastrado. Cadastre um local antes.")
                local_escolhido_id = None
            else:
                local_escolhido_nome = st.selectbox("Em qual local físico ele está?", df_locais_filtrados["nome"].tolist())
                local_escolhido_id = df_locais_filtrados[df_locais_filtrados["nome"] == local_escolhido_nome]["id"].values[0]

        if local_escolhido_id:
            st.markdown("---")
            with st.form("form_ativo", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                tipo = c1.selectbox("Tipo de Ativo:*", ["Servidor", "Switch", "Firewall", "Roteador", "Storage", "Nobreak", "Acess Point", "Outro"])
                fabricante = c2.text_input("Fabricante:* (Ex: Dell, Cisco, Fortinet)")
                modelo = c3.text_input("Modelo:* (Ex: PowerEdge R740, Catalyst 2960)")
                
                c4, c5 = st.columns(2)
                num_serie = c4.text_input("Número de Série / Service Tag:*")
                patrimonio = c5.text_input("Patrimônio Interno (Opcional):")
                
                c6, c7, c8 = st.columns(3)
                data_compra = c6.date_input("Data de Compra:", value=None)
                fim_garantia = c7.date_input("Fim da Garantia:", value=None)
                status_ativo = c8.selectbox("Status Operacional:", ["Em Produção", "Estoque/Backup", "Manutenção", "Desativado"])
                
                st.subheader("🌐 Configuração de Rede (Opcional)")
                c9, c10, c11 = st.columns(3)
                ip_local = c9.text_input("IP Local (Ex: 192.168.1.10)")
                mac = c10.text_input("Endereço MAC")
                vlan = c11.number_input("VLAN ID", min_value=0, max_value=4096, value=0)
                
                obs = st.text_area("Observações Técnicas:")
                
                if st.form_submit_button("Cadastrar Equipamento"):
                    if fabricante.strip() and modelo.strip() and num_serie.strip():
                        try:
                            # 1. Salva o Ativo
                            dados_ativo = {
                                "empresa_id": id_da_empresa, "local_id": local_chosen_id := local_escolhido_id,
                                "tipo": tipo, "fabricante": fabricante.strip(), "modelo": modelo.strip(),
                                "numero_serie": num_serie.strip(), "patrimonio_interno": patrimonio.strip(),
                                "data_compra": str(data_compra) if data_compra else None,
                                "fim_garantia": str(fim_garantia) if fim_garantia else None,
                                "status": status_ativo, "observacoes": obs.strip()
                            }
                            res_ativo = supabase.table("ativos").insert(dados_ativo).execute()
                            id_ativo_criado = res_ativo.data[0]["id"]
                            
                            # 2. Salva a Rede se algum campo foi preenchido
                            if ip_local.strip() or mac.strip() or vlan > 0:
                                dados_rede = {
                                    "ativo_id": id_ativo_criado, "ip_local": ip_local.strip(),
                                    "mac_address": mac.strip(), "vlan_id": vlan if vlan > 0 else None
                                }
                                supabase.table("redes").insert(dados_rede).execute()
                                
                            st.success(f"Equipamento {tipo} {fabricante} cadastrado com sucesso!")
                        except Exception as e:
                            st.error(f"Erro ao inserir ativo: {e}")
                    else:
                        st.warning("Por favor, preencha todos os campos obrigatórios (*).")