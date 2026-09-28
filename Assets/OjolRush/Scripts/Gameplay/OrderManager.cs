using UnityEngine;

namespace OjolRush
{
    public enum OrderType { Food, Package }
    public enum OrderStage { None, Pickup, Dropoff }

    public class Order
    {
        public OrderType type;
        public Spot pickup;
        public Spot dropoff;
        public string item;
        public float timeTotal;
        public float timeLeft;
        public OrderStage stage;
        public int penalty;
        public int spills;
    }

    /// <summary>
    /// NgoJek-in order flow: notification -> pickup marker -> drop-off marker -> rating + tip.
    /// </summary>
    public class OrderManager : MonoBehaviour
    {
        GameManager gm;
        GameConfig cfg;
        CityMap city;
        System.Random rng;

        public Order Current { get; private set; }
        public float NextOrderIn { get; private set; }

        GameObject pickupMarker, dropoffMarker;
        Transform pickupIcon, dropoffIcon;
        float time;

        static readonly string[] FoodItems = { "Nasi Goreng", "Bakso Urat", "Martabak Manis", "Es Kopi Susu x3", "Sate Ayam 20 tusuk", "Mie Ayam Pangsit", "Seblak Level 5", "Soto Betawi", "Pecel Lele", "Gorengan 10 biji" };
        static readonly string[] PackageItems = { "Paket Olshop", "Dokumen Kantor", "Kunci Rumah Ketinggalan", "Charger HP", "Sparepart Motor", "Obat dari Apotek", "Sepatu COD" };

        public void Init(GameManager game, CityMap map, System.Random random)
        {
            gm = game;
            cfg = game.config;
            city = map;
            rng = random;
            pickupMarker = BuildMarker("PickupMarker", new Color(1f, 0.55f, 0.1f), out pickupIcon, true);
            dropoffMarker = BuildMarker("DropoffMarker", Palette.OjolGreen, out dropoffIcon, false);
            pickupMarker.SetActive(false);
            dropoffMarker.SetActive(false);
        }

        GameObject BuildMarker(string name, Color c, out Transform icon, bool bowl)
        {
            GameObject root = new GameObject(name);
            root.transform.SetParent(transform, false);
            MeshBatcher mb = new MeshBatcher();
            int n = 20;
            float rad = cfg.markerRadius;
            for (int i = 0; i < n; i += 1)
            {
                if (i % 2 == 1) continue;
                float a0 = i * Mathf.PI * 2f / n, a1 = (i + 1) * Mathf.PI * 2f / n;
                mb.Beam(new Vector3(Mathf.Cos(a0) * rad, 0.2f, Mathf.Sin(a0) * rad), new Vector3(Mathf.Cos(a1) * rad, 0.2f, Mathf.Sin(a1) * rad), 0.3f, c, true);
            }
            mb.Box(new Vector3(0, 6f, 0), new Vector3(0.35f, 12f, 0.35f), Quaternion.identity, c, true);
            mb.BuildObject("Beam", root.transform, false);

            GameObject ic = new GameObject("Icon");
            ic.transform.SetParent(root.transform, false);
            MeshBatcher im = new MeshBatcher();
            if (bowl)
            {
                im.Prism(new Vector3(0, 0, 0), Vector3.up, 0.8f, 0.5f, 8, Color.white);
                im.Prism(new Vector3(0, 0.3f, 0), Vector3.up, 0.7f, 0.12f, 8, new Color(0.95f, 0.75f, 0.3f));
                im.Beam(new Vector3(-0.3f, 0.3f, 0), new Vector3(0.1f, 1.2f, 0.1f), 0.07f, new Color(0.6f, 0.4f, 0.2f));
                im.Beam(new Vector3(-0.1f, 0.3f, 0), new Vector3(0.3f, 1.2f, 0.1f), 0.07f, new Color(0.6f, 0.4f, 0.2f));
            }
            else
            {
                im.Box(new Vector3(0, 0.1f, 0), new Vector3(1.2f, 0.9f, 1.0f), Quaternion.identity, new Color(0.95f, 0.95f, 0.9f));
                im.Box(new Vector3(0, 0.95f, 0), new Vector3(1.5f, 0.2f, 1.2f), Quaternion.identity, new Color(0.85f, 0.25f, 0.2f));
                im.Box(new Vector3(0, -0.05f, -0.51f), new Vector3(0.4f, 0.6f, 0.05f), Quaternion.identity, new Color(0.5f, 0.3f, 0.15f));
            }
            im.Attach(ic, false);
            ic.transform.localPosition = new Vector3(0, 3f, 0);
            icon = ic.transform;
            return root;
        }

        public void ResetOrders()
        {
            Current = null;
            NextOrderIn = 0.6f;
            pickupMarker.SetActive(false);
            dropoffMarker.SetActive(false);
        }

        public Vector2? TargetPosition
        {
            get
            {
                if (Current == null) return null;
                return Current.stage == OrderStage.Pickup ? Current.pickup.pos : Current.dropoff.pos;
            }
        }

        public string TargetName
        {
            get
            {
                if (Current == null) return "";
                return Current.stage == OrderStage.Pickup ? Current.pickup.name : Current.dropoff.name;
            }
        }

        public bool CarryingFood { get { return Current != null && Current.stage == OrderStage.Dropoff && Current.type == OrderType.Food; } }
        public bool Carrying { get { return Current != null && Current.stage == OrderStage.Dropoff; } }

        Spot PickSpot(Vector2 from, float minD, float maxD, bool restaurant)
        {
            Spot best = null;
            for (int tries = 0; tries < 60; tries++)
            {
                Spot s = city.spots[rng.Next(city.spots.Count)];
                if (restaurant && !s.restaurant && tries < 40) continue;
                if (!restaurant && s.restaurant && tries < 40) continue;
                float d = Vector2.Distance(s.pos, from);
                if (d >= minD && d <= maxD) return s;
                if (best == null) best = s;
            }
            return best;
        }

        void NewOrder()
        {
            Vector2 p = gm.player.Pos;
            Order o = new Order();
            o.type = rng.NextDouble() < cfg.foodOrderChance ? OrderType.Food : OrderType.Package;
            o.pickup = PickSpot(p, cfg.pickupMinDistance, cfg.pickupMaxDistance, o.type == OrderType.Food);
            o.dropoff = PickSpot(o.pickup.pos, cfg.dropoffMinDistance, cfg.dropoffMaxDistance, false);
            if (o.dropoff == o.pickup) o.dropoff = PickSpot(o.pickup.pos, 40f, 400f, false);
            o.item = o.type == OrderType.Food ? FoodItems[rng.Next(FoodItems.Length)] : PackageItems[rng.Next(PackageItems.Length)];
            float route = OrderRules.Manhattan(p.x, p.y, o.pickup.pos.x, o.pickup.pos.y) + OrderRules.Manhattan(o.pickup.pos.x, o.pickup.pos.y, o.dropoff.pos.x, o.dropoff.pos.y);
            o.timeTotal = OrderRules.TimeLimit(cfg, route, gm.rush.Level.timerMultiplier);
            o.timeLeft = o.timeTotal;
            o.stage = OrderStage.Pickup;
            Current = o;
            PlaceMarker(pickupMarker, o.pickup.pos);
            dropoffMarker.SetActive(false);
            gm.audioManager.Play("ping", 0.9f, 1f);
            gm.hud.Notify("ORDER MASUK!", (o.type == OrderType.Food ? "Makanan: " : "Paket: ") + o.item + "\nAmbil di " + o.pickup.name);
        }

        void PlaceMarker(GameObject m, Vector2 p)
        {
            m.SetActive(true);
            m.transform.position = Geo.X0Z(p, CityMap.SidewalkHeight);
        }

        public void Tick(float dt)
        {
            if (dt <= 0f) return;
            time += dt;
            pickupIcon.localRotation = Quaternion.Euler(0, time * 90f, 0);
            dropoffIcon.localRotation = Quaternion.Euler(0, time * 90f, 0);
            pickupIcon.localPosition = new Vector3(0, 3f + Mathf.Sin(time * 3f) * 0.4f, 0);
            dropoffIcon.localPosition = new Vector3(0, 3f + Mathf.Sin(time * 3f) * 0.4f, 0);

            if (gm.State != GameState.Playing) return;

            if (Current == null)
            {
                NextOrderIn -= dt;
                if (NextOrderIn <= 0f) NewOrder();
                return;
            }

            Current.timeLeft -= dt;
            if (Current.timeLeft <= 0f)
            {
                Current.timeLeft = 0f;
                FailOrder();
                return;
            }

            Vector2 target = Current.stage == OrderStage.Pickup ? Current.pickup.pos : Current.dropoff.pos;
            if (Vector2.Distance(gm.player.Pos, target) < cfg.markerRadius)
            {
                if (Current.stage == OrderStage.Pickup)
                {
                    Current.stage = OrderStage.Dropoff;
                    pickupMarker.SetActive(false);
                    PlaceMarker(dropoffMarker, Current.dropoff.pos);
                    gm.audioManager.Play("pickup", 0.8f, 1f);
                    gm.hud.Popup(Geo.X0Z(target, 2f), "DIAMBIL!", new Color(1f, 0.7f, 0.2f), 1.1f);
                    gm.hud.Notify("ANTAR KE", Current.dropoff.name);
                }
                else
                {
                    CompleteOrder();
                }
            }
        }

        void CompleteOrder()
        {
            Order o = Current;
            int stars = OrderRules.Stars(o.timeLeft, o.timeTotal, o.penalty);
            gm.OnDelivered(o, stars, Geo.X0Z(o.dropoff.pos, 2f));
            dropoffMarker.SetActive(false);
            Current = null;
            NextOrderIn = cfg.nextOrderDelay;
        }

        void FailOrder()
        {
            gm.OnOrderFailed(Current);
            pickupMarker.SetActive(false);
            dropoffMarker.SetActive(false);
            Current = null;
            NextOrderIn = cfg.nextOrderDelay;
        }

        /// <summary>A heavy crash while carrying: food spills (-2 stars), packages get dented (-1).</summary>
        public string OnHeavyCrash()
        {
            if (!Carrying) return null;
            if (Current.type == OrderType.Food)
            {
                Current.spills++;
                Current.penalty += 2;
                return "TUMPAH!";
            }
            Current.penalty += 1;
            return "PAKET PENYOK!";
        }

        public void AddComplaint()
        {
            if (Current != null) Current.penalty += 1;
        }

        public void AddTimePenalty(float seconds)
        {
            if (Current != null) Current.timeLeft = Mathf.Max(0.5f, Current.timeLeft - seconds);
        }
    }
}
