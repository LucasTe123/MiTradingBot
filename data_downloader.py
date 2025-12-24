import asyncio
import pandas as pd
from datetime import datetime
from deriv_websocket import DerivAPI



async def download_all_data():
    print("="*60)
    print("📊 DESCARGANDO DATOS HISTÓRICOS DE DERIV")
    print("="*60 + "\n")
    
    # Descargar 100,000 ticks
    print("📥 Descargando 100,000 ticks de R_75...\n")
    
    connection = DerivAPI()
    all_ticks = []
    
    # Descargar en 20 lotes de 5000
    for i in range(20):
        try:
            response = await connection.ticks_history({
                "ticks_history": "R_75",
                "count": 5000,
                "end": "latest",
                "style": "ticks"
            })
            
            if 'history' in response:
                ticks = response['history']['prices']
                times = response['history']['times']
                
                for j in range(len(ticks)):
                    all_ticks.append({
                        'timestamp': times[j],
                        'price': float(ticks[j]),
                        'datetime': datetime.fromtimestamp(times[j])
                    })
                
                print(f"   ✓ Descargados {len(all_ticks)}/100000 ticks")
                
        except Exception as e:
            print(f"   ⚠ Error en lote {i+1}: {str(e)}")
            break
        
        await asyncio.sleep(1)
    
    # Guardar ticks
    df_ticks = pd.DataFrame(all_ticks)
    df_ticks.to_csv("data/R_75_ticks_100000.csv", index=False)
    print(f"\n✅ {len(all_ticks)} ticks guardados en data/R_75_ticks_100000.csv\n")
    
    # Descargar 10,000 velas
    print("📥 Descargando 10,000 velas de R_75...\n")
    
    all_candles = []
    
    # Descargar en 2 lotes de 5000
    for i in range(2):
        try:
            response = await connection.ticks_history({
                "ticks_history": "R_75",
                "count": 5000,
                "end": "latest",
                "style": "candles",
                "granularity": 60
            })
            
            if 'candles' in response:
                candles = response['candles']
                
                for candle in candles:
                    all_candles.append({
                        'timestamp': candle['epoch'],
                        'open': float(candle['open']),
                        'high': float(candle['high']),
                        'low': float(candle['low']),
                        'close': float(candle['close']),
                        'datetime': datetime.fromtimestamp(candle['epoch'])
                    })
                
                print(f"   ✓ Descargadas {len(all_candles)}/10000 velas")
                
        except Exception as e:
            print(f"   ⚠ Error en lote {i+1}: {str(e)}")
            break
        
        await asyncio.sleep(1)
    
    # Guardar velas
    df_candles = pd.DataFrame(all_candles)
    df_candles.to_csv("data/R_75_candles_60s_10000.csv", index=False)
    print(f"\n✅ {len(all_candles)} velas guardadas en data/R_75_candles_60s_10000.csv\n")
    
    print("="*60)
    print("✅ DESCARGA COMPLETADA")
    print("="*60)
    print("\n💡 Total descargado:")
    print(f"   - {len(all_ticks)} ticks")
    print(f"   - {len(all_candles)} velas")

if __name__ == "__main__":
    asyncio.run(download_all_data())
