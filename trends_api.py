from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pytrends.request import TrendReq
import pandas as pd
import sqlite3
import json
import time

app = FastAPI(
    title="GeoTrend Trends API",
    description="API de análise de tendências geolocalizado para São Paulo com dados do Google Trends."
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do banco de dados
DB_PATH = "trends_data.db"

# Bairros de São Paulo com coordenadas aproximadas
BAIRROS_SP = {
    "Centro": {"lat": -23.5505, "lon": -46.6333, "region_code": "SP-Centro"},
    "Saúde": {"lat": -23.6049, "lon": -46.6353, "region_code": "SP-Saúde"},
    "Pinheiros": {"lat": -23.5617, "lon": -46.6865, "region_code": "SP-Pinheiros"},
    "Vila Madalena": {"lat": -23.5726, "lon": -46.7036, "region_code": "SP-VilaMadalena"},
    "Jardins": {"lat": -23.5505, "lon": -46.6333, "region_code": "SP-Jardins"},
    "Consolação": {"lat": -23.5568, "lon": -46.6597, "region_code": "SP-Consolação"},
    "Bela Vista": {"lat": -23.5548, "lon": -46.6597, "region_code": "SP-BelaVista"},
    "Liberdade": {"lat": -23.5603, "lon": -46.6361, "region_code": "SP-Liberdade"},
    "Tatuapé": {"lat": -23.5341, "lon": -46.5476, "region_code": "SP-Tatuapé"},
    "Mooca": {"lat": -23.5526, "lon": -46.6017, "region_code": "SP-Mooca"},
    "Ipiranga": {"lat": -23.6149, "lon": -46.6149, "region_code": "SP-Ipiranga"},
    "Penha": {"lat": -23.5341, "lon": -46.5476, "region_code": "SP-Penha"},
    "Zona Leste": {"lat": -23.5341, "lon": -46.4476, "region_code": "SP-ZonaLeste"},
    "Zona Oeste": {"lat": -23.5341, "lon": -46.8476, "region_code": "SP-ZonaOeste"},
    "Zona Norte": {"lat": -23.4341, "lon": -46.6476, "region_code": "SP-ZonaNorte"},
    "Zona Sul": {"lat": -23.6341, "lon": -46.6476, "region_code": "SP-ZonaSul"},
}

def init_db():
    """Inicializar o banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trends_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            bairro TEXT NOT NULL,
            interest_value INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            periodo TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trend_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            bairro_recomendado TEXT NOT NULL,
            razao TEXT,
            crescimento_potencial REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Modelos
class TrendRequest(BaseModel):
    keyword: str
    periodo: str = "24h"  # 24h, 7d, 30d

class TrendResponse(BaseModel):
    bairro: str
    keyword: str
    interest_value: int
    crescimento_potencial: float
    recomendacao: Optional[str] = None

def obter_trends_google(keyword: str) -> Dict:
    """Obtém dados do Google Trends para uma palavra-chave."""
    try:
        pytrends = TrendReq(hl='pt-BR', tz=360)
        
        # Buscar interesse ao longo do tempo
        pytrends.build_payload([keyword], cat=0, timeframe='now 1-d', geo='BR-SP')
        
        # Obter dados de interesse por hora
        interest_over_time = pytrends.interest_over_time()
        
        # Obter interesse por região (se disponível)
        pytrends.build_payload([keyword], cat=0, timeframe='now 1-d', geo='BR-SP')
        interest_by_region = pytrends.interest_by_region()
        
        return {
            "keyword": keyword,
            "interest_over_time": interest_over_time,
            "interest_by_region": interest_by_region,
            "status": "sucesso"
        }
    except Exception as e:
        print(f"Erro ao obter dados do Google Trends: {str(e)}")
        return {
            "keyword": keyword,
            "status": "erro",
            "mensagem": str(e)
        }

def simular_distribuicao_bairros(keyword: str, interest_value: int) -> Dict[str, int]:
    """
    Simula a distribuição de interesse entre bairros de São Paulo.
    Em produção, isso seria baseado em dados reais de geolocalização.
    """
    # Distribuição simulada (em produção, seria baseada em dados reais)
    distribuicao = {
        "Centro": int(interest_value * 0.15),
        "Saúde": int(interest_value * 0.12),
        "Pinheiros": int(interest_value * 0.14),
        "Vila Madalena": int(interest_value * 0.10),
        "Jardins": int(interest_value * 0.13),
        "Consolação": int(interest_value * 0.08),
        "Bela Vista": int(interest_value * 0.06),
        "Liberdade": int(interest_value * 0.05),
        "Zona Leste": int(interest_value * 0.10),
        "Zona Oeste": int(interest_value * 0.05),
        "Zona Norte": int(interest_value * 0.04),
        "Zona Sul": int(interest_value * 0.03),
    }
    
    return distribuicao

def salvar_trends_no_db(keyword: str, distribuicao: Dict[str, int], periodo: str):
    """Salva os dados de tendências no banco de dados."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for bairro, interest_value in distribuicao.items():
        cursor.execute("""
            INSERT INTO trends_data (keyword, bairro, interest_value, periodo)
            VALUES (?, ?, ?, ?)
        """, (keyword.lower().strip(), bairro, interest_value, periodo))
    
    conn.commit()
    conn.close()

def gerar_recomendacoes(keyword: str, distribuicao: Dict[str, int]) -> List[Dict]:
    """Gera recomendações de bairros para anúncios direcionados."""
    recomendacoes = []
    
    # Ordenar bairros por interesse
    bairros_ordenados = sorted(distribuicao.items(), key=lambda x: x[1], reverse=True)
    
    # Top 3 bairros com maior interesse
    for idx, (bairro, interest) in enumerate(bairros_ordenados[:3]):
        if idx == 0:
            razao = f"Maior interesse em {keyword} em SP"
            crescimento = 100.0
        elif idx == 1:
            razao = f"Segundo maior interesse em {keyword}"
            crescimento = 85.0
        else:
            razao = f"Terceiro maior interesse em {keyword}"
            crescimento = 70.0
        
        recomendacoes.append({
            "bairro": bairro,
            "razao": razao,
            "crescimento_potencial": crescimento,
            "interesse_atual": interest
        })
    
    return recomendacoes

@app.post("/analisar-tendencia")
async def analisar_tendencia(request: TrendRequest):
    """Analisa uma tendência e retorna insights por bairro."""
    
    # Obter dados do Google Trends
    trends_data = obter_trends_google(request.keyword)
    
    if trends_data["status"] == "erro":
        raise HTTPException(status_code=400, detail=trends_data["mensagem"])
    
    # Simular valor de interesse (em produção, seria do Google Trends)
    interest_value = 75  # Valor simulado entre 0-100
    
    # Distribuir entre bairros
    distribuicao = simular_distribuicao_bairros(request.keyword, interest_value)
    
    # Salvar no banco de dados
    salvar_trends_no_db(request.keyword, distribuicao, request.periodo)
    
    # Gerar recomendações
    recomendacoes = gerar_recomendacoes(request.keyword, distribuicao)
    
    return {
        "keyword": request.keyword,
        "periodo": request.periodo,
        "distribuicao_bairros": distribuicao,
        "recomendacoes": recomendacoes,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/tendencias-por-bairro/{bairro}")
def tendencias_por_bairro(bairro: str, periodo: str = Query("24h")):
    """Retorna as tendências para um bairro específico."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT keyword, interest_value, timestamp FROM trends_data
        WHERE bairro = ? AND periodo = ?
        ORDER BY timestamp DESC
        LIMIT 10
    """, (bairro, periodo))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"bairro": bairro, "tendencias": []}
    
    tendencias = [
        {
            "keyword": row[0],
            "interest_value": row[1],
            "timestamp": row[2]
        }
        for row in rows
    ]
    
    return {"bairro": bairro, "tendencias": tendencias}

@app.get("/top-tendencias")
def top_tendencias(limite: int = Query(5), periodo: str = Query("24h")):
    """Retorna as top tendências em São Paulo."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT keyword, SUM(interest_value) as total_interest FROM trends_data
        WHERE periodo = ?
        GROUP BY keyword
        ORDER BY total_interest DESC
        LIMIT ?
    """, (periodo, limite))
    
    rows = cursor.fetchall()
    conn.close()
    
    tendencias = [
        {
            "keyword": row[0],
            "total_interest": row[1]
        }
        for row in rows
    ]
    
    return {"top_tendencias": tendencias, "periodo": periodo}

@app.get("/recomendacoes/{keyword}")
def obter_recomendacoes(keyword: str):
    """Retorna recomendações de bairros para anunciar um produto/serviço."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT bairro, razao, crescimento_potencial FROM trend_recommendations
        WHERE keyword = ?
        ORDER BY crescimento_potencial DESC
    """, (keyword.lower().strip(),))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        # Se não houver recomendações salvas, gerar novas
        trends_data = obter_trends_google(keyword)
        distribuicao = simular_distribuicao_bairros(keyword, 75)
        recomendacoes = gerar_recomendacoes(keyword, distribuicao)
        
        return {
            "keyword": keyword,
            "recomendacoes": recomendacoes,
            "tipo": "gerada_dinamicamente"
        }
    
    recomendacoes = [
        {
            "bairro": row[0],
            "razao": row[1],
            "crescimento_potencial": row[2]
        }
        for row in rows
    ]
    
    return {"keyword": keyword, "recomendacoes": recomendacoes}

@app.get("/dashboard-clinica/{clinica_id}")
def dashboard_clinica(clinica_id: str, bairro_atuacao: str = Query("Saúde")):
    """
    Dashboard específico para uma clínica.
    Mostra tendências na região onde ela atua e recomendações de expansão.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tendências no bairro onde a clínica atua
    cursor.execute("""
        SELECT keyword, interest_value FROM trends_data
        WHERE bairro = ?
        ORDER BY interest_value DESC
        LIMIT 5
    """, (bairro_atuacao,))
    
    tendencias_atuacao = [
        {
            "keyword": row[0],
            "interest_value": row[1]
        }
        for row in cursor.fetchall()
    ]
    
    # Tendências em bairros vizinhos (oportunidades de expansão)
    cursor.execute("""
        SELECT DISTINCT bairro, keyword, interest_value FROM trends_data
        WHERE bairro != ? AND interest_value > 50
        ORDER BY interest_value DESC
        LIMIT 5
    """, (bairro_atuacao,))
    
    oportunidades_expansao = [
        {
            "bairro": row[0],
            "keyword": row[1],
            "interest_value": row[2]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    
    return {
        "clinica_id": clinica_id,
        "bairro_atuacao": bairro_atuacao,
        "tendencias_atuacao": tendencias_atuacao,
        "oportunidades_expansao": oportunidades_expansao,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
def raiz():
    """Endpoint raiz para verificar o status da API."""
    return {
        "servico": "GeoTrend Trends API",
        "status": "online",
        "versao": "1.0",
        "descricao": "Análise de tendências geolocalizado para São Paulo",
        "endpoints": {
            "analisar_tendencia": "POST /analisar-tendencia",
            "tendencias_por_bairro": "GET /tendencias-por-bairro/{bairro}",
            "top_tendencias": "GET /top-tendencias",
            "recomendacoes": "GET /recomendacoes/{keyword}",
            "dashboard_clinica": "GET /dashboard-clinica/{clinica_id}"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
