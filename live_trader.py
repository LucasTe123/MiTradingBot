# ============================================
# BOT DE TRADING EN VIVO - DERIV DEMO
# ============================================

import asyncio
import numpy as np
from datetime import datetime
import csv
import os

from deriv_websocket import DerivAPI
from stable_baselines3 import PPO
from telegram_bot import TelegramNotifier
from indicators import TechnicalIndicators


class LiveTrader:
    """Bot mejorado que opera en Deriv en tiempo real"""

    def __init__(self, model_path, initial_balance=10000, risk_percent=1.0):
        self.model_path = model_path
        self.initial_balance = initial_balance
        self.risk_percent = risk_percent
        self.balance = initial_balance
        self.position = None
        self.entry_price = 0
        self.entry_time = None
        self.contract_id = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_losses = 0
        self.model = None
        self.notifier = None
        self.connection = None
        self.indicators = TechnicalIndicators(window_size=50)
        
        # Archivo de histórico
        self.history_file = "trade_history.csv"
        self._create_history_file()

    def _create_history_file(self):
        """Crear archivo CSV inmediatamente"""
        try:
            # Si ya existe, no hacer nada
            if os.path.exists(self.history_file):
                print(f"📝 Usando archivo existente: {self.history_file}")
                return
            
            # Crear nuevo archivo
            with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Fecha', 'Hora', 'Simbolo', 'Tipo', 'Precio_Entrada',
                    'Precio_Salida', 'Stake', 'Resultado', 'Ganancia',
                    'RSI', 'MACD', 'BB_Posicion', 'Volatilidad',
                    'Señal_Combinada', 'Fuerza_Señal', 'Balance_Final'
                ])
            print(f"✅ Archivo creado: {self.history_file}")
        except Exception as e:
            print(f"❌ Error creando CSV: {e}")

    def _save_trade(self, trade_data):
        """Guardar operación en CSV"""
        try:
            with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(trade_data)
            print(f"💾 Operación guardada en {self.history_file}")
        except Exception as e:
            print(f"❌ Error guardando trade: {e}")

    def calculate_stake(self, volatility, signal_strength):
        """Calcular tamaño de posición dinámico"""
        base_stake = self.balance * (self.risk_percent / 100)
        
        # Ajustar por volatilidad
        if volatility > 0.5:
            volatility_factor = 0.7
        elif volatility > 0.3:
            volatility_factor = 0.85
        else:
            volatility_factor = 1.0
        
        # Ajustar por fuerza de señal
        if signal_strength >= 3:
            signal_factor = 1.3
        else:
            signal_factor = 1.0
        
        # Ajustar por rachas perdedoras
        if self.consecutive_losses >= 3:
            loss_factor = 0.5
        elif self.consecutive_losses >= 2:
            loss_factor = 0.7
        else:
            loss_factor = 1.0
        
        stake = base_stake * volatility_factor * signal_factor * loss_factor
        
        # Límites
        min_stake = 10
        max_stake = self.balance * 0.05
        
        stake = max(min_stake, min(stake, max_stake))
        
        return round(stake, 2)

    def load_model(self):
        """Cargar modelo entrenado"""
        print(f"📂 Cargando modelo desde: {self.model_path}")
        self.model = PPO.load(self.model_path)
        print("✅ Modelo cargado!\n")

    async def connect_telegram(self):
        """Conectar bot de Telegram"""
        try:
            print("📱 Conectando Telegram Bot...")
            self.notifier = TelegramNotifier()
            await self.notifier.send_message(
                "🤖 Bot Mejorado Iniciado\n\n"
                "📊 Modo: MULTI-MERCADO\n"
                f"💰 Balance: ${self.initial_balance:,.2f}\n"
                "⚡ CALL y PUT activos\n"
                "🎯 RSI: <30 CALL, >70 PUT"
            )
            print("✅ Telegram conectado!\n")
        except Exception as e:
            print(f"⚠️ Telegram no disponible: {e}\n")
            self.notifier = None

    def get_observation(self, current_price, signals):
        """Crear observación para el modelo"""
        obs = np.array([
            current_price,
            self.balance,
            1.0 if self.position else 0.0,
            self.entry_price,
            0.0,
        ], dtype=np.float32)
        
        return obs.reshape(1, -1)

    async def run(self, symbol="R_75", duration_minutes=30):
        """Ejecutar bot en vivo"""
        print("=" * 70)
        print("🚀 BOT MULTI-MERCADO CON RSI ESTRICTO")
        print("=" * 70)
        print(f"📊 Símbolo: {symbol}")
        print(f"⏱️  Duración: {duration_minutes} minutos")
        print(f"💵 Riesgo: {self.risk_percent}% del balance")
        print(f"🎯 RSI: <30 = CALL | >70 = PUT")
        print(f"📝 Histórico: {self.history_file}")
        print("=" * 70 + "\n")

        self.load_model()
        await self.connect_telegram()

        print("🌐 Conectando a Deriv API...")
        self.connection = DerivAPI()

        connected = await self.connection.connect()
        if not connected:
            print("❌ No se pudo conectar")
            return

        authorized = await self.connection.authorize()
        if not authorized:
            print("❌ No se pudo autorizar")
            await self.connection.close()
            return

        print("✅ Conectado a Deriv\n")

        try:
            print(f"📈 Suscribiéndose a {symbol}...\n")
            ok = await self.connection.subscribe({"ticks": symbol})
            if not ok:
                print("❌ Falló suscripción")
                await self.connection.close()
                return

            start_time = datetime.now()
            tick_count = 0
            last_action_time = datetime.now()

            async def tick_callback(response):
                nonlocal tick_count, last_action_time

                if not response or "tick" not in response:
                    return False

                tick_count += 1
                tick = response["tick"]
                current_price = float(tick["quote"])
                tick_time = datetime.fromtimestamp(tick["epoch"])

                # Obtener señales
                signals = self.indicators.get_signals(current_price)

                # Mostrar cada 10 ticks
                if tick_count % 10 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    print(
                        f"[{tick_time.strftime('%H:%M:%S')}] "
                        f"Precio: ${current_price:,.2f} | "
                        f"RSI: {signals['rsi']:.1f} | "
                        f"MACD: {signals['macd']:+.3f} | "
                        f"BB: {signals['bb_position']} | "
                        f"Balance: ${self.balance:,.2f} | "
                        f"Trades: {self.total_trades}/{self.winning_trades}W"
                    )

                # LÓGICA DE TRADING SIMPLIFICADA
                time_since_last = (datetime.now() - last_action_time).total_seconds()
                
                if self.position is None and time_since_last > 25:
                    contract_type = None
                    
                    # REGLA SIMPLE Y DIRECTA
                    rsi = signals['rsi']
                    
                    # COMPRA (CALL) si RSI < 30
                    if rsi < 30:
                        contract_type = "CALL"
                        print(f"\n🟢 RSI BAJO ({rsi:.1f}) → SEÑAL DE COMPRA")
                    
                    # VENTA (PUT) si RSI > 70
                    elif rsi > 70:
                        contract_type = "PUT"
                        print(f"\n🔴 RSI ALTO ({rsi:.1f}) → SEÑAL DE VENTA")
                    
                    if contract_type:
                        # Calcular stake
                        stake = self.calculate_stake(signals['volatility'], 3)
                        
                        print(f"   Ejecutando {contract_type} @ ${current_price:,.2f}")
                        print(f"   RSI: {rsi:.1f} | MACD: {signals['macd']:+.3f} | BB: {signals['bb_position']}")
                        print(f"   Stake: ${stake:.2f}")
                        
                        contract = await self.connection.buy_contract(
                            symbol=symbol,
                            contract_type=contract_type,
                            amount=stake,
                            duration=15,
                            duration_unit="s"
                        )
                        
                        if contract:
                            self.position = contract_type
                            self.entry_price = current_price
                            self.entry_time = tick_time
                            self.contract_id = contract["contract_id"]
                            self.current_stake = stake
                            self.entry_signals = signals.copy()
                            last_action_time = datetime.now()
                            
                            print(f"✅ Contrato: {self.contract_id}")
                            
                            if self.notifier:
                                await self.notifier.send_trade_opened(
                                    symbol, contract_type, stake, self.contract_id
                                )
                        else:
                            print("❌ Error ejecutando")

                # CERRAR POSICIÓN
                elif self.position is not None:
                    time_in_trade = (tick_time - self.entry_time).total_seconds()
                    
                    if time_in_trade > 20:
                        price_change = current_price - self.entry_price
                        
                        if self.position == "CALL":
                            pnl = price_change
                        else:
                            pnl = -price_change

                        profit_percent = (pnl / self.entry_price) * 100
                        profit_amount = self.current_stake * 0.95 if profit_percent > 0 else -self.current_stake

                        self.balance += profit_amount
                        self.total_trades += 1

                        resultado = "GANÓ" if profit_amount > 0 else "PERDIÓ"
                        
                        if profit_amount > 0:
                            self.winning_trades += 1
                            self.consecutive_losses = 0
                            print(f"\n✅ {resultado} ${abs(profit_amount):,.2f}")
                        else:
                            self.losing_trades += 1
                            self.consecutive_losses += 1
                            print(f"\n❌ {resultado} ${abs(profit_amount):,.2f}")
                        
                        print(f"   Cambio: {profit_percent:+.2f}%")

                        # GUARDAR EN CSV
                        trade_data = [
                            tick_time.strftime('%Y-%m-%d'),
                            tick_time.strftime('%H:%M:%S'),
                            symbol,
                            self.position,
                            f"{self.entry_price:.2f}",
                            f"{current_price:.2f}",
                            f"{self.current_stake:.2f}",
                            resultado,
                            f"{profit_amount:+.2f}",
                            f"{self.entry_signals['rsi']:.2f}",
                            f"{self.entry_signals['macd']:.4f}",
                            self.entry_signals['bb_position'],
                            f"{self.entry_signals['volatility']:.2f}",
                            self.entry_signals['combined_signal'],
                            self.entry_signals['signal_strength'],
                            f"{self.balance:.2f}"
                        ]
                        self._save_trade(trade_data)

                        if self.notifier:
                            await self.notifier.send_trade_closed(
                                symbol, self.position, self.current_stake,
                                profit_amount, f"{int(time_in_trade)}s"
                            )

                        # Reset
                        self.position = None
                        self.entry_price = 0
                        self.entry_time = None
                        self.contract_id = None
                        print(f"💰 Balance: ${self.balance:,.2f}\n")

                # Verificar tiempo
                elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
                if elapsed_minutes >= duration_minutes:
                    print("\n⏱️ Tiempo completado!")
                    return True

                return False

            # Procesar ticks
            if self.connection.events is None:
                print("❌ Events es None")
                await self.connection.close()
                return

            async for response in self.connection.events:
                should_stop = await tick_callback(response)
                if should_stop:
                    break

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            await self.connection.close()

            print("\n" + "=" * 70)
            print("📊 RESUMEN FINAL")
            print("=" * 70)
            print(f"💰 Balance inicial: ${self.initial_balance:,.2f}")
            print(f"💰 Balance final: ${self.balance:,.2f}")
            pnl = self.balance - self.initial_balance
            print(f"💵 P&L: ${pnl:+,.2f} ({(pnl/self.initial_balance*100):+.2f}%)")
            print(f"📊 Trades: {self.total_trades}")
            print(f"✅ Ganadores: {self.winning_trades}")
            print(f"❌ Perdedores: {self.losing_trades}")

            if self.total_trades > 0:
                win_rate = (self.winning_trades / self.total_trades) * 100
                print(f"📈 Win rate: {win_rate:.1f}%")
            
            print(f"📝 Ver detalles en: {self.history_file}")
            print("=" * 70)


# ============================================
# MULTI-MERCADO
# ============================================

async def main():
    """Función principal - PUEDES CAMBIAR EL SÍMBOLO AQUÍ"""
    
    # ELIGE UNO DE ESTOS MERCADOS:
    # "R_10"   = Volatility 10
    # "R_25"   = Volatility 25
    # "R_50"   = Volatility 50
    # "R_75"   = Volatility 75
    # "R_100"  = Volatility 100
    # "BOOM500" = Boom 500
    # "BOOM1000" = Boom 1000
    # "CRASH500" = Crash 500
    # "CRASH1000" = Crash 1000
    # "stpRNG" = Step Index
    
    model_path = "models/deriv_bot_v1_final"
    
    # CAMBIA EL SÍMBOLO AQUÍ:
    symbol_to_trade = "R_75"  # <-- Cambia esto por el mercado que quieras
    
    trader = LiveTrader(
        model_path,
        initial_balance=10000,
        risk_percent=1.0
    )
    
    await trader.run(symbol=symbol_to_trade, duration_minutes=30)


if __name__ == "__main__":
    print("\n🤖 Bot MULTI-MERCADO con RSI estricto")
    print("📊 Mercados disponibles: R_10, R_25, R_50, R_75, R_100, BOOM500, CRASH500, etc.")
    print("✏️  Edita 'symbol_to_trade' en el código para cambiar de mercado")
    print("Presiona Ctrl+C para detener\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Bot detenido")
