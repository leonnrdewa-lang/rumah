using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Escalation arc: deliveries push the rush level up (1..5), which feeds traffic density,
    /// timers and world events (rain showers, flooded streets, razia checkpoints).
    /// </summary>
    public class RushLevelManager : MonoBehaviour
    {
        GameManager gm;
        GameConfig cfg;
        System.Random rng;

        public int LevelIndex { get; private set; }
        public RushLevelConfig Level { get { return cfg.rushLevels[LevelIndex]; } }
        public int LevelNumber { get { return LevelIndex + 1; } }
        public bool Raining { get; private set; }
        public float RainAmount { get; private set; }

        float rainTimer;
        float rainCheck;
        bool firstRainPending;

        Light sun;
        Color sunColor, fogColor, ambientSky;
        float sunIntensity;

        public void Init(GameManager game, System.Random random, Light sunLight)
        {
            gm = game;
            cfg = game.config;
            rng = random;
            sun = sunLight;
            sunColor = sun.color;
            sunIntensity = sun.intensity;
            fogColor = RenderSettings.fogColor;
            ambientSky = RenderSettings.ambientSkyColor;
        }

        public void ResetLevels()
        {
            LevelIndex = 0;
            Raining = false;
            RainAmount = 0f;
            rainCheck = 20f;
            firstRainPending = false;
            ApplyWeather();
        }

        public void OnDeliveriesChanged(int deliveries)
        {
            int lvl = RushRules.LevelForDeliveries(cfg.rushLevels, deliveries) - 1;
            if (lvl <= LevelIndex) return;
            LevelIndex = Mathf.Min(lvl, cfg.rushLevels.Length - 1);
            RushLevelConfig l = Level;
            gm.traffic.SetLevel(l);
            gm.hazards.SetLevel(l, false);
            gm.hud.BigBanner("RUSH " + LevelNumber + "!", l.title);
            gm.audioManager.Play("levelup", 0.9f, 1f);
            if (l.rainChance > 0f && !Raining) firstRainPending = true; // show off the new event soon
        }

        public void Tick(float dt)
        {
            if (dt <= 0f) return;
            RushLevelConfig l = Level;
            if (gm.State == GameState.Playing)
            {
                if (l.alwaysRain && !Raining) StartRain(999f);
                if (Raining)
                {
                    rainTimer -= dt;
                    if (rainTimer <= 0f && !l.alwaysRain) StopRain();
                }
                else if (l.rainChance > 0f)
                {
                    rainCheck -= dt;
                    if (firstRainPending && rainCheck > 6f) rainCheck = 6f;
                    if (rainCheck <= 0f)
                    {
                        rainCheck = 20f;
                        if (firstRainPending || rng.NextDouble() < l.rainChance)
                        {
                            firstRainPending = false;
                            StartRain(22f + (float)rng.NextDouble() * 12f);
                        }
                    }
                }
            }
            RainAmount = Mathf.MoveTowards(RainAmount, Raining ? 1f : 0f, dt * 0.5f);
            ApplyWeather();
        }

        void StartRain(float duration)
        {
            Raining = true;
            rainTimer = duration;
            gm.hazards.SetRain(true);
            gm.hud.Banner("HUJAN! Jalanan licin", new Color(0.55f, 0.8f, 1f));
            gm.audioManager.SetRain(true);
        }

        void StopRain()
        {
            Raining = false;
            gm.hazards.SetRain(false);
            gm.hud.Banner("Hujan reda", new Color(1f, 0.85f, 0.5f));
            gm.audioManager.SetRain(false);
        }

        public void ForceStopWeather()
        {
            if (Raining) StopRain();
            RainAmount = 0f;
            ApplyWeather();
        }

        void ApplyWeather()
        {
            float r = RainAmount;
            Color grey = new Color(0.55f, 0.6f, 0.68f);
            sun.color = Color.Lerp(sunColor, grey, r * 0.8f);
            sun.intensity = Mathf.Lerp(sunIntensity, sunIntensity * 0.45f, r);
            RenderSettings.fogColor = Color.Lerp(fogColor, new Color(0.5f, 0.55f, 0.62f), r);
            RenderSettings.fogStartDistance = Mathf.Lerp(70f, 35f, r);
            RenderSettings.ambientSkyColor = Color.Lerp(ambientSky, new Color(0.45f, 0.5f, 0.6f), r);
            gm.cameraManager.SetSkyTint(r);
        }
    }
}
