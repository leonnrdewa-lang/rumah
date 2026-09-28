using NUnit.Framework;
using UnityEngine;

namespace OjolRush.Tests
{
    public class OjolRushLogicTests
    {
        static GameConfig Cfg()
        {
#if UNITY_5_3_OR_NEWER
            GameConfig c = ScriptableObject.CreateInstance<GameConfig>();
#else
            // Outside the editor a ScriptableObject cannot be constructed; field values are set below.
            GameConfig c = (GameConfig)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(GameConfig));
#endif
            c.nearMissPoints = 50;
            c.deliveryBase = 500;
            c.speedBonusPerSecond = 15;
            c.tipsByStars = new[] { 0, 0, 0, 50, 120, 300 };
            c.orderBaseTime = 12f;
            c.orderReferenceSpeed = 8.5f;
            c.rushLevels = RushLevelConfig.Defaults();
            return c;
        }

        // ---------------------------------------------------------------- combo

        [Test]
        public void Combo_ChainsWithinWindow()
        {
            ComboSystem combo = new ComboSystem(2f, 10);
            Assert.AreEqual(1, combo.RegisterNearMiss());
            combo.Tick(1.5f);
            Assert.AreEqual(2, combo.RegisterNearMiss());
            combo.Tick(1.9f);
            Assert.AreEqual(3, combo.RegisterNearMiss());
            Assert.AreEqual(3, combo.Best);
        }

        [Test]
        public void Combo_ExpiresAfterWindow()
        {
            ComboSystem combo = new ComboSystem(2f, 10);
            combo.RegisterNearMiss();
            combo.RegisterNearMiss();
            combo.Tick(2.01f);
            Assert.AreEqual(0, combo.Count);
            Assert.AreEqual(1, combo.RegisterNearMiss());
        }

        [Test]
        public void Combo_BreakResetsChainButKeepsBest()
        {
            ComboSystem combo = new ComboSystem(2f, 10);
            for (int i = 0; i < 4; i++) combo.RegisterNearMiss();
            combo.Break();
            Assert.AreEqual(0, combo.Count);
            Assert.AreEqual(1, combo.Multiplier);
            Assert.AreEqual(4, combo.Best);
        }

        [Test]
        public void Combo_MultiplierIsCapped()
        {
            ComboSystem combo = new ComboSystem(2f, 5);
            int m = 0;
            for (int i = 0; i < 9; i++) m = combo.RegisterNearMiss();
            Assert.AreEqual(5, m);
            Assert.AreEqual(9, combo.Count);
        }

        // ---------------------------------------------------------------- score

        [Test]
        public void Score_NearMissUsesMultiplier()
        {
            ScoreManager s = new ScoreManager(Cfg());
            Assert.AreEqual(50, s.AddNearMiss(1));
            Assert.AreEqual(250, s.AddNearMiss(5));
            Assert.AreEqual(300, s.Score);
            Assert.AreEqual(2, s.NearMisses);
        }

        [Test]
        public void Score_DeliveryScalesWithStarsAndTime()
        {
            ScoreManager s = new ScoreManager(Cfg());
            Assert.AreEqual(500, s.DeliveryPoints(0f, 3));
            Assert.AreEqual(Mathf.RoundToInt((500 + 20 * 15) * 5f / 3f), s.DeliveryPoints(20f, 5));
            Assert.Less(s.DeliveryPoints(10f, 1), s.DeliveryPoints(10f, 2));
        }

        [Test]
        public void Score_TipsAndDeliveriesAccumulate()
        {
            ScoreManager s = new ScoreManager(Cfg());
            Assert.AreEqual(300, s.Tip(5));
            Assert.AreEqual(0, s.Tip(2));
            Assert.AreEqual(300, s.Tip(99));
            s.AddDelivery(800, 300);
            Assert.AreEqual(1100, s.Score);
            Assert.AreEqual(1, s.Deliveries);
            Assert.AreEqual(300, s.TotalTips);
            s.Reset();
            Assert.AreEqual(0, s.Score);
        }

        // ---------------------------------------------------------------- rating & orders

        [Test]
        public void Rating_StartsPerfectAndAveragesRecentOrders()
        {
            RatingTracker r = new RatingTracker(10, 3);
            Assert.AreEqual(5f, r.Average, 1e-4);
            r.Record(1);
            Assert.AreEqual(4f, r.Average, 1e-4);
            r.Record(1);
            r.Record(1);
            r.Record(1);
            Assert.Less(r.Average, 3f);
        }

        [Test]
        public void Rating_KeepsOnlyHistoryWindow()
        {
            RatingTracker r = new RatingTracker(3, 3);
            r.Record(2); r.Record(2); r.Record(2);
            Assert.AreEqual(2f, r.Average, 1e-4);
            r.Record(9);
            Assert.AreEqual(3f, r.Average, 1e-4); // clamped to 5: (2+2+5)/3
        }

        [Test]
        public void Stars_DependOnTimeLeftAndPenalties()
        {
            Assert.AreEqual(5, OrderRules.Stars(50f, 100f, 0));
            Assert.AreEqual(4, OrderRules.Stars(30f, 100f, 0));
            Assert.AreEqual(3, OrderRules.Stars(12f, 100f, 0));
            Assert.AreEqual(2, OrderRules.Stars(1f, 100f, 0));
            Assert.AreEqual(3, OrderRules.Stars(50f, 100f, 2));
            Assert.AreEqual(1, OrderRules.Stars(1f, 100f, 5));
        }

        [Test]
        public void OrderTime_GrowsWithDistanceAndLevelMultiplier()
        {
            GameConfig c = Cfg();
            float near = OrderRules.TimeLimit(c, 100f, 1f);
            float far = OrderRules.TimeLimit(c, 300f, 1f);
            float easy = OrderRules.TimeLimit(c, 300f, 1.5f);
            Assert.Greater(far, near);
            Assert.Greater(easy, far);
            Assert.AreEqual(12f + 100f / 8.5f, near, 1e-3);
            Assert.AreEqual(30f, OrderRules.Manhattan(0, 0, 10, -20), 1e-4);
        }

        // ---------------------------------------------------------------- rush levels

        [Test]
        public void Rush_LevelsFollowDeliveries()
        {
            RushLevelConfig[] l = RushLevelConfig.Defaults();
            Assert.AreEqual(5, l.Length);
            Assert.AreEqual(1, RushRules.LevelForDeliveries(l, 0));
            Assert.AreEqual(2, RushRules.LevelForDeliveries(l, l[1].deliveriesToReach));
            Assert.AreEqual(5, RushRules.LevelForDeliveries(l, 999));
        }

        [Test]
        public void Rush_LevelsEscalate()
        {
            RushLevelConfig[] l = RushLevelConfig.Defaults();
            for (int i = 1; i < l.Length; i++)
            {
                Assert.Greater(l[i].deliveriesToReach, l[i - 1].deliveriesToReach);
                Assert.GreaterOrEqual(l[i].trafficCount, l[i - 1].trafficCount);
                Assert.LessOrEqual(l[i].timerMultiplier, l[i - 1].timerMultiplier);
            }
            Assert.IsTrue(l[4].alwaysRain);
            Assert.Greater(l[3].floodZones, 0);
            Assert.AreEqual(0f, l[0].rainChance);
        }

        // ---------------------------------------------------------------- city map

        [Test]
        public void City_SurfacesAlongAStreet()
        {
            CityMap m = new CityMap();
            float y = CityMap.Pitch; // a horizontal street
            Assert.AreEqual(Surface.Road, m.SurfaceAt(new Vector2(30f, y)));
            Assert.AreEqual(Surface.Road, m.SurfaceAt(new Vector2(30f, y + 6.9f)));
            Assert.AreEqual(Surface.Sidewalk, m.SurfaceAt(new Vector2(30f, y + 8.5f)));
            Assert.AreEqual(Surface.Blocked, m.SurfaceAt(new Vector2(30f, y + 20f)));
            Assert.AreEqual(Surface.Blocked, m.SurfaceAt(new Vector2(-50f, 0f)));
        }

        [Test]
        public void City_GangsAreDrivableShortcutsThroughBlocks()
        {
            CityMap m = new CityMap();
            Assert.AreEqual(2, m.gangs.Count);
            foreach (Rect g in m.gangs)
            {
                Vector2 c = g.center;
                Surface s = m.SurfaceAt(c);
                Assert.IsTrue(s == Surface.Gang || s == Surface.Road || s == Surface.Sidewalk);
                // Somewhere along the gang there is interior (block) land that is only drivable because of the gang.
                bool vertical = g.height > g.width;
                Vector2 probe = vertical ? new Vector2(g.center.x, g.yMin + 30f) : new Vector2(g.xMin + 30f, g.center.y);
                Assert.AreEqual(Surface.Gang, m.SurfaceAt(probe));
                Vector2 beside = probe + (vertical ? new Vector2(3f, 0f) : new Vector2(0f, 3f));
                Assert.AreEqual(Surface.Blocked, m.SurfaceAt(beside));
            }
        }

        [Test]
        public void City_TrafficDrivesOnTheLeft()
        {
            // Eastbound lanes sit north of the centreline, northbound lanes west of it (left-hand traffic).
            Vector2 east = CityMap.LaneOffset(0, 0);
            Vector2 north = CityMap.LaneOffset(1, 1);
            Assert.Greater(east.y, 0f);
            Assert.Less(north.x, 0f);
            Assert.AreEqual(1.75f, CityMap.LaneOffset(2, 0).magnitude, 1e-4);
            Assert.AreEqual(5.25f, CityMap.LaneOffset(3, 1).magnitude, 1e-4);
        }

        [Test]
        public void City_EdgesStayInsideTheGrid()
        {
            CityMap m = new CityMap(5, 7);
            Assert.IsTrue(m.HasEdge(0, 0, 0));
            Assert.IsTrue(m.HasEdge(0, 0, 1));
            Assert.IsFalse(m.HasEdge(0, 0, 2));
            Assert.IsFalse(m.HasEdge(4, 6, 1));
            Vector2 a, b;
            m.EdgeLane(1, 1, 0, 0, out a, out b);
            Assert.AreEqual(CityMap.EdgeLength, Vector2.Distance(a, b), 1e-3);
            Assert.AreEqual(Surface.Road, m.SurfaceAt(a));
            Assert.AreEqual(Surface.Road, m.SurfaceAt(b));
        }

        [Test]
        public void City_TurnHelpers()
        {
            Assert.AreEqual(1, CityMap.LeftOf(0));   // east -> north
            Assert.AreEqual(3, CityMap.RightOf(0));  // east -> south
            Assert.AreEqual(2, CityMap.Opposite(0));
            Assert.AreEqual(0, CityMap.LeftOf(3));   // south -> east
        }

        [Test]
        public void City_SpotsAreOnSidewalks()
        {
            CityMap m = new CityMap();
            m.BuildSpots(new System.Random(1));
            Assert.Greater(m.spots.Count, 40);
            int restaurants = 0;
            foreach (Spot s in m.spots)
            {
                Assert.AreEqual(Surface.Sidewalk, m.SurfaceAt(s.pos), s.name);
                if (s.restaurant) restaurants++;
            }
            Assert.Greater(restaurants, 5);
        }

        [Test]
        public void City_StreetOffsetSign()
        {
            CityMap m = new CityMap();
            bool horizontal;
            float off = m.StreetOffset(new Vector2(30f, CityMap.Pitch + 3f), out horizontal);
            Assert.IsTrue(horizontal);
            Assert.AreEqual(3f, off, 1e-4);
            off = m.StreetOffset(new Vector2(CityMap.Pitch - 2f, 30f), out horizontal);
            Assert.IsFalse(horizontal);
            Assert.AreEqual(2f, off, 1e-4); // west of a northbound street is "left"
        }

        // ---------------------------------------------------------------- geometry & lights

        [Test]
        public void Geo_HeadingRoundTrip()
        {
            Assert.AreEqual(0f, Geo.Heading(new Vector2(0, 1)), 1e-4);
            Assert.AreEqual(90f, Geo.Heading(new Vector2(1, 0)), 1e-4);
            Vector2 d = Geo.Dir(90f);
            Assert.AreEqual(1f, d.x, 1e-4);
            Assert.AreEqual(0f, d.y, 1e-4);
            Assert.AreEqual(-1f, Geo.Left(new Vector2(0, 1)).x, 1e-4);
        }

        [Test]
        public void Geo_ClosestOnObb()
        {
            Vector2 closest;
            bool inside = Geo.ClosestOnObb(Vector2.zero, new Vector2(0, 1), 2f, 1f, new Vector2(3f, 0f), out closest);
            Assert.IsFalse(inside);
            Assert.AreEqual(1f, closest.x, 1e-4);
            inside = Geo.ClosestOnObb(Vector2.zero, new Vector2(0, 1), 2f, 1f, new Vector2(0.8f, 0.2f), out closest);
            Assert.IsTrue(inside);
            Assert.AreEqual(1f, closest.x, 1e-4); // pushed out through the nearest (side) face
            Assert.AreEqual(0.2f, closest.y, 1e-4);
        }

        [Test]
        public void Geo_BezierEndpoints()
        {
            Vector2 a = new Vector2(0, 0), c = new Vector2(10, 0), b = new Vector2(10, 10);
            Assert.AreEqual(a, Geo.Bezier(a, c, b, 0f));
            Assert.AreEqual(b, Geo.Bezier(a, c, b, 1f));
            float len = Geo.BezierLength(a, c, b);
            Assert.Greater(len, Vector2.Distance(a, b));
            Assert.Less(len, 20f);
        }

        [Test]
        public void Lights_NeverGreenBothWays()
        {
            TrafficLights lights = new TrafficLights(5, 7, new System.Random(3));
            for (float t = 0f; t < 60f; t += 0.25f)
            {
                for (int i = 0; i < 5; i++)
                    for (int j = 0; j < 7; j++)
                    {
                        LightState h = lights.State(i, j, true, t);
                        LightState v = lights.State(i, j, false, t);
                        Assert.IsFalse(h != LightState.Red && v != LightState.Red, "conflict at " + i + "," + j + " t=" + t);
                    }
            }
        }
    }
}
