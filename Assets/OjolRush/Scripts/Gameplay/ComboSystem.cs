namespace OjolRush
{
    /// <summary>Near-miss chain: every SALIP within the window extends the chain and raises the multiplier.</summary>
    public class ComboSystem
    {
        readonly float window;
        readonly int maxMultiplier;
        float timer;

        public int Count { get; private set; }
        public int Best { get; private set; }

        public ComboSystem(float window, int maxMultiplier)
        {
            this.window = window;
            this.maxMultiplier = maxMultiplier < 1 ? 1 : maxMultiplier;
        }

        public int Multiplier
        {
            get
            {
                if (Count < 1) return 1;
                return Count > maxMultiplier ? maxMultiplier : Count;
            }
        }

        /// <summary>0..1 of the chain window remaining (for the HUD bar).</summary>
        public float WindowLeft { get { return Count > 0 ? timer / window : 0f; } }

        /// <summary>Registers a near miss and returns the multiplier it earned.</summary>
        public int RegisterNearMiss()
        {
            Count = timer > 0f ? Count + 1 : 1;
            timer = window;
            if (Count > Best) Best = Count;
            return Multiplier;
        }

        public void Tick(float dt)
        {
            if (timer <= 0f) return;
            timer -= dt;
            if (timer <= 0f)
            {
                timer = 0f;
                Count = 0;
            }
        }

        /// <summary>Any bump or crash drops the chain.</summary>
        public void Break()
        {
            Count = 0;
            timer = 0f;
        }

        public void Reset()
        {
            Break();
            Best = 0;
        }
    }
}
