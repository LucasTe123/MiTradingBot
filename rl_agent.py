# ============================================
# AGENTE DE REINFORCEMENT LEARNING
# ============================================


import os
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback
from trading_env import TradingEnv
from telegram_bot import TelegramNotifier
import asyncio


class TrainingCallback(BaseCallback):
    """Callback para monitorear entrenamiento"""
    
    def __init__(self, check_freq, save_path, verbose=1):
        super(TrainingCallback, self).__init__(verbose)
        self.check_freq = check_freq
        self.save_path = save_path
        self.best_mean_reward = -float('inf')
        
    def _on_step(self):
        if self.n_calls % self.check_freq == 0:
            # Guardar modelo cada cierto número de pasos
            model_path = f"{self.save_path}/model_checkpoint_{self.n_calls}"
            self.model.save(model_path)
            
            if self.verbose > 0:
                print(f"✅ Checkpoint guardado: {model_path}")
        
        return True


class RLAgent:
    """Agente de RL para trading"""
    
    def __init__(self, env, model_name="trading_bot"):
        self.env = env
        self.model_name = model_name
        self.model = None
        
    def create_model(self, learning_rate=0.0003):
        """Crear nuevo modelo PPO"""
        print("🧠 Creando modelo PPO...")
        
        self.model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=learning_rate,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            verbose=1,
            tensorboard_log="./logs/"
        )
        
        print("✅ Modelo creado!")
        return self.model
    
    def train(self, total_timesteps=100000, save_freq=10000):
        """Entrenar el modelo"""
        print(f"🚀 Iniciando entrenamiento: {total_timesteps} pasos\n")
        
        # Crear directorio para modelos si no existe
        os.makedirs("models", exist_ok=True)
        
        # Callback para guardar progreso
        callback = TrainingCallback(
            check_freq=save_freq,
            save_path="models",
            verbose=1
        )
        
        # Entrenar
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            tb_log_name=self.model_name
        )
        
        # Guardar modelo final
        final_path = f"models/{self.model_name}_final"
        self.model.save(final_path)
        print(f"\n✅ Entrenamiento completado!")
        print(f"💾 Modelo guardado en: {final_path}")
        
        return self.model
    
    def load_model(self, path):
        """Cargar modelo entrenado"""
        print(f"📂 Cargando modelo desde: {path}")
        self.model = PPO.load(path, env=self.env)
        print("✅ Modelo cargado!")
        return self.model
    
    def test(self, num_episodes=10):
        """Probar el modelo entrenado"""
        print(f"\n🧪 Probando modelo ({num_episodes} episodios)...\n")
        
        results = []
        
        for episode in range(num_episodes):
            # Usar el ambiente vectorizado (self.env es DummyVecEnv)
            obs = self.env.reset()  # Devuelve solo obs, no tupla
            done = False
            episode_reward = 0.0
            
            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, done, info = self.env.step(action)
                
                # reward puede ser array [valor], convertir a float
                episode_reward += float(reward[0]) if hasattr(reward, '__iter__') else float(reward)
                
                # done puede ser array [True/False]
                done = done[0] if hasattr(done, '__iter__') else done
            
            # Acceder al ambiente original para métricas
            env_original = self.env.envs[0]
            
            win_rate = (env_original.winning_trades / env_original.total_trades * 100) if env_original.total_trades > 0 else 0
            
            results.append({
                'episode': episode + 1,
                'balance': env_original.balance,
                'trades': env_original.total_trades,
                'wins': env_original.winning_trades,
                'win_rate': win_rate,
                'reward': episode_reward
            })
            
            print(f"Episodio {episode+1}: Balance=${env_original.balance:.2f} | "
                  f"Trades={env_original.total_trades} | Win Rate={win_rate:.1f}% | "
                  f"Reward={episode_reward:.2f}")
        
        # Calcular estadísticas
        df_results = pd.DataFrame(results)
        print(f"\n📊 RESULTADOS:")
        print(f"Balance promedio: ${df_results['balance'].mean():.2f}")
        print(f"Win rate promedio: {df_results['win_rate'].mean():.1f}%")
        print(f"Trades promedio: {df_results['trades'].mean():.1f}")
        
        return df_results


# ============================================
# FUNCIÓN DE ENTRENAMIENTO
# ============================================


def train_bot():
    """Entrenar el bot desde cero"""
    print("="*60)
    print("🤖 ENTRENAMIENTO DE BOT DE TRADING CON RL")
    print("="*60 + "\n")
    
    # Cargar datos
    print("📊 Cargando datos históricos...")
    df = pd.read_csv("data/R_75_ticks_10000.csv")
    print(f"✅ {len(df)} registros cargados\n")
    
    # Crear ambiente
    print("🎮 Creando ambiente de trading...")
    env = TradingEnv(df)
    env = DummyVecEnv([lambda: env])
    print("✅ Ambiente creado\n")
    
    # Crear agente
    agent = RLAgent(env, model_name="deriv_bot_v1")
    agent.create_model(learning_rate=0.0003)
    
    # Entrenar (empezamos con 50k pasos para prueba rápida)
    print("\n" + "="*60)
    print("Esto tomará aproximadamente 5-10 minutos...")
    print("="*60 + "\n")
    
    agent.train(total_timesteps=200000, save_freq=20000)

    
    # Probar modelo
    agent.test(num_episodes=5)
    
    print("\n" + "="*60)
    print("✅ ENTRENAMIENTO COMPLETADO")
    print("="*60)
    print("\n💡 Para entrenar más: aumenta total_timesteps a 100000-400000")
    print("💡 Para ver progreso: tensorboard --logdir=./logs/")


if __name__ == "__main__":
    train_bot()
