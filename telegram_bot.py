# ============================================
# TELEGRAM BOT PARA NOTIFICACIONES
# ============================================

import asyncio
from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  # ESTO SÍ VA AQUÍ

class TelegramNotifier:
    """Clase para enviar notificaciones por Telegram"""
    
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.chat_id = TELEGRAM_CHAT_ID
    
    async def send_message(self, message):
        """Enviar mensaje simple"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            return True
        except TelegramError as e:
            print(f"❌ Error enviando mensaje: {e}")
            return False
    
    async def send_trade_opened(self, symbol, contract_type, stake, contract_id):
        """Notificación de trade abierto"""
        message = f"""
🟢 <b>TRADE ABIERTO</b>

📍 Mercado: {symbol}
📊 Tipo: {contract_type}
💵 Stake: ${stake}
🆔 Contract ID: {contract_id}
⏰ Ahora mismo
"""
        await self.send_message(message)
    
    async def send_trade_closed(self, symbol, contract_type, stake, profit, duration):
        """Notificación de trade cerrado"""
        emoji = "✅" if profit > 0 else "❌"
        profit_text = f"+${profit:.2f}" if profit > 0 else f"-${abs(profit):.2f}"
        profit_percent = (profit / stake) * 100
        
        message = f"""
{emoji} <b>TRADE CERRADO</b>

📍 Mercado: {symbol}
📊 Tipo: {contract_type}
💵 Stake: ${stake}
💰 P/L: {profit_text} ({profit_percent:+.1f}%)
⏱️ Duración: {duration}
"""
        await self.send_message(message)
    
    async def send_daily_summary(self, trades, wins, losses, profit, balance):
        """Resumen diario"""
        win_rate = (wins / trades * 100) if trades > 0 else 0
        
        message = f"""
📊 <b>RESUMEN DIARIO</b>

🎯 Trades: {trades}
✅ Ganadores: {wins}
❌ Perdedores: {losses}
📈 Win Rate: {win_rate:.1f}%
💰 Profit/Loss: ${profit:+.2f}
💳 Balance: ${balance:.2f}
"""
        await self.send_message(message)
    
    async def send_status(self, balance, active_trades, profit_today, trades_today):
        """Estado actual del bot"""
        message = f"""
📊 <b>ESTADO ACTUAL</b>

💰 Balance: ${balance:.2f}
📈 P/L Hoy: ${profit_today:+.2f}
🎯 Trades hoy: {trades_today}
🔄 Trades activos: {active_trades}
🟢 Bot: ACTIVO
"""
        await self.send_message(message)
    
    async def send_alert(self, alert_type, description):
        """Alertas del sistema"""
        message = f"""
⚠️ <b>ALERTA</b>

🔔 Tipo: {alert_type}
📝 {description}
"""
        await self.send_message(message)


# ============================================
# FUNCIÓN DE PRUEBA
# ============================================

async def test_telegram():
    """Probar el bot de Telegram"""
    print("🚀 Probando Telegram Bot...\n")
    
    notifier = TelegramNotifier()
    
    # Mensaje de prueba
    print("📱 Enviando mensaje de prueba...")
    success = await notifier.send_message("✅ <b>Bot de Telegram conectado!</b>\n\nEl bot está listo para enviar notificaciones.")
    
    if success:
        print("✅ Mensaje enviado correctamente!")
        print("\n🔔 Revisa tu Telegram para ver el mensaje")
    else:
        print("❌ Error enviando mensaje")
    
    # Ejemplo de notificación de trade
    await asyncio.sleep(2)
    print("\n📊 Enviando ejemplo de trade abierto...")
    await notifier.send_trade_opened("R_75", "CALL", 10, "123456789")
    
    await asyncio.sleep(2)
    print("📊 Enviando ejemplo de trade cerrado...")
    await notifier.send_trade_closed("R_75", "CALL", 10, 8.50, "3:45 min")
    
    await asyncio.sleep(2)
    print("📊 Enviando ejemplo de estado...")
    await notifier.send_status(10263.73, 1, 45.30, 15)
    
    print("\n✅ Prueba completada! Revisa todos los mensajes en Telegram")


if __name__ == "__main__":
    asyncio.run(test_telegram())
