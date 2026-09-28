using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Arcade scooter: accelerates on its own, the thumb only picks a direction.
    /// Leans into turns, wobbles on bumps, slides in puddles, recovers quickly.
    /// </summary>
    public class PlayerBikeController : MonoBehaviour
    {
        GameManager gm;
        GameConfig cfg;
        CityMap city;

        public Vector2 Pos;
        public Vector2 Velocity;
        public float Heading;
        public float Speed;
        public bool Active;
        public int Helmets;
        public float Invulnerable;

        float air, airTotal;
        float bounce;
        float slide;
        float frozen;
        float wobble, wobbleVel;
        float lean;
        float wallCooldown;
        float visibleTimer;
        Transform leanPivot;
        Renderer[] renderers;
        GameObject model;

        public Vector2 Forward { get { return Geo.Dir(Heading); } }
        public bool Airborne { get { return air > 0f; } }
        public bool Sliding { get { return slide > 0f; } }
        public bool Frozen { get { return frozen > 0f; } }
        public float Speed01 { get { return Mathf.Clamp01(Speed / cfg.maxSpeed); } }

        public void Init(GameManager game)
        {
            gm = game;
            cfg = game.config;
            city = game.city;
            Renderer[] blink;
            GameObject box;
            model = VehicleFactory.BuildPlayer(transform, out leanPivot, out blink, out box);
            renderers = model.GetComponentsInChildren<Renderer>();
        }

        public void ResetAt(Vector2 pos, float heading)
        {
            Pos = pos;
            Heading = heading;
            Speed = 0f;
            Velocity = Vector2.zero;
            Helmets = cfg.helmets;
            Invulnerable = 0f;
            air = bounce = slide = frozen = wobble = wobbleVel = lean = 0f;
            Active = true;
            SetVisible(true);
            UpdateVisual(0f, 0f);
        }

        public void SetVisible(bool v)
        {
            for (int i = 0; i < renderers.Length; i++)
                if (renderers[i].name != "BlinkL" && renderers[i].name != "BlinkR") renderers[i].enabled = v;
        }

        public void Tick(float dt, PlayerInput input, bool raining, bool inFlood)
        {
            if (!Active || dt <= 0f) return;
            if (wallCooldown > 0f) wallCooldown -= dt;
            if (Invulnerable > 0f)
            {
                Invulnerable -= dt;
                visibleTimer += dt;
                SetVisible(Invulnerable <= 0f || Mathf.Repeat(visibleTimer, 0.16f) < 0.1f);
            }

            float prevHeading = Heading;
            if (frozen > 0f)
            {
                frozen -= dt;
                Speed = 0f;
                Velocity = Vector2.zero;
                UpdateVisual(dt, 0f);
                return;
            }

            Surface surf = city.SurfaceAt(Pos);
            float factor = surf == Surface.Sidewalk ? cfg.sidewalkSpeedFactor : (surf == Surface.Gang ? cfg.gangSpeedFactor : 1f);
            if (inFlood) factor *= cfg.floodSpeedFactor;
            float target = cfg.maxSpeed * factor;
            if (input.Hold) target *= cfg.holdSpeedFactor;

            if (air > 0f)
            {
                air -= dt;
                if (air <= 0f)
                {
                    air = 0f;
                    wobbleVel += 90f;
                    gm.OnLanded(Pos);
                }
            }
            else if (input.Direction.sqrMagnitude > 0.01f)
            {
                float desired = Geo.Heading(input.Direction);
                float diff = Mathf.DeltaAngle(Heading, desired);
                float rate = Mathf.Lerp(cfg.turnRateLow, cfg.turnRateHigh, Speed01);
                if (slide > 0f) rate *= 0.6f;
                Heading += Mathf.Clamp(diff, -rate * dt, rate * dt);
                if (Mathf.Abs(diff) > cfg.sharpTurnAngle) target *= 0.55f;
            }
            Heading = Mathf.Repeat(Heading, 360f);

            float accel = target > Speed ? cfg.acceleration : cfg.brakeDeceleration;
            Speed = Mathf.MoveTowards(Speed, target, accel * dt);

            float grip = cfg.grip * (raining ? cfg.rainGripFactor : 1f);
            if (slide > 0f)
            {
                slide -= dt;
                grip = cfg.puddleGrip;
            }
            if (air > 0f) grip = 0.5f;
            Velocity = Vector2.Lerp(Velocity, Forward * Speed, Geo.ExpLerp(grip, dt));

            Move(dt);

            float angVel = Mathf.DeltaAngle(prevHeading, Heading) / dt;
            UpdateVisual(dt, angVel);
        }

        void Move(float dt)
        {
            float r = cfg.playerRadius;
            Vector2 next = Pos + Velocity * dt;
            if (city.IsDrivable(next, r) || !city.IsDrivable(Pos, r))
            {
                Pos = next;
                return;
            }
            Vector2 nx = new Vector2(next.x, Pos.y);
            Vector2 nz = new Vector2(Pos.x, next.y);
            float into;
            if (Mathf.Abs(Velocity.x) >= Mathf.Abs(Velocity.y) && city.IsDrivable(nx, r))
            {
                into = Mathf.Abs(Velocity.y);
                Pos = nx;
                Velocity.y = 0f;
            }
            else if (city.IsDrivable(nz, r))
            {
                into = Mathf.Abs(Velocity.x);
                Pos = nz;
                Velocity.x = 0f;
            }
            else if (city.IsDrivable(nx, r))
            {
                into = Mathf.Abs(Velocity.y);
                Pos = nx;
                Velocity.y = 0f;
            }
            else
            {
                into = Velocity.magnitude;
                Velocity = Vector2.zero;
            }
            // Scraping along a wall bleeds speed; slamming into one is a bump.
            Speed = Mathf.Max(0f, Speed - Speed * 3f * dt);
            if (into > 6f && wallCooldown <= 0f)
            {
                wallCooldown = 0.6f;
                Speed *= 0.5f;
                wobbleVel += 160f;
                gm.OnWallBump(Pos, into);
            }
        }

        void UpdateVisual(float dt, float angVel)
        {
            float leanTarget = Mathf.Clamp(-angVel * Speed * 0.011f, -38f, 38f);
            if (Airborne) leanTarget *= 0.3f;
            lean = Mathf.Lerp(lean, leanTarget, Geo.ExpLerp(10f, dt));
            wobbleVel += (-wobble * 160f - wobbleVel * 9f) * dt;
            wobble += wobbleVel * dt;
            wobble = Mathf.Clamp(wobble, -25f, 25f);

            float y = city.SurfaceHeight(Pos);
            float pitch = 0f;
            if (air > 0f && airTotal > 0f)
            {
                float t = 1f - air / airTotal;
                y += 4f * 0.7f * airTotal * t * (1f - t);
                pitch = Mathf.Lerp(-12f, 10f, t);
            }
            if (bounce > 0f)
            {
                bounce -= dt;
                y += Mathf.Sin(bounce / 0.2f * Mathf.PI) * 0.15f;
            }
            transform.position = Geo.X0Z(Pos, y);
            // Show the drift: the body points between heading and actual travel direction when sliding.
            float yaw = Heading;
            if (Velocity.sqrMagnitude > 1f && slide > 0f) yaw = Heading + Mathf.DeltaAngle(Geo.Heading(Velocity), Heading) * 0.4f;
            transform.rotation = Quaternion.Euler(0f, yaw, 0f);
            leanPivot.localRotation = Quaternion.Euler(pitch, 0f, lean + wobble);
        }

        // ------------------------------------------------------------------ hazard reactions

        public bool StartSlide()
        {
            bool fresh = slide <= 0f;
            slide = cfg.puddleSlideTime;
            if (fresh) wobbleVel += 60f;
            return fresh;
        }

        public void HitPothole()
        {
            Speed *= 0.72f;
            wobbleVel += (Random.value < 0.5f ? -1f : 1f) * 220f;
            bounce = 0.2f;
        }

        public void HitSpeedBump()
        {
            if (Speed > 6f)
            {
                airTotal = air = cfg.bumpJumpTime * (0.5f + 0.5f * Speed01);
                gm.OnSpeedBumpJump(Pos);
            }
            else
            {
                bounce = 0.2f;
                Speed *= 0.9f;
            }
        }

        public void HardStop(Vector2 pushDir)
        {
            Speed = 0f;
            Velocity = pushDir * 2f;
            wobbleVel += 200f;
        }

        public void Freeze(float t)
        {
            frozen = t;
            Speed = 0f;
            Velocity = Vector2.zero;
        }

        /// <summary>Contact response after the position was already pushed out of the obstacle.</summary>
        public void ApplyHit(Vector2 normal, Vector2 otherVel, bool heavy)
        {
            if (heavy)
            {
                Speed *= 0.15f;
                Velocity = normal * 6f + otherVel * 0.5f;
                wobbleVel += 420f * (Random.value < 0.5f ? -1f : 1f);
                Invulnerable = cfg.invulnerableTime;
                visibleTimer = 0f;
            }
            else
            {
                float into = Vector2.Dot(Velocity - otherVel, normal);
                if (into < 0f) Velocity -= normal * into * 1.4f;
                Velocity += otherVel * 0.3f;
                Speed *= 0.65f;
                wobbleVel += 150f * (Random.value < 0.5f ? -1f : 1f);
            }
        }

        public void Park()
        {
            Active = false;
            Invulnerable = 0f;
            SetVisible(true);
            Speed = 0f;
            Velocity = Vector2.zero;
        }
    }
}
