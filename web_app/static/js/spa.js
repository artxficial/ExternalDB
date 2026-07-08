/**
 * spa.js — client-side router for artxficial.dev
 *
 * Works with the markup already in base.html:
 *   - nav links: <a class="spa-link" data-title="...">
 *   - swap target: <div id="page-content">
 *
 * Fixes vs a naive innerHTML swap:
 *   1. innerHTML never executes <script> tags — this manually re-inserts
 *      and runs any scripts found in the fetched page.
 *   2. Re-run scripts are wrapped in an IIFE, so top-level `const`/`let`
 *      declarations (e.g. `const databaseLogger = ...`) don't throw
 *      "already been declared" the second time you visit the page.
 *   3. Exposes a teardown registry (window.__spaTeardown) so pages that
 *      start intervals/pollers can clean up when you navigate away.
 */
(function () {
  const contentEl = document.getElementById('page-content');
  if (!contentEl) return;

  function runTeardown() {
    (window.__spaTeardown || []).forEach(function (fn) {
      try { fn(); } catch (err) { console.error('[SPA] teardown error:', err); }
    });
    window.__spaTeardown = [];
  }

  function extractScripts(container) {
    const scripts = [];
    container.querySelectorAll('script').forEach(function (node) {
      scripts.push({ src: node.getAttribute('src'), code: node.textContent });
      node.remove();
    });
    return scripts;
  }

  function runScripts(scripts) {
    // Remove whatever we injected on the previous swap.
    document.querySelectorAll('script.spa-injected').forEach(function (el) { el.remove(); });

    scripts.forEach(function (script) {
      const s = document.createElement('script');
      s.className = 'spa-injected';
      if (script.src) {
        s.src = script.src;
      } else {
        s.textContent = '(function(){\n' + script.code + '\n})();';
      }
      document.body.appendChild(s);
    });
  }

  async function navigate(url, title, pushState) {
    if (pushState === undefined) pushState = true;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      const html = await res.text();

      const doc = new DOMParser().parseFromString(html, 'text/html');
      const newContent = doc.getElementById('page-content');
      if (!newContent) throw new Error('Response had no #page-content');

      runTeardown();

      const scripts = extractScripts(newContent);
      contentEl.innerHTML = newContent.innerHTML;
      document.title = title || doc.title;

      if (pushState) history.pushState({ url: url, title: title }, '', url);

      runScripts(scripts);
      if (typeof updateAuthUI === 'function') updateAuthUI();
      window.scrollTo(0, 0);
    } catch (err) {
      console.error('[SPA] navigation failed, doing a full load instead:', err);
      window.location.href = url;
    }
  }

  document.addEventListener('click', function (e) {
    const link = e.target.closest('.spa-link');
    if (!link) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || link.target === '_blank') return;
    e.preventDefault();
    navigate(link.getAttribute('href'), link.dataset.title);
  });

  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.url) navigate(e.state.url, e.state.title, false);
  });

  history.replaceState({ url: window.location.pathname, title: document.title }, '', window.location.pathname);
})();