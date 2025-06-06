from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from ...db.database import Base

class GridStrategy(Base):
    __tablename__ = "grid_strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    grid_type = Column(String, nullable=False)  # ARITHMETIC, GEOMETRIC
    strategy_type = Column(String, nullable=False, default="NEUTRAL")  # BULLISH, NEUTRAL, BEARISH
    market_type = Column(String, nullable=False, default="FUTURES")  # 目前只支持FUTURES
    upper_price = Column(Numeric(28, 8), nullable=False)
    lower_price = Column(Numeric(28, 8), nullable=False)
    grid_number = Column(Integer, nullable=False)
    total_investment = Column(Numeric(28, 8), nullable=False)
    per_grid_amount = Column(Numeric(28, 8), nullable=True)
    leverage = Column(Integer, nullable=True)  # 僅合約有效
    stop_loss = Column(Numeric(28, 8), nullable=True)
    take_profit = Column(Numeric(28, 8), nullable=True)
    profit_collection = Column(Boolean, default=False)  # 是否回收利潤
    status = Column(String, default="CREATED")  # CREATED, RUNNING, STOPPED, FINISHED
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 交易對規則緩存
    symbol_price_precision = Column(Integer, nullable=True)
    symbol_qty_precision = Column(Integer, nullable=True)
    symbol_min_qty = Column(Numeric(28, 8), nullable=True)
    symbol_min_notional = Column(Numeric(28, 8), nullable=True)
    symbol_max_leverage = Column(Integer, nullable=True)
    
    # 關聯
    user = relationship("User", back_populates="grid_strategies")
    grid_orders = relationship("GridOrder", back_populates="strategy")


class GridOrder(Base):
    __tablename__ = "grid_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("grid_strategies.id"))
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    grid_index = Column(Integer, nullable=False)
    price = Column(Numeric(28, 8), nullable=False)
    quantity = Column(Numeric(28, 8), nullable=False)
    side = Column(String, nullable=False)  # BUY, SELL
    order_id = Column(String, nullable=True)
    status = Column(String, nullable=False)  # PLACED, FILLED, CANCELED
    created_at = Column(DateTime, default=func.now())
    filled_at = Column(DateTime, nullable=True)
    profit = Column(Numeric(28, 8), nullable=True)
    
    # 關聯
    strategy = relationship("GridStrategy", back_populates="grid_orders")


class SymbolRules(Base):
    __tablename__ = "symbol_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    price_precision = Column(Integer, nullable=False)
    quantity_precision = Column(Integer, nullable=False)
    min_quantity = Column(Numeric(28, 8), nullable=False)
    min_notional = Column(Numeric(28, 8), nullable=False)
    max_leverage = Column(Integer, nullable=True)
    taker_fee = Column(Numeric(28, 8), nullable=False)
    maker_fee = Column(Numeric(28, 8), nullable=False)
    contract_value = Column(Numeric(28, 8), nullable=True)  # 合約面值
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', name='uix_exchange_symbol'),
    ) 