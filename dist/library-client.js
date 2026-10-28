'use strict';
(function (scope) {
  const scriptURL = typeof document !== 'undefined' && document.currentScript && document.currentScript.src || scope.location && scope.location.href || 'http://localhost/library-client.js';
  class LRU {
    constructor(limit) { this.limit = limit; this.values = new Map(); }
    get(key) { if (!this.values.has(key)) return undefined; const value = this.values.get(key); this.values.delete(key); this.values.set(key, value); return value; }
    set(key, value) { this.values.delete(key); this.values.set(key, value); while (this.values.size > this.limit) this.values.delete(this.values.keys().next().value); return value; }
  }
  class CommonplaceLibrary {
    constructor({ base = 'data/' } = {}) {
      this.base = new URL(base, scope.document && scope.document.baseURI || scope.location && scope.location.href || scriptURL).href;
      if (!this.base.endsWith('/')) this.base += '/';
      this.manifest = null; this.initial = new Map(); this.chunks = new LRU(8); this.chunkPending = new Map(); this.pending = new Map(); this.sequence = 0; this.worker = null; this.initPromise = null; this.readyPromise = null;
    }
    async init() {
      if (!this.initPromise) this.initPromise = (async () => { const r = await scope.fetch(new URL('manifest.json', this.base).href, { cache: 'no-cache' }); if (!r.ok) throw Error('The library could not be opened. Please retry.'); const m = await r.json(); if (m.version !== 2 || !Number.isInteger(m.total) || m.total < 0) throw Error('The library manifest is invalid.'); this.manifest = m; for (const q of m.initial || []) this.initial.set(q.id, q); return m; })().catch(e => { this.initPromise = null; throw e; });
      return this.initPromise;
    }
    canonical(id) { const seen = new Set(), aliases = this.manifest && this.manifest.aliases || {}; while (Object.prototype.hasOwnProperty.call(aliases, id) && !seen.has(id)) { seen.add(id); id = aliases[id]; } return id; }
    asset(path) { const u = new URL(path, this.base); if (this.manifest.release) u.searchParams.set('v', this.manifest.release); return u.href; }
    async ready() {
      await this.init();
      if (!this.readyPromise) { let startedWorker; this.readyPromise = (async () => {
        const workerURL = new URL('library-worker.js', scriptURL); if (this.manifest.release) workerURL.searchParams.set('v', this.manifest.release);
        const worker = startedWorker = this.worker = new scope.Worker(workerURL.href, { name: 'commonplace-library' });
        worker.onmessage = event => { const p = this.pending.get(event.data.id); if (!p) return; this.pending.delete(event.data.id); if (event.data.error) p.reject(Error(event.data.error)); else p.resolve(event.data.result); };
        worker.onerror = () => { if (this.worker !== worker) return; const error = Error('Library search stopped. Please retry.'); for (const p of this.pending.values()) p.reject(error); this.pending.clear(); worker.terminate(); if (this.worker === worker) { this.worker = null; this.readyPromise = null; } };
        await this.request('init', { manifest: this.manifest, base: this.base });
      })().catch(e => { if (this.worker === startedWorker) { if (this.worker) this.worker.terminate(); this.worker = null; this.readyPromise = null; } throw e; }); }
      return this.readyPromise;
    }
    request(type, payload) { const id = ++this.sequence; return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); try { this.worker.postMessage({ id, type, payload }); } catch (e) { this.pending.delete(id); reject(e); } }); }
    async chunk(n) {
      const cached = this.chunks.get(n); if (cached) return cached;
      if (!this.chunkPending.has(n)) this.chunkPending.set(n, (async () => { const r = await scope.fetch(this.asset('records/' + String(n).padStart(5, '0') + '.json')); if (!r.ok) throw Error('This page of quotes could not be loaded. Please retry.'); const records = await r.json(); if (!Array.isArray(records)) throw Error('This quote page is invalid.'); return this.chunks.set(n, { records, byId: new Map(records.map(q => [q.id, q])) }); })().finally(() => this.chunkPending.delete(n)));
      return this.chunkPending.get(n);
    }
    getCached(id) { id = this.canonical(id); if (this.initial.has(id)) return this.initial.get(id); for (const [n, entry] of this.chunks.values) if (entry.byId.has(id)) { this.chunks.get(n); return entry.byId.get(id); } return null; }
    async records(refs) {
      const out = Array(refs.length).fill(null), groups = new Map(), size = this.manifest.chunkSize || 200;
      refs.forEach((ref, i) => { if (!ref) return; if (ref.record) { out[i] = ref.record; return; } const cached = this.getCached(ref.id); if (cached) { out[i] = cached; return; } const n = Math.floor(ref.ordinal / size); if (!groups.has(n)) groups.set(n, []); groups.get(n).push([ref, i]); });
      // Sequential chunk loading bounds peak memory even for large backup/PDF resolves.
      for (const [n, entries] of groups) { const chunk = await this.chunk(n); for (const [ref, i] of entries) { const record = chunk.records[ref.ordinal % size]; if (!record || record.id !== ref.id) { this.chunks.values.delete(n); throw Error('The library data does not match its catalog. Please refresh.'); } out[i] = record; } }
      return out;
    }
    async query(options = {}) { await this.ready(); const result = await this.request('query', options), items = await this.records(result.refs); return { total: result.total, page: result.page, items, ...(result.message ? { message: result.message } : {}) }; }
    async resolve(ids) { await this.ready(); return this.records(await this.request('resolve', ids)); }
    async hasIds(ids) { await this.ready(); const refs = await this.request('resolve', ids); return ids.filter((id, i) => !refs[i]); }
    close() { if (this.worker) this.worker.terminate(); for (const p of this.pending.values()) p.reject(Error('Library closed.')); this.pending.clear(); this.worker = null; this.readyPromise = null; }
  }
  scope.CommonplaceLibrary = CommonplaceLibrary;
  if (typeof module !== 'undefined' && module.exports) module.exports = CommonplaceLibrary;
})(typeof window === 'undefined' ? globalThis : window);
