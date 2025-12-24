# ============================================
# INDICADORES TÉCNICOS PARA EL BOT
# ============================================

import numpy as np
import pandas as pd
from collections import deque


class TechnicalIndicators:
    """Calcula indicadores técnicos en tiempo real"""
    
    def __init__(self, window_size=50):
        self.window_size = window_size
        self.prices = deque(maxlen=window_size)
        
    def add_price(self, price):
        """Agregar nuevo precio al historial"""
        self.prices.append(price)
    
    def calculate_rsi(self, period=14):
        """Calcular RSI (Relative Strength Index)"""
        if len(self.prices) < period + 1:
            return 50
        
        prices_array = np.array(list(self.prices))
        deltas = np.diff(prices_array)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, fast=12, slow=26, signal=9):
        """Calcular MACD"""
        if len(self.prices) < slow:
            return 0, 0, 0
        
        prices_array = np.array(list(self.prices))
        
        ema_fast = self._calculate_ema(prices_array, fast)
        ema_slow = self._calculate_ema(prices_array, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = 0
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, period=20, std_dev=2):
        """Calcular Bollinger Bands"""
        if len(self.prices) < period:
            current_price = list(self.prices)[-1] if self.prices else 0
            return current_price, current_price, current_price
        
        prices_array = np.array(list(self.prices)[-period:])
        
        middle_band = np.mean(prices_array)
        std = np.std(prices_array)
        
        upper_band = middle_band + (std_dev * std)
        lower_band = middle_band - (std_dev * std)
        
        return middle_band, upper_band, lower_band
    
    def calculate_volatility(self, period=20):
        """Calcular volatilidad"""
        if len(self.prices) < period:
            return 0
        
        prices_array = np.array(list(self.prices)[-period:])
        returns = np.diff(prices_array) / prices_array[:-1]
        volatility = np.std(returns) * 100
        
        return volatility
    
    def _calculate_ema(self, data, period):
        """Calcular EMA"""
        if len(data) < period:
            return np.mean(data)
        
        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def get_signals(self, current_price):
        """Obtener señales de trading"""
        self.add_price(current_price)
        
        rsi = self.calculate_rsi()
        macd_line, signal_line, histogram = self.calculate_macd()
        middle_bb, upper_bb, lower_bb = self.calculate_bollinger_bands()
        volatility = self.calculate_volatility()
        
        signals = {
            'rsi': rsi,
            'rsi_signal': 'CALL' if rsi < 35 else 'PUT' if rsi > 65 else 'NEUTRAL',
            'macd': histogram,
            'macd_signal': 'CALL' if histogram > 0 else 'PUT' if histogram < 0 else 'NEUTRAL',
            'bb_position': 'LOWER' if current_price <= lower_bb else 'UPPER' if current_price >= upper_bb else 'MIDDLE',
            'bb_signal': 'CALL' if current_price <= lower_bb else 'PUT' if current_price >= upper_bb else 'NEUTRAL',
            'volatility': volatility,
            'bb_middle': middle_bb,
            'bb_upper': upper_bb,
            'bb_lower': lower_bb,
            'combined_signal': 'NEUTRAL',
            'signal_strength': 0
        }
        
        return signals
