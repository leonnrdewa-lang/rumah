using System;
using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    /// <summary>Generic GameObject pool: inactive instances are reused instead of instantiated.</summary>
    public class Pool<T> where T : Component
    {
        readonly Func<T> factory;
        readonly Stack<T> free = new Stack<T>();

        public Pool(Func<T> factory) { this.factory = factory; }

        public T Get()
        {
            T item = free.Count > 0 ? free.Pop() : factory();
            item.gameObject.SetActive(true);
            return item;
        }

        public void Release(T item)
        {
            item.gameObject.SetActive(false);
            free.Push(item);
        }

        public int FreeCount { get { return free.Count; } }
    }

    /// <summary>Keyed pools so managers can share one registry (e.g. one pool per vehicle type).</summary>
    public class PoolManager
    {
        readonly Dictionary<string, object> pools = new Dictionary<string, object>();

        public Pool<T> For<T>(string key, Func<T> factory) where T : Component
        {
            object p;
            if (!pools.TryGetValue(key, out p))
            {
                p = new Pool<T>(factory);
                pools[key] = p;
            }
            return (Pool<T>)p;
        }
    }
}
