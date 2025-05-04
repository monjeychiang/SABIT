### 系統安全

#### 多層防禦架構

1. **網絡層安全**
   - DDoS防護
   - Web應用防火牆(WAF)
   - 流量加密(TLS 1.3)
   - IP白名單機制
   - 異常流量檢測與阻斷

2. **應用層安全**
   - OWASP Top 10防護
   - 輸入驗證和消毒
   - 防SQL注入
   - 防XSS攻擊
   - CSRF保護
   - 防止參數篡改
   - API速率限制

3. **認證與授權**
   - 多因素認證(MFA)
   - 基於角色的訪問控制(RBAC)
   - JWT令牌管理
   - 會話超時控制
   - 最小權限原則
   - IP綁定和異常檢測

4. **數據安全**
   - 數據傳輸加密(TLS)
   - 數據存儲加密(AES-256)
   - 資產冷熱錢包分離
   - 私鑰多重簽名
   - 數據備份和災難恢復
   - 敏感數據脫敏

#### 密碼學安全措施

- 密碼使用Argon2加密存儲
- 加密密鑰安全管理
- 定期密鑰輪換
- 硬件安全模塊(HSM)保護私鑰
- 完美前向保密(PFS)

### 安全開發生命週期(SDLC)

- 安全需求分析
- 威脅建模
- 安全設計審查
- 安全編碼實踐
- 靜態應用安全測試(SAST)
- 動態應用安全測試(DAST)
- 滲透測試
- 依賴項掃描
- 代碼審查

### 安全監控與審計

- 實時安全監控
- 全面日誌記錄與審計
- 異常行為檢測
- 安全事件與事故響應
- 定期安全評估
- 第三方安全審計

### 合規框架

系統設計遵循多個國際和區域的合規要求：

#### 國際標準

- **ISO/IEC 27001**: 信息安全管理
- **ISO/IEC 27017**: 雲服務信息安全
- **ISO/IEC 27018**: 個人數據保護
- **PCI DSS**: 支付卡行業數據安全標準
- **GDPR**: 歐盟通用數據保護條例

#### 加密貨幣特定規定

- **FATF旅行規則**: 虛擬資產服務提供商(VASP)合規
- **KYC/AML流程**: 了解您的客戶和反洗錢程序
- **市場操縱監控**: 檢測並防止市場操縱行為

#### 系統審計與合規報告

- 定期系統安全審計
- 合規性自我評估
- 第三方滲透測試
- SOC 2 Type II報告
- 合規性證明和認證

### 漏洞管理

- **漏洞報告計劃**:
  - 公開漏洞報告渠道
  - 漏洞懸賞計劃
  - 安全研究人員合作

- **漏洞響應流程**:
  - 漏洞分類與優先級
  - 及時修補
  - 安全更新發布
  - 漏洞披露政策

### 安全配置示例

#### Nginx安全配置

```nginx
# 增強的Nginx安全配置示例
server {
    listen 443 ssl http2;
    server_name example.com;

    # SSL配置
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # 現代TLS配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS (31536000秒 = 1年)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 其他安全頭
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://trusted-cdn.com; img-src 'self' data: https://trusted-cdn.com; style-src 'self' https://trusted-cdn.com; font-src 'self' https://trusted-cdn.com; connect-src 'self'; frame-ancestors 'none'; form-action 'self';";

    # 防止緩存敏感數據
    add_header Cache-Control "no-store, no-cache, must-revalidate";
    
    # 配置API代理
    location /api/ {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 請求大小限制
        client_max_body_size 10m;
        
        # 超時設置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 速率限制
        limit_req zone=api_limit burst=20 nodelay;
    }
    
    # 靜態文件緩存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
        access_log off;
    }
    
    # 拒絕訪問隱藏文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}

# 定義速率限制區域
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```

#### ModSecurity WAF規則示例

```conf
# 啟用ModSecurity
SecRuleEngine On

# 基本設置
SecRequestBodyAccess On
SecResponseBodyAccess On
SecResponseBodyMimeType text/plain text/html text/xml application/json
SecResponseBodyLimit 1024

# 包含OWASP核心規則集
Include /etc/nginx/modsecurity.d/owasp-crs/crs-setup.conf
Include /etc/nginx/modsecurity.d/owasp-crs/rules/*.conf

# 自定義規則 - SQL注入防護加強
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_HEADERS|ARGS_NAMES|ARGS|XML:/* "@rx (?i:(?:s(?:e(?:lect\s+(?:(?:group_)?concat|(?:distinct|all)\s+(?!.*\bcase\b))|\s*?[^\w\s])|p\s*?[^\w\s]|\w+\s*?(?:(?:between|and|or|union|intersect|minus)\s|\bxor\b|\|\||\&\&))|t(?:o(?:_(?:(?:su|nu)mber|cha(?:r(?:acter)?)?|date)|p\s+\d+)|r(?:uncate|im))|i(?:n(?:s(?:ert(?:(?:\s+(?:all|distinct))?(?:\s+(?:into(?:\s+outfile)?|\boverwrite\b))?)|ert\s+(?:into|executable))|to\s+(?:dump|out)file)|f\s+(?:\d+|null|(?:(?:not\s+)?null))|dentified\s+by)|like(?:\s+(?:binary)?)?|\bsi(?:imilar\s*to|gn)\b|c(?:o(?:(?:py\b|nstraint)(?!\s*\()|mment(?:\s|')(?!\*))|ur(?:rent_(?:timestamp|date|user|time)|date|_(?:time|date|timestamp|user))|h(?:ar(?:(?:acter)?_length|\b)|\bksum)|ase(?!\s*\()|ast)|d(?:e(?:(?:c(?:lare\s+(?:[^\s]+\s+)?cursor|imal)|fault|sc(?:ribe)?|lete(?:\s+from)?)\b|code)|ate(?:_(?:format|add)|\s*\()|ump)|group\s+by|having|e(?:xec(?:ute(?:\s+immediate)?)?|x(?:tract|ists)|lse)|v(?:a(?:r(?:(?:binary|char\d*)\b|iant)|lues)|ersion)|s(?:ession_user|y(?:s(?:tem(?:_user|\b)|date|_connect_by_path)|ndex)|elect\s+(?!into\s+(?:outfile|dumpfile|variable))|ome|p_(?:executesql|password|sqlexec|addextendedproc|prepare|rename|makewebtask|help)|ql_(?:(?:(?:dump|big_)table|longvarchar)|variant))|p(?:r(?:o(?:c(?:edure(?:_(?:analyse|params))?|ess(?:list)?)|file)|epare)|osition(?!\s*\()|assword|ublic)|order\s+by|u(?:nion\s+(?:all|distinct|select)|pdate|ername|id)|left(?:\s+(?:join|outer))?|trim(?!\s*\()|x(?:p_(?:cmdshell|terminate|api)|o(?:r(?:_)?)?)|r(?:e(?:(?:place|store|al)|voke|gexp|ad)|ight\s+(?:join|outer)|ow_count|and(?:om)?)|limit(?!\s*\()|waitfor|a(?:s(?:c(?:ii(?!\s*\()|i)?|signment)|tt(?:ach(?:\s+database)?|ributes)|dd(?:date|time))|between|md5(?!\s*\()|field(?:id)?|print(?!\s*\()|while|uid|grant(?:\s+(?:option|privileges|view))?|master(?:\.dbo)?|benchmark|columns?|create(?:\s+(?:unique\s+index|or\s+replace|database|table|view))?|nvarchar|t(?:able(?:_(?:name|schema))?|hen|o_(?:cha(?:r(?:acter)?|r_base64)|days|second|binary|number))|inner\s+join|end(?:if)?|with(?:\s+(?:cube|ties))?|from(?:\s+dual)?|where|u(?:se(?!\s*\()|tf(?:-)?8)|open(?:rowset|query)?))" \
    "id:1000001,phase:2,block,msg:'SQL Injection Attack Detected',logdata:'%{MATCHED_VAR}',severity:'2'"

# 自定義規則 - 加密貨幣地址保護
SecRule REQUEST_HEADERS:User-Agent "@rx ^(?:curl|wget|python-requests)" \
    "id:1000002,phase:1,block,msg:'API自動化工具訪問限制',severity:'2'"

# 自定義規則 - API速率限制增強
SecAction \
    "id:1000003,phase:1,pass,initcol:ip=%{REMOTE_ADDR},initcol:timestamp=%{TIME_EPOCH},nolog"

SecRule IP:REQUESTS "@gt 100" \
    "id:1000004,phase:1,block,msg:'API請求速率過高',logdata:'%{REMOTE_ADDR} 在60秒內發送了 %{IP:REQUESTS} 個請求',setvar:ip.blocked=1,expirevar:ip.blocked=60,severity:'2'"

# 保護加密錢包地址不被泄露
SecRule RESPONSE_BODY "@rx \b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b" \
    "id:1000005,phase:4,block,msg:'可能的比特幣地址洩露',severity:'2'"

SecRule RESPONSE_BODY "@rx \b0x[a-fA-F0-9]{40}\b" \
    "id:1000006,phase:4,block,msg:'可能的以太坊地址洩露',severity:'2'"
```

#### 安全頭配置

```python
# FastAPI安全頭配置示例
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# 限制主機頭
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["api.example.com", "*.example.com"]
)

# 壓縮響應
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS設置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# 會話安全
app.add_middleware(
    SessionMiddleware, 
    secret_key="YOUR_SECRET_KEY_HERE",
    max_age=1800,  # 30分鐘
    same_site="lax",
    https_only=True
)

# 安全頭中間件
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # 安全頭設置
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    
    return response
```

### 安全應急響應計劃

為確保在發生安全事件時能夠迅速有效地響應，系統實施了全面的安全應急響應計劃：

1. **事件檢測與分類**
   - 24/7安全監控
   - 事件嚴重性分級
   - 自動化告警機制

2. **響應團隊與職責**
   - 安全響應團隊(CSIRT)組織結構
   - 明確的職責分配
   - 上報機制

3. **包含事件處理流程**
   - 遏制措施
   - 風險評估
   - 根本原因分析
   - 移除威脅
   - 恢復服務
   - 事後審查

4. **溝通策略**
   - 內部通知流程
   - 用戶通知機制
   - 監管機構報告
   - 公共關係聲明

5. **業務連續性**
   - 備份與恢復程序
   - 故障轉移機制
   - 災難恢復計劃

// ... existing code ...