'use strict';
/* The worker retains compact metadata and bounded token dictionaries, never quote text. */
(function (scope) {
  class LRU {
    constructor(limit) { this.limit = limit; this.values = new Map(); }
    get(key) { if (!this.values.has(key)) return undefined; const value = this.values.get(key); this.values.delete(key); this.values.set(key, value); return value; }
    set(key, value) { this.values.delete(key); this.values.set(key, value); while (this.values.size > this.limit) this.values.delete(this.values.keys().next().value); return value; }
  }
  function tokens(value) { return [...new Set((String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().match(/[a-z0-9]+/g) || []).filter(t => t.length >= 2))]; }
  function intersect(a, b) { const out = []; let i = 0, j = 0; while (i < a.length && j < b.length) { if (a[i] === b[j]) { out.push(a[i]); i++; j++; } else if (a[i] < b[j]) i++; else j++; } return out; }
  function createEngine({ manifest, base, fetch: fetcher = scope.fetch.bind(scope) }) {
    const dictionaries = new LRU(8), pending = new Map(), prefixSet = new Set(manifest.searchPrefixes || []);
    const sectionDefinitions = new Map((manifest.browseGroups || []).flatMap(g => g.sections.map(s => [s.id, { ...s, topic: g.topic }]))), sectionCache = new LRU(8), sectionPending = new Map();
    async function sectionMembers(section) {
      const cached = sectionCache.get(section.id); if (cached) return cached;
      if (!sectionPending.has(section.id)) sectionPending.set(section.id, (async () => {
        const r = await fetcher(asset(section.file)); if (!r.ok) throw Error('This topic section could not be loaded. Please retry.');
        const values = await r.json();
        if (!Array.isArray(values) || values.length !== section.count || values.length > (manifest.sectionLimit || 10000) || values.some((n, i) => !Number.isInteger(n) || n < 0 || n >= manifest.total || i > 0 && n <= values[i - 1])) throw Error('This topic section is incomplete. Please retry.');
        return sectionCache.set(section.id, new Set(values));
      })().finally(() => sectionPending.delete(section.id)));
      return sectionPending.get(section.id);
    }
    let catalogPromise, view, idIndex;
    const asset = path => { const u = new URL(path, base); if (manifest.release) u.searchParams.set('v', manifest.release); return u.href; };
    const canonical = id => { const seen = new Set(); while (Object.prototype.hasOwnProperty.call(manifest.aliases || {}, id) && !seen.has(id)) { seen.add(id); id = manifest.aliases[id]; } return id; };
    async function catalog() {
      if (!catalogPromise) catalogPromise = (async () => { const r = await fetcher(asset(manifest.catalog || 'catalog.bin')); if (!r.ok) throw Error('The library catalog could not be loaded.'); const buffer = await r.arrayBuffer(); if (buffer.byteLength !== manifest.total * 32) throw Error('The library catalog is incomplete. Please retry.'); view = new DataView(buffer); return view; })().catch(e => { catalogPromise = null; throw e; });
      return catalogPromise;
    }
    function idAt(n) {
      if (manifest.legacyIds && manifest.legacyIds[n]) return manifest.legacyIds[n];
      let hex = ''; for (let j = 0; j < 8; j++) hex += view.getUint8(n * 32 + j).toString(16).padStart(2, '0');
      return 'cq-' + hex;
    }
    async function index() { await catalog(); if (!idIndex) { idIndex = new Map(); for (let n = 0; n < manifest.total; n++) idIndex.set(idAt(n), n); } return idIndex; }
    async function resolve(ids) { const map = await index(); return ids.map(id => { const c = canonical(id), n = map.get(c); return n === undefined ? null : { id: c, ordinal: n }; }); }
    async function dictionary(prefix) {
      if (manifest.searchPrefixes && !prefixSet.has(prefix)) return {};
      const cached = dictionaries.get(prefix); if (cached) return cached;
      if (!pending.has(prefix)) pending.set(prefix, (async () => { const r = await fetcher(asset('search/' + prefix + '.json')); if (!r.ok) throw Error('Search could not be loaded. Please retry.'); return dictionaries.set(prefix, await r.json()); })().finally(() => pending.delete(prefix)));
      return pending.get(prefix);
    }
    async function candidates(terms) {
      let result = null;
      for (const term of terms) { const dict = await dictionary(term.slice(0, 2)), union = new Set(); for (const key of Object.keys(dict)) if (key.startsWith(term)) for (const n of dict[key]) if (Number.isInteger(n) && n >= 0 && n < manifest.total) union.add(n); const list = [...union].sort((a, b) => a - b); result = result === null ? list : intersect(result, list); if (!result.length) break; }
      return result;
    }
    async function query(options = {}) {
      await catalog();
      const terms = tokens(options.search), pageSize = Math.min(100, Math.max(1, Number(options.pageSize) || 10));
      if (String(options.search || '').trim() && !terms.length) return { total: 0, page: 1, refs: [], message: 'Enter at least two letters or numbers to search.' };
      const topic = options.topic || 'All topics', topicIndex = (manifest.topics || []).findIndex(t => (typeof t === 'string' ? t : t.name) === topic), topicActive = topic !== 'All topics';
      const sectionId = options.section || '', section = sectionDefinitions.get(sectionId), sectionActive = !!sectionId;
      const onlyCustom = sectionId === 'custom:' + topic, onlyLibrary = sectionId === 'library:' + topic;
      if (sectionActive && (topicIndex < 0 || topicIndex >= 64 || (!onlyCustom && !onlyLibrary && (!section || section.topic !== topic)) || onlyLibrary && (manifest.topics[topicIndex].count || 0) > (manifest.sectionLimit || 10000))) return { total: 0, page: 1, refs: [] };
      const membership = section && section.topic === topic ? await sectionMembers(section) : null;
      const maxAge = options.age === 'all' || options.age == null ? Infinity : Number(options.age), collection = options.collection || 'all';
      const favorites = new Set((options.favorites || []).map(canonical)), ratings = new Map(), rows = [];
      if (Object.keys(options.ratings || {}).length) { const map = await index(); for (const [id, rating] of Object.entries(options.ratings)) if (Number.isInteger(rating) && rating >= 1 && rating <= 5) { const c = canonical(id); ratings.set(c, rating); const n = map.get(c); if (n !== undefined) ratings.set(n, rating); } }
      let favoriteOrdinals;
      if (collection === 'favorites') { const map = await index(); favoriteOrdinals = new Set([...favorites].map(id => map.get(id)).filter(n => n !== undefined)); }
      const custom = new Map(); for (const record of options.custom || []) if (record && typeof record.id === 'string') custom.set(canonical(record.id), record);
      for (const [id, record] of custom) {
        if (sectionActive && !onlyCustom) continue;
        if (collection === 'goodreads' && record.popularity?.source !== 'Goodreads') continue;
        if (topicActive && !(record.topics || []).includes(topic) || Number(record.minAge || 0) > maxAge || collection === 'favorites' && !favorites.has(id)) continue;
        const haystack = tokens([record.text, record.author, ...(record.topics || []), record.source, record.year ?? '', record.chronology?.label || '', record.chronology?.startYear ?? '', record.chronology?.endYear ?? ''].join(' '));
        if (!terms.every(term => haystack.some(word => word.startsWith(term)))) continue;
        rows.push({ record, id, order: rows.length, importance: ratings.get(id) ?? record.importance ?? 0, length: record.text.length, year: [1,2].includes(record.chronology?.version)&&record.chronology.kind!=='unknown'&&Number.isInteger(record.chronology.startYear)?record.chronology.startYear:record.year===0?32767:record.year ?? 32767, likes: record.likes ?? -1 });
      }
      if (!onlyCustom && collection !== 'mine' && (!topicActive || topicIndex >= 0 && topicIndex < 64)) {
        const found = terms.length ? await candidates(terms) : null;
        const visit = n => { const p = n * 32;
          if (membership && !membership.has(n)) return;
          if (view.getUint8(p + 24) > maxAge || favoriteOrdinals && !favoriteOrdinals.has(n)) return;
          if (topicActive && !(view.getUint32(p + (topicIndex < 32 ? 8 : 12), true) & (1 << (topicIndex % 32)))) return;
          if (custom.size && custom.has(idAt(n))) return;
          const indexedLikes = manifest.hasLikeCounts === true ? view.getUint32(p + 28, true) : 0xffffffff;
          if (collection === 'goodreads' && indexedLikes === 0xffffffff) return;
          rows.push({ ordinal: n, order: custom.size + n, importance: ratings.get(n) ?? view.getUint8(p + 25), author: view.getUint32(p + 16, true), length: view.getUint16(p + 20, true), year: view.getInt16(p + 22, true), likes: indexedLikes === 0xffffffff ? -1 : indexedLikes });
        };
        if (found) found.forEach(visit); else for (let n = 0; n < manifest.total; n++) visit(n);
      }
      const sort = options.sort || 'curated', authorNames = manifest.authorNames || (Array.isArray(manifest.authors) ? manifest.authors : null);
      const authorOf = row => row.record ? row.record.author : authorNames && authorNames[row.author] || '';
      rows.sort((a, b) => { let d = 0;
        if (sort === 'importance') d = b.importance - a.importance;
        else if (sort === 'author') d = authorNames ? authorOf(a).localeCompare(authorOf(b)) : a.record && b.record ? a.record.author.localeCompare(b.record.author) : a.record ? -1 : b.record ? 1 : a.author - b.author;
        else if (sort === 'short') d = a.length - b.length;
        else if (sort === 'oldest') d = a.year - b.year;
        else if (sort === 'likes') d = b.likes - a.likes;
        return d || a.order - b.order;
      });
      const total = rows.length, page = Math.min(Math.max(1, Math.floor(Number(options.page) || 1)), Math.max(1, Math.ceil(total / pageSize)));
      return { total, page, refs: rows.slice((page - 1) * pageSize, page * pageSize).map(row => row.record ? { record: row.record } : { ordinal: row.ordinal, id: idAt(row.ordinal) }) };
    }
    return { query, resolve, canonical, catalog, dictionary, dictionaries, sectionCache };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { createEngine, tokens, LRU };
  else {
    let engine;
    scope.onmessage = async event => { const { id, type, payload } = event.data || {}; try { let result; if (type === 'init') { engine = createEngine(payload); result = true; } else { if (!engine) throw Error('Library is not initialized.'); if (type === 'query') result = await engine.query(payload); else if (type === 'resolve') result = await engine.resolve(payload); else throw Error('Unknown library request.'); } scope.postMessage({ id, result }); } catch (error) { scope.postMessage({ id, error: error.message || String(error) }); } };
  }
})(typeof self === 'undefined' ? globalThis : self);
