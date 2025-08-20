## 📈 StockTogether | 당신을 위한 투자 순간, 흩어지지 않게 (MVP)

**“어제 본 뉴스, 오늘의 공시… 흩어진 정보를 한눈에 모아드립니다.”**

* **수집**: Yahoo Finance MCP로 뉴스·공시·시세를 실시간 가져와요.
* **정리**: 중복된 기사와 오래된 소식은 정리하고, 신뢰도와 최신성으로 랭킹해요.
* **분석**: AI가 요약하고 감성·영향 스코어(0\~100)로 직관적인 인사이트를 드려요.

---

### 🎯 시나리오 1 — 단일 종목 뉴스·공시 스코어

* 종목 입력 → 최신 뉴스·공시 자동 수집
* AI가 요약 + 긍/부정 감성 분석
* **투자 영향 점수**로 빠르게 분위기 파악

---

### 🛠️ 기술 스택

* **Frontend**: Next.js (A2A Client → Agent 호출)
* **Backend(Agent)**: FastAPI (A2A Server + MCP Client)
* **Data Source**: Yahoo Finance MCP Server
* **AI 분석**: Clova Studio LLM