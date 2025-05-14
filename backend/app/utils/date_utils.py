import datetime
import pytz
from typing import Optional

# 定义台北時區
TZ_TAIPEI = pytz.timezone('Asia/Taipei')

def get_taiwan_time() -> datetime.datetime:
    """返回台灣標準時間（UTC+8）"""
    return datetime.datetime.now(TZ_TAIPEI)

def format_datetime(dt: Optional[datetime.datetime] = None, 
                   format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化日期時間為指定格式的字符串
    
    Args:
        dt: 要格式化的日期時間，如果為 None 則使用當前台灣時間
        format_str: 日期時間格式字符串
        
    Returns:
        格式化後的日期時間字符串
    """
    if dt is None:
        dt = get_taiwan_time()
    return dt.strftime(format_str)

def parse_datetime(datetime_str: str, 
                  format_str: str = "%Y-%m-%d %H:%M:%S",
                  timezone: pytz.timezone = TZ_TAIPEI) -> datetime.datetime:
    """
    將字符串解析為日期時間對象
    
    Args:
        datetime_str: 日期時間字符串
        format_str: 日期時間格式字符串
        timezone: 時區
        
    Returns:
        日期時間對象
    """
    naive_dt = datetime.datetime.strptime(datetime_str, format_str)
    return timezone.localize(naive_dt)

def get_date_range(start_date: datetime.date, 
                  end_date: datetime.date) -> list[datetime.date]:
    """
    獲取兩個日期之間的所有日期列表
    
    Args:
        start_date: 開始日期
        end_date: 結束日期
        
    Returns:
        日期列表
    """
    if start_date > end_date:
        start_date, end_date = end_date, start_date
        
    date_range = []
    current_date = start_date
    
    while current_date <= end_date:
        date_range.append(current_date)
        current_date += datetime.timedelta(days=1)
        
    return date_range

def get_time_ago(timestamp: datetime.datetime) -> str:
    """
    計算距離給定時間戳過去了多長時間，並以易讀的格式返回
    
    Args:
        timestamp: 過去的時間戳
        
    Returns:
        易讀的時間差字符串，如 "2 分鐘前"
    """
    now = get_taiwan_time()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return f"{int(seconds)} 秒前"
    elif seconds < 3600:
        return f"{int(seconds // 60)} 分鐘前"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} 小時前"
    elif seconds < 604800:
        return f"{int(seconds // 86400)} 天前"
    elif seconds < 2592000:
        return f"{int(seconds // 604800)} 週前"
    elif seconds < 31536000:
        return f"{int(seconds // 2592000)} 個月前"
    else:
        return f"{int(seconds // 31536000)} 年前" 