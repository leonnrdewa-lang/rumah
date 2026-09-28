using UnityEngine;

namespace OjolRush
{
    public enum GameState { Title, Playing, GameOver }

    /// <summary>
    /// Owns every subsystem, the run state machine and the explicit per-frame update order:
    /// input -> player -> traffic -> hazards -> contacts (crash / near miss) -> orders -> rush level
    /// -> camera / fx / audio / HUD. Everything is built procedurally, so the game runs from any scene.
    /// </summary>
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        public GameConfig config;
        public CityMap city;
        public PlayerBikeController player;
        public TrafficManager traffic;
        public HazardManager hazards;
        public OrderManager orders;
        public RushLevelManager rush;
        public CameraManager cameraManager;
        public AudioManager audioManager;
        public FxManager fx;
        public HUD hud;
        public PoolManager pools;
        public ScoreManager score;
        public ComboSystem combo;
        public RatingTracker rating;
        public PlayerInput input;

        public GameState State { get; private set; }
        public bool Paused { get; private set; }
        public string GameOverReason { get; private set; }
        public float GameOverTime { get; private set; }
        public int BestScore { get; private set; }
        public bool NewBest { get; private set; }

        const string BestKey = "OjolRush_Best";
        const string ControlKey = "OjolRush_Control";

        System.Random rng;
        float hitStop;
        float popupCooldown;
        Vector2 startPos;
        float startHeading;

        void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            Application.targetFrameRate = 60;
            Screen.sleepTimeout = SleepTimeout.NeverSleep;
            if (Application.isMobilePlatform) Screen.orientation = ScreenOrientation.Portrait;

            config = GameConfig.Load();
            rng = new System.Random();
            pools = new PoolManager();
            score = new ScoreManager(config);
            combo = new ComboSystem(config.comboWindow, config.maxComboMultiplier);
            rating = new RatingTracker(config.ratingHistory, config.ratingSeedCount);
            input = new PlayerInput();
            input.mode = (ControlMode)PlayerPrefs.GetInt(ControlKey, 0);
            BestScore = PlayerPrefs.GetInt(BestKey, 0);

            Light sun = SetupEnvironment();

            city = new CityMap();
            city.BuildSpots(new System.Random(1234));
            new CityBuilder(city, new System.Random(4321), transform).Build();

            cameraManager = Child<CameraManager>("Camera");
            cameraManager.Init(this);
            audioManager = Child<AudioManager>("Audio");
            audioManager.Init(this);
            fx = Child<FxManager>("Fx");
            fx.Init(this);
            hud = Child<HUD>("HUD");
            hud.Init(this);
            player = Child<PlayerBikeController>("Player");
            player.Init(this);
            hazards = Child<HazardManager>("Hazards");
            hazards.Init(this, city, rng);
            traffic = Child<TrafficManager>("TrafficManager");
            traffic.Init(this, city, rng, pools);
            orders = Child<OrderManager>("Orders");
            orders.Init(this, city, rng);
            rush = Child<RushLevelManager>("Rush");
            rush.Init(this, rng, sun);

            startPos = new Vector2(2f * CityMap.Pitch - CityMap.LaneWidth * 1.5f, CityMap.Pitch + 14f);
            startHeading = 0f;
            EnterTitle();
        }

        T Child<T>(string name) where T : Component
        {
            GameObject go = new GameObject(name);
            go.transform.SetParent(transform, false);
            return go.AddComponent<T>();
        }

        Light SetupEnvironment()
        {
            // Take over from whatever the scene had (e.g. the template's Main Camera / Directional Light).
            foreach (Camera c in FindObjectsOfType<Camera>()) c.gameObject.SetActive(false);
            foreach (AudioListener l in FindObjectsOfType<AudioListener>()) l.enabled = false;
            foreach (Light l in FindObjectsOfType<Light>()) if (l.type == LightType.Directional) l.gameObject.SetActive(false);

            GameObject sg = new GameObject("GoldenHourSun");
            sg.transform.SetParent(transform, false);
            Light sun = sg.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.color = new Color(1f, 0.8f, 0.58f);
            sun.intensity = 1.25f;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 0.55f;
            sg.transform.rotation = Quaternion.Euler(38f, 58f, 0f);
            RenderSettings.sun = sun;

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.86f, 0.74f, 0.64f);
            RenderSettings.ambientEquatorColor = new Color(0.64f, 0.56f, 0.5f);
            RenderSettings.ambientGroundColor = new Color(0.36f, 0.31f, 0.28f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.97f, 0.76f, 0.55f);
            RenderSettings.fogStartDistance = 70f;
            RenderSettings.fogEndDistance = 170f;
            QualitySettings.shadowDistance = 90f;
            return sun;
        }

        // ------------------------------------------------------------------ state machine

        void EnterTitle()
        {
            State = GameState.Title;
            // Waiting for orders at the curb, like every ojol between jobs.
            player.ResetAt(startPos + new Vector2(-(CityMap.CorridorHalf - 1.2f) + CityMap.LaneWidth * 1.5f, 0f), 180f);
            player.Park();
            cameraManager.Snap(player.Pos);
            rush.ResetLevels();
            hazards.ResetHazards(rush.Level);
            traffic.ResetTraffic(rush.Level);
            orders.ResetOrders();
        }

        public void StartRun()
        {
            State = GameState.Playing;
            Paused = false;
            hitStop = 0f;
            NewBest = false;
            score.Reset();
            combo.Reset();
            rating.Reset();
            rush.ForceStopWeather();
            rush.ResetLevels();
            player.ResetAt(startPos, startHeading);
            cameraManager.Snap(player.Pos);
            hazards.ResetHazards(rush.Level);
            traffic.ResetTraffic(rush.Level);
            orders.ResetOrders();
            fx.Clear();
            hud.ClearAll();
            hud.BigBanner("GAS!", "Shift dimulai - antar semua order!");
            input.ResetState();
        }

        void GameOver(string reason)
        {
            if (State != GameState.Playing) return;
            State = GameState.GameOver;
            GameOverReason = reason;
            GameOverTime = 0f;
            player.Park();
            if (score.Score > BestScore)
            {
                BestScore = score.Score;
                NewBest = true;
                PlayerPrefs.SetInt(BestKey, BestScore);
                PlayerPrefs.Save();
            }
            audioManager.Play("gameover", 0.9f, 1f);
        }

        public void TogglePause()
        {
            if (State != GameState.Playing) return;
            Paused = !Paused;
            if (!Paused) input.ResetState();
        }

        public void SetControlMode(ControlMode m)
        {
            input.mode = m;
            PlayerPrefs.SetInt(ControlKey, (int)m);
            PlayerPrefs.Save();
        }

        void OnApplicationPause(bool paused)
        {
            if (paused && State == GameState.Playing && !Paused) Paused = true;
        }

        // ------------------------------------------------------------------ frame

        void Update()
        {
            float unscaled = Mathf.Min(Time.unscaledDeltaTime, 0.1f);
            float dt = Mathf.Min(Time.deltaTime, 0.05f);
            if (hitStop > 0f)
            {
                hitStop -= unscaled;
                dt = 0f;
            }
            if (popupCooldown > 0f) popupCooldown -= unscaled;

            input.blockedScreenRect = State == GameState.Playing ? hud.PauseButtonScreenRect : new Rect();
            input.Update();
            if (input.PausePressed) TogglePause();
            if (Paused) dt = 0f;

            switch (State)
            {
                case GameState.Playing:
                    player.Tick(dt, input, rush.Raining, hazards.PlayerInFlood);
                    traffic.Tick(dt);
                    hazards.Tick(dt);
                    hazards.CheckPlayer(player, dt);
                    if (dt > 0f) VehicleContacts();
                    combo.Tick(dt);
                    orders.Tick(dt);
                    rush.Tick(dt);
                    break;
                default:
                    if (State == GameState.GameOver) GameOverTime += unscaled;
                    traffic.Tick(dt);
                    hazards.Tick(dt);
                    orders.Tick(dt);
                    rush.Tick(dt);
                    break;
            }
        }

        void LateUpdate()
        {
            float unscaled = Mathf.Min(Time.unscaledDeltaTime, 0.1f);
            float dt = (Paused || hitStop > 0f) ? 0f : Mathf.Min(Time.deltaTime, 0.05f);
            cameraManager.LateTick(dt, unscaled);
            fx.Tick(dt, rush.RainAmount);
            audioManager.Tick(unscaled, State == GameState.Playing && !Paused);
            hud.Tick(Paused ? 0f : unscaled);
        }

        // ------------------------------------------------------------------ contacts

        void VehicleContacts()
        {
            float r = config.playerRadius;
            Vector2 pp = player.Pos;
            for (int i = 0; i < traffic.vehicles.Count; i++)
            {
                TrafficVehicle v = traffic.vehicles[i];
                Vector2 rel = pp - v.pos;
                float reach = v.HalfLength + 4f;
                if (rel.sqrMagnitude > reach * reach)
                {
                    v.nearMissArmed = true;
                    continue;
                }
                Vector2 closest;
                bool inside = Geo.ClosestOnObb(v.pos, v.fwd, v.HalfLength, v.HalfWidth, pp, out closest);
                Vector2 delta = pp - closest;
                float dist = delta.magnitude;
                if (inside || dist < r)
                {
                    Vector2 n;
                    if (dist < 0.0001f) n = Geo.Left(v.fwd) * (Vector2.Dot(rel, Geo.Left(v.fwd)) >= 0f ? 1f : -1f);
                    else n = inside ? -delta / dist : delta / dist;
                    player.Pos = closest + n * (r + 0.02f);
                    pp = player.Pos;
                    float closing = Vector2.Dot(player.Velocity - v.Velocity, -n);
                    bool heavy = closing > config.heavyCrashSpeed && player.Invulnerable <= 0f;
                    Crash(heavy, n, v.Velocity, Geo.X0Z(closest, 1f));
                    v.OnHitByPlayer();
                    v.nearMissArmed = false;
                    if (v.honkCooldown <= 0f)
                    {
                        v.honkCooldown = 2f;
                        audioManager.PlayHorn(v.transform.position, v.type);
                    }
                    continue;
                }
                float gap = dist - r;
                if (gap > 3f)
                {
                    v.nearMissArmed = true;
                }
                else if (gap < config.nearMissDistance && v.nearMissArmed && player.Speed > config.nearMissMinSpeed
                         && player.Invulnerable <= 0f && (player.Velocity - v.Velocity).magnitude > 4f)
                {
                    v.nearMissArmed = false;
                    NearMiss(v);
                }
            }
        }

        void NearMiss(TrafficVehicle v)
        {
            int mult = combo.RegisterNearMiss();
            int pts = score.AddNearMiss(mult);
            string t = mult > 1 ? "SALIP x" + mult + "!  +" + pts : "SALIP! +" + pts;
            Color c = Color.Lerp(new Color(1f, 0.95f, 0.3f), new Color(1f, 0.4f, 0.95f), Mathf.Clamp01((mult - 1) / 8f));
            hud.Popup(v.transform.position + Vector3.up * 2.5f, t, c, 0.8f + Mathf.Min(mult, 8) * 0.05f);
            hud.SpeedLines();
            hud.ComboPulse();
            cameraManager.Kick(0.6f);
            audioManager.Play("whoosh", 0.8f, 0.9f + Mathf.Min(mult, 10) * 0.05f);
        }

        void Crash(bool heavy, Vector2 n, Vector2 otherVel, Vector3 at)
        {
            combo.Break();
            if (heavy)
            {
                player.Helmets--;
                player.ApplyHit(n, otherVel, true);
                hitStop = config.hitStop;
                cameraManager.Shake(config.crashShake);
                hud.CrashFlash(true);
                fx.Emit(FxKind.Spark, at, 22);
                fx.Emit(FxKind.Dust, at, 10);
                audioManager.Play("crash", 1f, 0.95f + Random.value * 0.1f);
                hud.Popup(at + Vector3.up, "BRAK!", new Color(1f, 0.3f, 0.2f), 1.4f);
                string spill = orders.OnHeavyCrash();
                if (spill != null)
                {
                    hud.Popup(Geo.X0Z(player.Pos, 3f), spill + " -" + (spill == "TUMPAH!" ? 2 : 1) + " bintang", new Color(1f, 0.6f, 0.2f), 1.1f);
                    fx.Emit(FxKind.Confetti, Geo.X0Z(player.Pos, 1.2f), 10);
                }
                if (player.Helmets <= 0) GameOver("Helm hancur! Kebanyakan nabrak.");
            }
            else
            {
                player.ApplyHit(n, otherVel, false);
                cameraManager.Shake(config.bumpShake);
                hud.CrashFlash(false);
                fx.Emit(FxKind.Dust, at, 5);
                audioManager.Play("bump", 0.8f, 1f);
                if (popupCooldown <= 0f)
                {
                    popupCooldown = 0.6f;
                    hud.Popup(at + Vector3.up, "DUK!", new Color(1f, 0.85f, 0.6f), 0.9f);
                }
            }
        }

        // ------------------------------------------------------------------ events from subsystems

        public void OnPlayerHitObstacle(Vector2 n, Vector2 closest, Vector2 otherVel, string label, TrafficVehicle v)
        {
            player.Pos = closest + n * (config.playerRadius + 0.02f);
            float closing = Vector2.Dot(player.Velocity - otherVel, -n);
            bool heavy = closing > config.heavyCrashSpeed && player.Invulnerable <= 0f;
            Crash(heavy, n, otherVel, Geo.X0Z(closest, 1f));
            if (heavy) hud.Popup(Geo.X0Z(closest, 3f), label, new Color(1f, 0.7f, 0.3f), 1f);
        }

        public void OnCritterHit(Vector3 at, string text, string sound, FxKind kind, bool complaint)
        {
            combo.Break();
            fx.Emit(kind, at, kind == FxKind.Feather ? 16 : 8);
            audioManager.Play(sound, 0.8f, 0.95f + Random.value * 0.15f);
            hud.Popup(at + Vector3.up, text, new Color(1f, 0.9f, 0.5f), 1f);
            cameraManager.Shake(config.bumpShake);
            if (complaint)
            {
                orders.AddComplaint();
                hud.Banner("Komplain warga! -1 bintang", new Color(1f, 0.5f, 0.4f));
            }
            else
            {
                player.Speed *= 0.7f;
            }
        }

        public void OnPothole(Vector2 at)
        {
            cameraManager.Shake(config.bumpShake);
            audioManager.Play("bump", 0.9f, 0.8f);
            fx.Emit(FxKind.Dust, Geo.X0Z(at, 0.2f), 6);
            if (popupCooldown <= 0f)
            {
                popupCooldown = 0.8f;
                hud.Popup(Geo.X0Z(at, 2f), "JEGLONG!", new Color(0.9f, 0.8f, 0.7f), 0.8f);
            }
        }

        public void OnSpeedBumpJump(Vector2 at)
        {
            audioManager.Play("bump", 0.6f, 1.3f);
            fx.Emit(FxKind.Dust, Geo.X0Z(at, 0.1f), 5);
            if (popupCooldown <= 0f)
            {
                popupCooldown = 0.8f;
                hud.Popup(Geo.X0Z(at, 2f), "POLISI TIDUR!", new Color(1f, 0.9f, 0.3f), 0.75f);
            }
        }

        public void OnLanded(Vector2 at)
        {
            cameraManager.Shake(0.2f);
            audioManager.Play("bump", 0.7f, 0.9f);
            fx.Emit(FxKind.Dust, Geo.X0Z(at, 0.1f), 8);
        }

        public void OnWallBump(Vector2 at, float into)
        {
            combo.Break();
            cameraManager.Shake(config.bumpShake);
            audioManager.Play("bump", 0.8f, 0.9f);
            fx.Emit(FxKind.Dust, Geo.X0Z(at, 0.5f), 6);
            if (popupCooldown <= 0f)
            {
                popupCooldown = 0.6f;
                hud.Popup(Geo.X0Z(at, 2f), "DUK!", new Color(1f, 0.85f, 0.6f), 0.9f);
            }
        }

        public void OnRazia(Vector3 at)
        {
            combo.Break();
            orders.AddTimePenalty(config.raziaTimePenalty);
            audioManager.Play("siren", 0.8f, 1f);
            cameraManager.Shake(0.3f);
            hud.Popup(at, "KENA RAZIA! -" + Mathf.RoundToInt(config.raziaTimePenalty) + " dtk", new Color(1f, 0.35f, 0.3f), 1.2f);
            hud.Banner("\"Selamat sore, SIM dan STNK-nya?\"", new Color(1f, 0.8f, 0.6f));
        }

        public void OnDelivered(Order o, int stars, Vector3 at)
        {
            int pts = score.DeliveryPoints(o.timeLeft, stars);
            int tip = score.Tip(stars);
            score.AddDelivery(pts, tip);
            rating.Record(stars);
            fx.Emit(FxKind.Confetti, at, 40);
            audioManager.Play("chaching", 1f, 1f);
            hud.Popup(at, "PESANAN SAMPAI! +" + pts, Palette.OjolGreen, 1.2f);
            hud.ScreenPopup(new Vector2(0.5f, 0.52f), "BINTANG " + stars + (stars == 5 ? " - MANTAP!" : ""), new Color(1f, 0.85f, 0.2f), 1.2f);
            if (tip > 0) hud.ScreenPopup(new Vector2(0.5f, 0.58f), "TIP +" + tip, new Color(0.7f, 1f, 0.6f), 1f);
            rush.OnDeliveriesChanged(score.Deliveries);
            CheckRating();
        }

        public void OnOrderFailed(Order o)
        {
            rating.Record(1);
            audioManager.Play("bump", 1f, 0.6f);
            hud.ScreenPopup(new Vector2(0.5f, 0.5f), "ORDER DIBATALKAN - BINTANG 1", new Color(1f, 0.35f, 0.3f), 1.1f);
            hud.Banner("Customer kecewa... rating turun", new Color(1f, 0.5f, 0.4f));
            CheckRating();
        }

        void CheckRating()
        {
            if (rating.Average < config.ratingGameOver) GameOver("Rating anjlok - akun dibekukan!");
        }
    }
}
