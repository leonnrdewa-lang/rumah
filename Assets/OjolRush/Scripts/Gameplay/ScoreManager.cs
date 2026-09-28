using System;
using System.Collections.Generic;

namespace OjolRush
{
    /// <summary>Score maths. Pure C# so it can be unit tested outside the engine.</summary>
    public class ScoreManager
    {
        readonly GameConfig cfg;

        public int Score { get; private set; }
        public int Deliveries { get; private set; }
        public int NearMisses { get; private set; }
        public int TotalTips { get; private set; }

        public ScoreManager(GameConfig cfg) { this.cfg = cfg; }

        public void Reset()
        {
            Score = 0;
            Deliveries = 0;
            NearMisses = 0;
            TotalTips = 0;
        }

        public int AddNearMiss(int multiplier)
        {
            int pts = cfg.nearMissPoints * Math.Max(1, multiplier);
            NearMisses++;
            Score += pts;
            return pts;
        }

        /// <summary>(base + speed bonus) x star multiplier, where 3 stars = x1.</summary>
        public int DeliveryPoints(float timeLeft, int stars)
        {
            float bonus = Math.Max(0f, timeLeft) * cfg.speedBonusPerSecond;
            return (int)Math.Round((cfg.deliveryBase + bonus) * (stars / 3f));
        }

        public int Tip(int stars)
        {
            int[] tips = cfg.tipsByStars;
            if (tips == null || tips.Length == 0) return 0;
            int i = Math.Max(0, Math.Min(stars, tips.Length - 1));
            return tips[i];
        }

        public void AddDelivery(int points, int tip)
        {
            Deliveries++;
            Score += points + tip;
            TotalTips += tip;
        }

        public void AddRaw(int points) { Score += points; }
    }

    /// <summary>Driver rating = average of the last N order ratings, seeded with 5-star history.</summary>
    public class RatingTracker
    {
        readonly int history;
        readonly int seedCount;
        readonly List<int> stars = new List<int>();

        public RatingTracker(int history, int seedCount)
        {
            this.history = Math.Max(1, history);
            this.seedCount = seedCount;
            Reset();
        }

        public void Reset()
        {
            stars.Clear();
            for (int i = 0; i < seedCount; i++) stars.Add(5);
        }

        public void Record(int s)
        {
            stars.Add(Math.Max(1, Math.Min(5, s)));
            while (stars.Count > history) stars.RemoveAt(0);
        }

        public float Average
        {
            get
            {
                if (stars.Count == 0) return 5f;
                float sum = 0f;
                for (int i = 0; i < stars.Count; i++) sum += stars[i];
                return sum / stars.Count;
            }
        }
    }

    /// <summary>Order timer and star rules.</summary>
    public static class OrderRules
    {
        public static float Manhattan(float ax, float az, float bx, float bz)
        {
            return Math.Abs(ax - bx) + Math.Abs(az - bz);
        }

        public static float TimeLimit(GameConfig cfg, float routeDistance, float levelMultiplier)
        {
            return cfg.orderBaseTime + routeDistance / cfg.orderReferenceSpeed * levelMultiplier;
        }

        /// <summary>Stars for an on-time delivery, minus penalties (spills, complaints). Never below 1.</summary>
        public static int Stars(float timeLeft, float timeTotal, int penalty)
        {
            float f = timeTotal > 0f ? timeLeft / timeTotal : 0f;
            int s;
            if (f >= 0.45f) s = 5;
            else if (f >= 0.25f) s = 4;
            else if (f >= 0.1f) s = 3;
            else s = 2;
            s -= penalty;
            return s < 1 ? 1 : s;
        }
    }

    public static class RushRules
    {
        /// <summary>Returns the 1-based rush level reached after the given number of deliveries.</summary>
        public static int LevelForDeliveries(RushLevelConfig[] levels, int deliveries)
        {
            int lvl = 1;
            for (int i = 0; i < levels.Length; i++)
                if (deliveries >= levels[i].deliveriesToReach) lvl = i + 1;
            return lvl;
        }
    }
}
