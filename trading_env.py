# ============================================
# AMBIENTE DE TRADING PARA REINFORCEMENT LEARNING
# ============================================

import gym
from gym import spaces
import numpy as np
import pandas as pd


class TradingEnv(gym.Env):
    """Ambiente de trading para entrenar el bot"""
    
    def __init__(self, df, initial_balance=10000, stake_amount=10):
        super(TradingEnv, self).__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.stake_amount = stake_amount
        
        # Espacios de acción: 0=HOLD, 1=BUY_CALL, 2=BUY_PUT
        self.action_space = spaces.Discrete(3)
        
        # Espacios de observación: [precio_actual, balance, posición_abierta, precio_entrada, pasos_en_posición]
        self.observation_space = spaces.Box(
            low=0, 
            high=np.inf, 
            shape=(5,), 
            dtype=np.float32
        )
        
        # Estado del ambiente
        self.current_step = 0
        self.balance = initial_balance
        self.position = None  # None, 'CALL', o 'PUT'
        self.entry_price = 0
        self.position_steps = 0
        
        # Estadísticas
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
    def reset(self):
        """Reiniciar el ambiente"""
        self.current_step = 0
        self.balance = self.initial_balance
        self.position = None
        self.entry_price = 0
        self.position_steps = 0
        
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        return self._get_observation()
    
    def _get_observation(self):
        """Obtener estado actual"""
        current_price = self.df.iloc[self.current_step]['price']
        
        obs = np.array([
            current_price,
            self.balance,
            1.0 if self.position else 0.0,
            self.entry_price,
            float(self.position_steps)
        ], dtype=np.float32)
        
        return obs
    
    def step(self, action):
        """Ejecutar una acción"""
        current_price = self.df.iloc[self.current_step]['price']
        reward = 0
        done = False
        
        # Si tiene posición abierta
        if self.position is not None:
            self.position_steps += 1
            price_change = current_price - self.entry_price
            
            # Calcular P&L
            if self.position == 'CALL':
                pnl = price_change
            else:  # PUT
                pnl = -price_change
            
            # Cerrar posición después de 5-15 pasos (aleatorio para variedad)
            close_threshold = np.random.randint(5, 16)
            
            if self.position_steps >= close_threshold:
                # Cerrar trade
                profit_percent = (pnl / self.entry_price) * 100
                profit_amount = self.stake_amount * (profit_percent / 100)
                
                self.balance += profit_amount
                self.total_trades += 1
                self.total_profit += profit_amount
                
                # SISTEMA DE RECOMPENSAS MEJORADO
                if profit_amount > 0:
                    # GANANCIA
                    self.winning_trades += 1
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                    
                    # Recompensa base por ganar
                    reward = 10 + (profit_amount * 2)
                    
                    # Bonus por racha ganadora
                    if self.consecutive_wins >= 3:
                        reward += 20
                    if self.consecutive_wins >= 5:
                        reward += 50
                    
                    # Bonus extra si la ganancia es grande (>8%)
                    if profit_percent > 8:
                        reward += 30
                    
                else:
                    # PÉRDIDA
                    self.losing_trades += 1
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                    
                    # Penalización por perder
                    reward = -15 + (profit_amount * 3)  # profit_amount es negativo
                    
                    # Penalización extra por rachas perdedoras
                    if self.consecutive_losses >= 3:
                        reward -= 25
                    if self.consecutive_losses >= 5:
                        reward -= 50
                    
                    # Penalización severa por pérdidas grandes (>-8%)
                    if profit_percent < -8:
                        reward -= 40
                
                # Resetear posición
                self.position = None
                self.entry_price = 0
                self.position_steps = 0
        
        else:
            # No tiene posición abierta
            if action == 1:  # Abrir CALL
                self.position = 'CALL'
                self.entry_price = current_price
                self.position_steps = 0
                reward = 2  # Pequeña recompensa por tomar acción
                
            elif action == 2:  # Abrir PUT
                self.position = 'PUT'
                self.entry_price = current_price
                self.position_steps = 0
                reward = 2  # Pequeña recompensa por tomar acción
                
            else:  # HOLD (no hacer nada)
                # Penalización LEVE por quedarse quieto mucho tiempo
                if self.current_step > 50 and self.total_trades == 0:
                    reward = -0.5
                else:
                    reward = -0.1
        
        # Avanzar al siguiente paso
        self.current_step += 1
        
        # Verificar si terminó el episodio
        if self.current_step >= len(self.df) - 1:
            done = True
            
            # Bonus/penalización final según desempeño
            if self.total_trades > 0:
                win_rate = self.winning_trades / self.total_trades
                
                if win_rate > 0.6:
                    reward += 100  # Excelente win rate
                elif win_rate > 0.5:
                    reward += 50   # Buen win rate
                elif win_rate < 0.4:
                    reward -= 50   # Mal win rate
                
                # Bonus por profit total positivo
                if self.total_profit > 0:
                    reward += self.total_profit * 0.5
                else:
                    reward += self.total_profit * 0.8  # Más penalización por pérdidas
            else:
                # Penalización por nunca operar
                reward -= 100
        
        # Límite de balance (stop de seguridad)
        if self.balance < self.initial_balance * 0.5:  # Perdió 50% o más
            done = True
            reward -= 200  # Penalización severa por drawdown excesivo
        
        info = {
            'balance': self.balance,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        }
        
        return self._get_observation(), reward, done, info
    
    def render(self, mode='human'):
        """Mostrar estado actual"""
        profit = self.balance - self.initial_balance
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        print(f"Step: {self.current_step:4d} | Balance: ${self.balance:8.2f} | "
              f"Profit: ${profit:+7.2f} | Trades: {self.total_trades:3d} | "
              f"Win Rate: {win_rate:5.1f}% | Position: {self.position or 'NONE'}")


# ============================================
# PRUEBA DEL AMBIENTE
# ============================================

if __name__ == "__main__":
    print("🧪 Probando Trading Environment...\n")
    
    # Cargar datos
    df = pd.read_csv("data/R_75_ticks_10000.csv")
    print(f"✅ Datos cargados: {len(df)} registros\n")
    
    # Crear ambiente
    env = TradingEnv(df)
    
    # Probar con acciones aleatorias
    obs = env.reset()
    print("🎮 Ejecutando 20 acciones aleatorias:\n")
    
    action_names = ['HOLD', 'BUY_CALL', 'BUY_PUT']
    
    for i in range(20):
        action = env.action_space.sample()
        obs, reward, done, info = env.step(action)
        
        print(f"Acción: {action_names[action]:10}  Reward: {reward:+6.2f}  ", end="")
        env.render()
        
        if done:
            print("\n❌ Episodio terminado")
            break
    
    print(f"\n✅ Prueba completada!")
    print(f"💰 Balance final: ${env.balance:.2f}")
    print(f"📊 Trades totales: {env.total_trades}")
    print(f"🎯 Win rate: {(env.winning_trades/env.total_trades*100) if env.total_trades > 0 else 0:.1f}%")
