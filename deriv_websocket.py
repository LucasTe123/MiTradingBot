# ============================================
# CONEXIÓN CON DERIV API
# ============================================

import asyncio
import websockets
import json
from config import DERIV_APP_ID, DERIV_API_TOKEN, DERIV_WEBSOCKET


class DerivAPI:
    """Clase para manejar conexión y operaciones con Deriv API"""

    def __init__(self):
        self.websocket = None
        self.authorized = False
        self._recv_queue = None
        self.events = None          # async generator de eventos
        self._reader_task = None    # tarea en background que lee del WS

    async def connect(self):
        """Conectar al websocket de Deriv"""
        try:
            self.websocket = await websockets.connect(
                f"{DERIV_WEBSOCKET}?app_id={DERIV_APP_ID}"
            )
            print("✅ Conectado a Deriv API")
            return True
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            self.websocket = None
            return False

    async def authorize(self):
        """Autorizar con el token API"""
        if self.websocket is None:
            print("❌ No hay websocket en authorize(); llama a connect() primero")
            return False

        try:
            auth_request = {"authorize": DERIV_API_TOKEN}
            await self.websocket.send(json.dumps(auth_request))

            response = await self.websocket.recv()
            data = json.loads(response)

            if "authorize" in data:
                self.authorized = True
                balance = data["authorize"].get("balance")
                currency = data["authorize"].get("currency")
                print("✅ Autorizado correctamente")
                if balance is not None and currency is not None:
                    print(f"💰 Balance: {balance} {currency}")

                # Inicializar cola de recepción si no existe
                if self._recv_queue is None:
                    self._recv_queue = asyncio.Queue()

                # Crear el generador async de eventos
                self.events = self._event_generator()

                # Iniciar tarea lectora en segundo plano
                if self._reader_task is None:
                    self._reader_task = asyncio.create_task(self._read_loop())

                return True
            else:
                print(f"❌ Error en autorización: {data}")
                return False

        except Exception as e:
            print(f"❌ Error autorizando: {e}")
            return False

    async def subscribe(self, payload):
        """Suscribirse a ticks en tiempo real.

        Acepta `payload` como string (símbolo) o dict (request).
        Ejemplo: await connection.subscribe({'ticks': 'R_75'})
        """
        if self.websocket is None:
            print("❌ WebSocket no inicializado en subscribe(); llama a connect() y authorize() primero")
            return False

        try:
            if isinstance(payload, dict):
                tick_request = payload
            else:
                tick_request = {"ticks": payload, "subscribe": 1}

            if "subscribe" not in tick_request:
                tick_request["subscribe"] = 1

            await self.websocket.send(json.dumps(tick_request))
            print(f"📊 Suscrito con request: {tick_request}")
            return True
        except Exception as e:
            print(f"❌ Error suscribiendo: {e}")
            return False

    async def buy_contract(self, symbol, contract_type, amount, duration=15, duration_unit="s"):
        """Ejecutar una compra REAL de contrato en Deriv
        
        Args:
            symbol: Símbolo (ej: 'R_75')
            contract_type: 'CALL' o 'PUT'
            amount: Monto en USD (ej: 10)
            duration: Duración del contrato (ej: 15)
            duration_unit: 's' para segundos, 'm' para minutos
        
        Returns:
            dict con información del contrato comprado, o None si falla
        """
        if self.websocket is None:
            print("❌ WebSocket no inicializado")
            return None
        
        if self._recv_queue is None:
            print("❌ Cola de recepción no inicializada")
            return None
        
        try:
            # Paso 1: Obtener propuesta (precio estimado)
            proposal_request = {
                "proposal": 1,
                "amount": amount,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "duration": duration,
                "duration_unit": duration_unit,
                "symbol": symbol
            }
            
            await self.websocket.send(json.dumps(proposal_request))
            
            # Leer respuesta desde la COLA, no directamente del websocket
            proposal = None
            for _ in range(10):  # Intentar hasta 10 mensajes
                data = await self._recv_queue.get()
                if "proposal" in data:
                    proposal = data
                    break
                elif "tick" in data:
                    # Re-encolar ticks para que los procese el bot
                    await self._recv_queue.put(data)
                    await asyncio.sleep(0.01)
            
            if proposal is None:
                print("❌ No se recibió respuesta de propuesta")
                return None
            
            if "error" in proposal:
                print(f"❌ Error en propuesta: {proposal['error']}")
                return None
            
            if "proposal" not in proposal:
                print(f"❌ Respuesta inesperada: {proposal}")
                return None
            
            proposal_id = proposal["proposal"]["id"]
            
            # Paso 2: Ejecutar compra con la propuesta
            buy_request = {
                "buy": proposal_id,
                "price": amount
            }
            
            await self.websocket.send(json.dumps(buy_request))
            
            # Leer respuesta de compra desde la COLA
            buy_response = None
            for _ in range(10):  # Intentar hasta 10 mensajes
                data = await self._recv_queue.get()
                if "buy" in data:
                    buy_response = data
                    break
                elif "tick" in data:
                    # Re-encolar ticks para que los procese el bot
                    await self._recv_queue.put(data)
                    await asyncio.sleep(0.01)
            
            if buy_response is None:
                print("❌ No se recibió respuesta de compra")
                return None
            
            if "error" in buy_response:
                print(f"❌ Error comprando: {buy_response['error']}")
                return None
            
            if "buy" in buy_response:
                contract = buy_response["buy"]
                return {
                    "contract_id": contract["contract_id"],
                    "buy_price": contract["buy_price"],
                    "payout": contract["payout"],
                    "start_time": contract["start_time"],
                    "longcode": contract.get("longcode", "")
                }
            else:
                print(f"❌ Respuesta inesperada al comprar: {buy_response}")
                return None
                
        except Exception as e:
            print(f"❌ Error ejecutando contrato: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_next_tick(self):
        """Recibir el siguiente tick como dict sencillo."""
        try:
            # Preferir leer desde la cola si existe
            if self._recv_queue is not None:
                data = await self._recv_queue.get()
            else:
                if self.websocket is None:
                    print("❌ WebSocket no inicializado en get_next_tick()")
                    return None
                response = await self.websocket.recv()
                data = json.loads(response)

            if "tick" in data:
                return {
                    "price": data["tick"]["quote"],
                    "time": data["tick"]["epoch"],
                    "raw": data,
                }
            return {"raw": data}
        except Exception as e:
            print(f"❌ Error recibiendo tick: {e}")
            return None

    async def get_ticks(self, symbol="R_75"):
        """Pequeña prueba de ticks (no usada por el bot)."""
        try:
            ok = await self.subscribe(symbol)
            if not ok:
                return

            for i in range(5):
                if self._recv_queue is None:
                    if self.websocket is None:
                        print("❌ WebSocket no inicializado en get_ticks()")
                        return
                    response = await self.websocket.recv()
                    data = json.loads(response)
                else:
                    data = await self._recv_queue.get()

                if "tick" in data:
                    tick = data["tick"]
                    print(f"Tick {i+1}: Precio={tick['quote']}, Tiempo={tick['epoch']}")
        except Exception as e:
            print(f"❌ Error obteniendo ticks: {e}")

    async def close(self):
        """Cerrar conexión y limpiar recursos."""
        if self.websocket:
            if self._reader_task is not None:
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

            await self.websocket.close()
            print("🔌 Desconectado de Deriv API")

        self.websocket = None
        self._recv_queue = None
        self.events = None
        self._reader_task = None
        self.authorized = False

    async def _read_loop(self):
        """Lee mensajes del websocket y los mete en la cola."""
        try:
            while True:
                if self.websocket is None:
                    break
                raw = await self.websocket.recv()
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {"raw": raw}

                if self._recv_queue is not None:
                    await self._recv_queue.put(data)
        except asyncio.CancelledError:
            return
        except Exception as e:
            if self._recv_queue is not None:
                await self._recv_queue.put({"error": str(e)})

    async def _event_generator(self):
        """Async generator que entrega eventos desde la cola."""
        if self._recv_queue is None:
            self._recv_queue = asyncio.Queue()
        while True:
            item = await self._recv_queue.get()
            yield item


async def test_connection():
    """Probar la conexión con Deriv"""
    print("🚀 Iniciando prueba de conexión...\n")

    api = DerivAPI()

    connected = await api.connect()
    if not connected:
        print("❌ No se pudo conectar")
        return

    authorized = await api.authorize()
    if not authorized:
        print("❌ No se pudo autorizar")
        return

    print("\n📈 Obteniendo ticks de Volatility 75...\n")
    await api.get_ticks("R_75")

    await api.close()

    print("\n✅ Prueba completada exitosamente!")


if __name__ == "__main__":
    asyncio.run(test_connection())
