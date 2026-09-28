using System;
using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Every tunable number in one place. Create an asset via
    /// Assets > Create > Ojol Rush > Game Config, name it "OjolRushConfig" and put it in a
    /// Resources folder to override these defaults without touching code.
    /// </summary>
    [CreateAssetMenu(menuName = "Ojol Rush/Game Config", fileName = "OjolRushConfig")]
    public class GameConfig : ScriptableObject
    {
        [Header("Bike")]
        public float maxSpeed = 17f;
        public float acceleration = 7f;
        public float brakeDeceleration = 14f;
        [Tooltip("Speed factor while the thumb is held still (slow down to thread a gap).")]
        public float holdSpeedFactor = 0.45f;
        public float turnRateLow = 280f;
        public float turnRateHigh = 170f;
        [Tooltip("Sharp direction changes above this angle bleed speed.")]
        public float sharpTurnAngle = 100f;
        public float grip = 9f;
        public float puddleGrip = 1.3f;
        public float puddleSlideTime = 0.8f;
        public float rainGripFactor = 0.55f;
        public float sidewalkSpeedFactor = 0.75f;
        public float gangSpeedFactor = 0.95f;
        public float floodSpeedFactor = 0.4f;
        public float playerRadius = 0.55f;
        public float bumpJumpTime = 0.35f;

        [Header("Helmet health")]
        public int helmets = 3;
        [Tooltip("Closing speed (m/s) into a vehicle that counts as a heavy crash.")]
        public float heavyCrashSpeed = 7f;
        public float invulnerableTime = 1.6f;

        [Header("Near miss & combo")]
        public float nearMissDistance = 1.1f;
        public float nearMissMinSpeed = 8f;
        public int nearMissPoints = 50;
        public float comboWindow = 2f;
        public int maxComboMultiplier = 10;

        [Header("Delivery scoring")]
        public int deliveryBase = 500;
        public int speedBonusPerSecond = 15;
        [Tooltip("Tip points by star rating (index = stars).")]
        public int[] tipsByStars = { 0, 0, 0, 50, 120, 300 };

        [Header("Rating")]
        public float ratingGameOver = 3.0f;
        public int ratingHistory = 10;
        public int ratingSeedCount = 3;

        [Header("Orders")]
        public float orderBaseTime = 12f;
        public float orderReferenceSpeed = 8.5f;
        public float markerRadius = 4f;
        public float nextOrderDelay = 1.5f;
        [Range(0f, 1f)] public float foodOrderChance = 0.6f;
        public float pickupMinDistance = 60f;
        public float pickupMaxDistance = 170f;
        public float dropoffMinDistance = 110f;
        public float dropoffMaxDistance = 260f;

        [Header("Hazards")]
        public float raziaStopTime = 2.5f;
        public float raziaTimePenalty = 8f;

        [Header("Juice")]
        public float hitStop = 0.06f;
        public float crashShake = 0.7f;
        public float bumpShake = 0.25f;

        [Header("Rush levels (index 0 = Rush 1)")]
        public RushLevelConfig[] rushLevels = RushLevelConfig.Defaults();

        public static GameConfig Load()
        {
            GameConfig cfg = Resources.Load<GameConfig>("OjolRushConfig");
            if (cfg == null) cfg = CreateInstance<GameConfig>();
            if (cfg.rushLevels == null || cfg.rushLevels.Length == 0) cfg.rushLevels = RushLevelConfig.Defaults();
            return cfg;
        }
    }

    [Serializable]
    public class RushLevelConfig
    {
        public string title = "RUSH";
        [Tooltip("Total deliveries needed to reach this level.")]
        public int deliveriesToReach;
        public int trafficCount = 30;
        public float trafficSpeedMultiplier = 1f;
        [Header("Spawn weights")]
        public float car = 0.35f;
        public float angkot = 0.15f;
        public float bajaj = 0.1f;
        public float bus = 0.05f;
        public float motorbike = 0.35f;
        [Header("World")]
        public int waitingPassengers = 6;
        public float timerMultiplier = 1.5f;
        [Tooltip("Chance per 20 s check that a rain shower starts.")]
        public float rainChance;
        public bool alwaysRain;
        public int floodZones;
        public int raziaCount;
        public float catInterval = 9f;
        public float honkRate = 0.3f;
        public float lightGreenTime = 9f;

        public static RushLevelConfig[] Defaults()
        {
            return new[]
            {
                new RushLevelConfig { title = "Santai", deliveriesToReach = 0, trafficCount = 28, waitingPassengers = 5, timerMultiplier = 1.55f, catInterval = 10f, honkRate = 0.2f },
                new RushLevelConfig { title = "Mulai Padat", deliveriesToReach = 2, trafficCount = 40, angkot = 0.22f, car = 0.3f, waitingPassengers = 14, timerMultiplier = 1.3f, catInterval = 8f, honkRate = 0.35f },
                new RushLevelConfig { title = "Hujan Lokal", deliveriesToReach = 4, trafficCount = 50, angkot = 0.2f, car = 0.3f, waitingPassengers = 14, timerMultiplier = 1.12f, rainChance = 0.45f, raziaCount = 1, catInterval = 7f, honkRate = 0.5f },
                new RushLevelConfig { title = "Jam Pulang Kantor", deliveriesToReach = 6, trafficCount = 64, bus = 0.12f, car = 0.28f, angkot = 0.2f, motorbike = 0.3f, waitingPassengers = 16, timerMultiplier = 1.0f, rainChance = 0.5f, floodZones = 2, raziaCount = 2, catInterval = 6f, honkRate = 0.8f, lightGreenTime = 7f },
                new RushLevelConfig { title = "MACET TOTAL", deliveriesToReach = 9, trafficCount = 95, trafficSpeedMultiplier = 0.75f, bus = 0.14f, car = 0.3f, angkot = 0.2f, bajaj = 0.1f, motorbike = 0.26f, waitingPassengers = 22, timerMultiplier = 0.75f, alwaysRain = true, floodZones = 4, raziaCount = 3, catInterval = 4f, honkRate = 1.6f, lightGreenTime = 5f },
            };
        }
    }
}
