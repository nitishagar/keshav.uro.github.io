(function () {
  'use strict';
  const STORAGE_KEY = 'uro-lang';
  const root = document.documentElement;

  function apply(lang) {
    const hi = lang === 'hi';
    root.classList.toggle('lang-hi', hi);
    root.setAttribute('lang', hi ? 'hi-IN' : 'en-IN');
    document.querySelectorAll('[data-i18n-en]').forEach(function (el) {
      const en = el.getAttribute('data-i18n-en');
      const hiText = el.getAttribute('data-i18n-hi');
      if (hi && hiText) el.textContent = hiText;
      else if (en) el.textContent = en;
    });
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    const toggle = document.getElementById('lang-toggle');
    if (toggle) toggle.setAttribute('aria-pressed', String(hi));
  }

  function init() {
    let saved = 'en';
    try { saved = localStorage.getItem(STORAGE_KEY) || 'en'; } catch (e) {}
    apply(saved);
    const toggle = document.getElementById('lang-toggle');
    if (toggle) toggle.addEventListener('click', function () {
      apply(root.classList.contains('lang-hi') ? 'en' : 'hi');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
