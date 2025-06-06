import base64
import logging
import os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import nacl.signing
import nacl.encoding

logger = logging.getLogger(__name__)

class Ed25519KeyManager:
    """
    Ed25519密鑰管理器
    
    用於生成和管理用於幣安WebSocket API的Ed25519密鑰對
    """
    
    def __init__(self, generate_key_pair=False):
        """
        初始化Ed25519密鑰管理器
        
        Args:
            generate_key_pair: 是否生成新的密鑰對，默認為不生成
        """
        self.private_key = None
        self.public_key = None
        self.signing_key = None
        self.verify_key = None
        
        if generate_key_pair:
            logger.info("生成新的Ed25519鑰匙對")
            self._generate_key_pair()
    
    def _generate_key_pair(self):
        """生成新的Ed25519密鑰對"""
        # 生成密鑰對
        self.signing_key = nacl.signing.SigningKey.generate()
        self.verify_key = self.signing_key.verify_key
        
        # 提取密鑰值
        self.private_key = base64.b64encode(self.signing_key.encode()).decode('utf-8')
        self.public_key = base64.b64encode(self.verify_key.encode()).decode('utf-8')
        
        logger.debug(f"生成的Ed25519公鑰: {self.public_key[:10]}...")
    
    def is_pem_format(self, key_data: str) -> bool:
        """
        檢查是否為 PEM 格式密鑰
        
        PEM 格式特徵:
        1. 以 "-----BEGIN" 開頭
        2. 以 "-----END" 結尾
        3. 中間為 Base64 編碼數據
        
        Args:
            key_data: 待檢查的密鑰數據
        
        Returns:
            是否為 PEM 格式
        """
        return key_data.strip().startswith("-----BEGIN") and key_data.strip().endswith("-----")
    
    def extract_key_from_pem(self, pem_key: str) -> bytes:
        """
        從 PEM 格式提取實際的密鑰數據
        
        PEM 格式密鑰結構:
        -----BEGIN PRIVATE KEY-----
        Base64編碼的數據（可能有多行）
        -----END PRIVATE KEY-----
        
        Args:
            pem_key: PEM 格式密鑰
        
        Returns:
            解析後的實際密鑰數據
        """
        logger.debug("開始從 PEM 格式提取密鑰數據")
        
        # 移除頭尾標記和空白
        lines = pem_key.strip().split('\n')
        if len(lines) < 3:
            raise ValueError("不符合 PEM 格式標準")
            
        # 提取 Base64 數據（跳過第一行和最後一行）
        base64_data = ''.join(lines[1:-1]).replace(' ', '')
        logger.debug(f"PEM 內部 Base64 數據長度: {len(base64_data)}")
        
        # 解碼 Base64 數據
        try:
            decoded_data = base64.b64decode(base64_data)
            logger.debug(f"從 PEM 解碼後的數據長度: {len(decoded_data)} 字節")
            
            # 處理 PKCS#8 格式
            if len(decoded_data) == 48:
                logger.info("檢測到 PKCS#8 格式的 Ed25519 私鑰 (48 字節)")
                
                # 從 ASN.1 結構中提取實際的 Ed25519 私鑰
                # PKCS#8 格式的 Ed25519 私鑰在字節偏移 16 處的 32 字節是實際密鑰
                actual_key = decoded_data[16:]
                
                # 驗證提取的密鑰
                try:
                    test_key = nacl.signing.SigningKey(actual_key)
                    logger.debug(f"從 PEM/PKCS#8 格式成功提取出 {len(actual_key)} 字節的 Ed25519 私鑰")
                    return actual_key
                except Exception as e:
                    logger.warning(f"從 PEM/PKCS#8 格式提取私鑰驗證失敗: {str(e)}")
            elif len(decoded_data) == 32:
                # 標準 Ed25519 私鑰長度
                logger.debug("從 PEM 格式提取出標準 32 字節長度的 Ed25519 私鑰")
                return decoded_data
            else:
                # 對於其他長度，嘗試找到有效的部分
                logger.warning(f"從 PEM 格式提取出的數據長度 ({len(decoded_data)} 字節) 非標準")
                
                # 嘗試多種可能的情況
                if len(decoded_data) > 32:
                    # 對於較長的密鑰，嘗試末尾的 32 字節
                    key_candidate = decoded_data[-32:]
                    try:
                        test_key = nacl.signing.SigningKey(key_candidate)
                        logger.info(f"使用 PEM 解碼數據末尾的 32 字節作為有效私鑰")
                        return key_candidate
                    except Exception:
                        pass
                    
                    # 嘗試開頭的 32 字節
                    key_candidate = decoded_data[:32]
                    try:
                        test_key = nacl.signing.SigningKey(key_candidate)
                        logger.info(f"使用 PEM 解碼數據開頭的 32 字節作為有效私鑰")
                        return key_candidate
                    except Exception:
                        pass
            
            # 如果無法明確確定，返回整個解碼數據，讓後續流程嘗試處理
            logger.warning("無法從 PEM 格式確定準確的私鑰部分，返回完整解碼數據")
            return decoded_data
            
        except Exception as e:
            logger.error(f"PEM 格式密鑰的 Base64 解碼失敗: {str(e)}")
            raise ValueError(f"PEM 格式密鑰錯誤: {str(e)}")
    
    def sign_message(self, message: str, private_key: str = None) -> str:
        """
        使用Ed25519私鑰簽名消息
        
        優先支持 PEM 格式的私鑰 (帶 -----BEGIN PRIVATE KEY----- 標記)
        其次支持 Base64 格式的私鑰 (可能包含 +, /, = 符號)
        特別處理 PKCS#8 格式的 Ed25519 私鑰 (解碼後通常為 48 字節)
        也支持其他格式：
        1. 十六進制格式 (64字符)
        2. 原始字符串格式
        
        Args:
            message: 要簽名的消息
            private_key: 用於簽名的私鑰，如果為None則使用實例的私鑰
        
        Returns:
            Base64編碼的簽名
        """
        # 創建安全的日誌字符串，隱藏敏感信息
        safe_message = message
        if len(message) > 20:
            # 只顯示消息的前20個字符，後面用省略號替換
            safe_message = message[:20] + "..."
            
            # 進一步檢查是否包含API密鑰相關內容
            if "apiKey=" in message:
                parts = message.split("apiKey=")
                if len(parts) > 1:
                    # 找到apiKey的值
                    api_key_part = parts[1].split("&")[0]
                    # 替換為遮蔽版本
                    if len(api_key_part) > 8:
                        masked_key = api_key_part[:8] + "..."
                        safe_message = message.replace(api_key_part, masked_key)
        
        logger.debug(f"使用 Ed25519 簽名消息: {safe_message}")
        
        # 如果提供了私鑰，使用它；否則使用實例的私鑰
        key_to_use = private_key if private_key is not None else self.private_key
        
        if key_to_use is None:
            raise ValueError("未提供私鑰且實例沒有私鑰")
        
        # 創建簽名密鑰
        signing_key = None
        
        # 1. 首先檢查是否為 PEM 格式 (帶頭尾標記)
        if self.is_pem_format(key_to_use):
            logger.info("檢測到 PEM 格式私鑰 (帶標準頭尾標記)")
            try:
                # 從 PEM 格式提取實際的密鑰
                key_bytes = self.extract_key_from_pem(key_to_use)
                
                # 使用提取的密鑰創建簽名密鑰
                signing_key = nacl.signing.SigningKey(key_bytes)
                logger.debug("成功從 PEM 格式創建私鑰的簽名密鑰")
                
                # 簽名消息
                signed_message = signing_key.sign(message.encode('utf-8'))
                signature_b64 = base64.b64encode(signed_message.signature).decode('utf-8')
                logger.debug(f"使用 PEM 格式私鑰成功生成 Ed25519 簽名: {signature_b64[:10]}...")
                return signature_b64
            except Exception as e:
                logger.warning(f"PEM 格式處理失敗: {str(e)}，嘗試其他格式")
        
        # 檢查是否包含 Base64 特有字符，暗示這可能是 Base64 編碼
        contains_base64_chars = '+' in key_to_use or '/' in key_to_use or '=' in key_to_use
        
        # 2. 嘗試 Base64 格式 - 自行生成的密鑰通常是這種格式
        if signing_key is None and (contains_base64_chars or len(key_to_use) % 4 == 0):
            try:
                # 嘗試標準 Base64 解碼
                key_bytes = base64.b64decode(key_to_use)
                logger.debug(f"檢測到 Base64 格式密鑰，解碼後長度: {len(key_bytes)} 字節")
                
                # 特殊處理 48 字節長度的 PKCS#8 格式密鑰
                if len(key_bytes) == 48:
                    logger.info("檢測到 PKCS#8 格式的 Ed25519 私鑰 (48 字節)")
                    
                    # PKCS#8 格式的 Ed25519 私鑰通常在後 32 字節位置包含實際的私鑰數據
                    try:
                        # 嘗試提取後 32 字節作為私鑰
                        actual_key_bytes = key_bytes[16:]
                        logger.debug(f"提取的私鑰數據長度: {len(actual_key_bytes)} 字節")
                        
                        # 驗證提取的數據是否為有效的 Ed25519 私鑰
                        test_key = nacl.signing.SigningKey(actual_key_bytes)
                        logger.info("成功從 PKCS#8 格式提取有效的 Ed25519 私鑰")
                        key_bytes = actual_key_bytes
                    except Exception as e:
                        logger.warning(f"從 PKCS#8 格式提取私鑰失敗: {str(e)}")
                        
                        # 嘗試使用完整的 48 字節作為私鑰的備選方案
                        logger.warning("嘗試使用完整的 48 字節數據作為私鑰")
                        try:
                            # 如果無法提取，嘗試使用原始 48 字節
                            test_key = nacl.signing.SigningKey(key_bytes)
                            logger.info("使用完整的 48 字節作為私鑰成功")
                        except Exception:
                            logger.warning("完整的 48 字節數據也不是有效的私鑰，嘗試截取前 32 字節")
                            key_bytes = key_bytes[:32]
                # 根據 Ed25519 標準，私鑰應該是 32 字節
                elif len(key_bytes) == 32:
                    logger.debug("Base64 解碼後長度正好是標準的 32 字節")
                elif len(key_bytes) > 32:
                    # 如果大於 32 字節但不是 48 字節，這可能是其他格式
                    # 嘗試查找有效的 Ed25519 私鑰部分
                    logger.warning(f"非標準私鑰長度: {len(key_bytes)} 字節")
                    
                    # 嘗試前 32 字節
                    try:
                        test_key = nacl.signing.SigningKey(key_bytes[:32])
                        logger.debug("前 32 字節是有效的 Ed25519 私鑰")
                        key_bytes = key_bytes[:32]
                    except Exception:
                        # 嘗試後 32 字節
                        try:
                            test_key = nacl.signing.SigningKey(key_bytes[-32:])
                            logger.debug("後 32 字節是有效的 Ed25519 私鑰")
                            key_bytes = key_bytes[-32:]
                        except Exception:
                            logger.warning("無法找到有效的 32 字節私鑰部分，使用截斷的數據")
                            key_bytes = key_bytes[:32]
                else:
                    logger.warning(f"私鑰長度 ({len(key_bytes)} 字節) 小於標準的 32 字節，可能導致簽名失敗")
                
                # 嘗試使用解碼後的字節創建簽名密鑰
                try:
                    signing_key = nacl.signing.SigningKey(key_bytes)
                    logger.debug("成功創建 Base64 格式私鑰的簽名密鑰")
                except Exception as sk_error:
                    logger.warning(f"Base64 解碼後的數據不是有效的 Ed25519 私鑰: {str(sk_error)}")
            except Exception as e:
                logger.warning(f"Base64 格式處理失敗: {str(e)}")
        
        # 3. 嘗試十六進制格式
        if signing_key is None and len(key_to_use) == 64 and all(c in '0123456789abcdefABCDEF' for c in key_to_use):
            try:
                key_bytes = bytes.fromhex(key_to_use)
                logger.debug(f"檢測到十六進制格式密鑰，轉換為字節長度: {len(key_bytes)}")
                
                # 確認是否是有效的 Ed25519 私鑰
                signing_key = nacl.signing.SigningKey(key_bytes)
                logger.debug("成功創建十六進制格式私鑰的簽名密鑰")
            except Exception as e:
                logger.warning(f"十六進制格式處理失敗: {str(e)}")
        
        # 4. 最後嘗試直接使用私鑰字符串
        if signing_key is None:
            try:
                # 對於其他格式或編碼，嘗試直接使用原始字符串
                key_bytes = key_to_use.encode('utf-8')
                logger.debug(f"嘗試使用原始字符串作為密鑰，長度: {len(key_bytes)} 字節")
                
                if len(key_bytes) == 32:
                    logger.debug("原始字符串正好是 32 字節長度")
                    signing_key = nacl.signing.SigningKey(key_bytes)
                else:
                    logger.warning(f"原始字符串長度 ({len(key_bytes)} 字節) 不是標準的 32 字節")
                    
                    # 嘗試調整為32字節
                    if len(key_bytes) > 32:
                        logger.warning("截斷至 32 字節尺寸")
                        signing_key = nacl.signing.SigningKey(key_bytes[:32])
                    else:
                        # 如果長度小於32，嘗試填充
                        logger.warning(f"原始密鑰長度不足 32 字節，簽名可能失敗")
                        try:
                            # 嘗試填充到32字節
                            padded_key = key_bytes.ljust(32, b'\0')
                            signing_key = nacl.signing.SigningKey(padded_key)
                        except Exception as pad_error:
                            logger.warning(f"填充密鑰失敗: {str(pad_error)}")
            except Exception as e:
                logger.warning(f"原始字符串格式處理失敗: {str(e)}")
        
        # 如果所有方法都失敗，生成一個新的密鑰對，但這只是臨時方案
        if signing_key is None:
            logger.warning("所有密鑰格式處理都失敗，生成臨時密鑰對（不推薦用於正式環境）")
            signing_key = nacl.signing.SigningKey.generate()
        
        # 簽名消息
        try:
            signed_message = signing_key.sign(message.encode('utf-8'))
            signature_b64 = base64.b64encode(signed_message.signature).decode('utf-8')
            logger.debug(f"成功生成 Ed25519 簽名: {signature_b64[:10]}...")
            return signature_b64
        except Exception as sign_error:
            logger.error(f"簽名過程中出錯: {str(sign_error)}")
            raise ValueError(f"無法使用提供的私鑰生成簽名: {str(sign_error)}")
    
    def get_public_key(self) -> str:
        """
        獲取Ed25519公鑰
        
        Returns:
            Base64編碼的公鑰
        """
        if self.public_key is None:
            raise ValueError("未生成密鑰對")
        
        return self.public_key
    
    def get_private_key(self) -> str:
        """
        獲取Ed25519私鑰
        
        Returns:
            Base64編碼的私鑰
        """
        if self.private_key is None:
            raise ValueError("未生成密鑰對")
        
        return self.private_key

# 使用示例
# key_manager = Ed25519KeyManager("path/to/private_key.pem")
# signature = key_manager.sign_message("hello world", key_manager.private_key)
# print(signature) 