/**
 * Abhinav Group AI Property Sales Chatbot Widget
 * Version: 1.0.0
 *
 * Vanilla JS — no framework dependencies.
 * Loads asynchronously, does not block page rendering.
 * Fully self-contained: injects its own HTML + CSS.
 *
 * Usage (via WordPress plugin or manual):
 *   <script>
 *     window.AbhinavChatConfig = { apiBase: 'https://api.example.com' };
 *   </script>
 *   <script src="abhinav-chatbot.min.js" defer></script>
 */

(function () {
  'use strict';

  /* ── Configuration ─────────────────────────────────────── */
  var cfg = window.AbhinavChatConfig || {};
  var API_BASE   = (cfg.apiBase   || 'http://localhost:8000').replace(/\/$/, '');
  var WIDGET_KEY = cfg.widgetKey  || '';          // Set in WordPress plugin settings
  var SOURCE_PAGE = cfg.sourcePage || window.location.href;
  var LANG        = cfg.lang      || 'auto';      // 'en' | 'hi' | 'auto'
  var POSITION    = cfg.position  || 'bottom-right';
  var BRAND_COLOR = cfg.brandColor || '#0284c7';  // Sky Blue primary
  var ACCENT_COLOR = cfg.accentColor || '#38bdf8'; // Sky Blue accent

  /* ── State ─────────────────────────────────────────────── */
  var state = {
    open: false,
    sessionToken: null,
    messages: [],
    isTyping: false,
    leadCaptured: false,
    leadStep: null,  // null | 'name' | 'phone' | 'confirm'
    leadData: {},
  };

  /* ── Translations ───────────────────────────────────────── */
  var T = {
    en: {
      title: 'Abhinav Group',
      subtitle: 'Property Assistant',
      online: 'We are online to assist you',
      placeholder: 'Type your message...',
      send: 'Send',
      welcome: 'Hello! Welcome to Abhinav Group. 🏠\n\nI\'m your AI property assistant. I can help you explore our projects, answer your questions, and connect you with our sales team.\n\nHow may I help you today?',
      qr_projects: 'Explore Projects',
      qr_residential: 'Residential',
      qr_commercial: 'Commercial Properties',
      qr_pricing: 'Check Pricing',
      qr_brochure: 'Download Brochure',
      qr_sales: 'Speak to Sales',
      lead_prompt: 'Would you like our sales team to contact you with more details?',
      lead_name: 'Please share your name:',
      lead_phone: 'Your 10-digit mobile number:',
      lead_email: 'Email address (optional):',
      lead_confirm: 'Thank you! Our team will contact you shortly. 📞',
      lead_btn: 'Get a Callback',
      typing: 'Typing...',
      error: 'Connection issue. Please try again or call us at +91 9309505388.',
      powered: 'Powered by Abhinav Group AI',
      close: 'Close chat',
      open: 'Chat with us',
    },
    hi: {
      title: 'अभिनव ग्रुप',
      subtitle: 'प्रॉपर्टी असिस्टेंट',
      online: 'हम आपकी सहायता के लिए ऑनलाइन हैं',
      placeholder: 'अपना संदेश टाइप करें...',
      send: 'भेजें',
      welcome: 'नमस्ते! अभिनव ग्रुप में आपका स्वागत है। 🏠\n\nमैं आपका AI प्रॉपर्टी असिस्टेंट हूं।\n\nआज मैं आपकी कैसे सहायता कर सकता हूं?',
      qr_projects: 'प्रोजेक्ट देखें',
      qr_residential: 'आवासीय',
      qr_commercial: 'व्यावसायिक संपत्ति',
      qr_pricing: 'कीमत जानें',
      qr_brochure: 'ब्रोशर डाउनलोड करें',
      qr_sales: 'सेल्स टीम से बात करें',
      lead_prompt: 'क्या आप चाहते हैं कि हमारी सेल्स टीम आपसे संपर्क करे?',
      lead_name: 'कृपया अपना नाम बताएं:',
      lead_phone: 'आपका 10 अंकों का मोबाइल नंबर:',
      lead_email: 'ईमेल आईडी (वैकल्पिक):',
      lead_confirm: 'धन्यवाद! हमारी टीम जल्द संपर्क करेगी। 📞',
      lead_btn: 'कॉलबैक के लिए अनुरोध करें',
      typing: 'टाइप हो रहा है...',
      error: 'कनेक्शन त्रुटि। कृपया पुनः प्रयास करें या +91 9309505388 पर कॉल करें।',
      powered: 'Abhinav Group AI द्वारा संचालित',
      close: 'चैट बंद करें',
      open: 'हमसे चैट करें',
    },
  };

  function t(key) {
    var lang = state.lang || 'en';
    return (T[lang] && T[lang][key]) ? T[lang][key] : (T.en[key] || key);
  }

  /* ── CSS Injection ──────────────────────────────────────── */
  function injectStyles() {
    var css = [
      /* Widget container */
      '#abhinav-chat-widget{position:fixed;z-index:999999;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:14px;line-height:1.5}',
      '#abhinav-chat-widget.pos-bottom-right{bottom:24px;right:24px}',
      '#abhinav-chat-widget.pos-bottom-left{bottom:24px;left:24px}',

      /* Launcher bubble */
      '#abhinav-launcher{width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,' + BRAND_COLOR + ',' + ACCENT_COLOR + ');cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 20px rgba(2,132,199,0.4);border:none;transition:transform 0.2s,box-shadow 0.2s;position:relative}',
      '#abhinav-launcher:hover{transform:scale(1.08);box-shadow:0 6px 25px rgba(2,132,199,0.5)}',
      '#abhinav-launcher svg{width:28px;height:28px;fill:white;transition:opacity 0.2s}',
      '#abhinav-launcher .badge{position:absolute;top:-4px;right:-4px;width:18px;height:18px;border-radius:50%;background:#e53935;color:white;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;animation:pulse 2s infinite}',
      '@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.15)}}',

      /* Chat panel */
      '#abhinav-chat-panel{width:360px;height:560px;background:white;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.18);display:flex;flex-direction:column;overflow:hidden;transition:all 0.3s ease;transform-origin:bottom right}',
      '#abhinav-chat-panel.hidden{opacity:0;transform:scale(0.85) translateY(20px);pointer-events:none;position:absolute;bottom:70px;right:0}',
      '#abhinav-chat-panel.visible{opacity:1;transform:scale(1) translateY(0);position:absolute;bottom:70px;right:0}',

      /* Header */
      '#abhinav-header{background:linear-gradient(135deg,' + BRAND_COLOR + ' 0%,#0369a1 100%);padding:14px 16px;display:flex;align-items:center;gap:10px;flex-shrink:0}',
      '#abhinav-header-logo{width:38px;height:38px;border-radius:50%;background:white;display:flex;align-items:center;justify-content:center;font-weight:700;color:' + BRAND_COLOR + ';font-size:14px;flex-shrink:0;box-shadow:0 2px 6px rgba(0,0,0,0.1)}',
      '#abhinav-header-info{flex:1;min-width:0}',
      '#abhinav-header-title{color:white;font-weight:700;font-size:15px;margin:0}',
      '#abhinav-header-subtitle{color:rgba(255,255,255,0.85);font-size:11px;margin:0}',
      '#abhinav-header-status{display:flex;align-items:center;gap:5px;margin-top:2px}',
      '#abhinav-header-status .dot{width:7px;height:7px;border-radius:50%;background:#4caf50;animation:pulse 2s infinite}',
      '#abhinav-header-status span{color:rgba(255,255,255,0.9);font-size:11px}',
      '#abhinav-close-btn{background:rgba(255,255,255,0.2);border:none;color:white;cursor:pointer;padding:6px;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background 0.2s}',
      '#abhinav-close-btn:hover{background:rgba(255,255,255,0.35)}',

      /* Messages area */
      '#abhinav-messages{flex:1;overflow-y:auto;padding:16px 12px;display:flex;flex-direction:column;gap:10px;background:#f8fafc}',
      '#abhinav-messages::-webkit-scrollbar{width:4px}',
      '#abhinav-messages::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px}',

      /* Message bubbles */
      '.ag-msg{display:flex;flex-direction:column;max-width:82%;animation:fadeUp 0.25s ease;flex-shrink:0}',
      '@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}',
      '.ag-msg.user{align-self:flex-end;align-items:flex-end}',
      '.ag-msg.bot{align-self:flex-start;align-items:flex-start}',
      '.ag-bubble{padding:10px 14px;border-radius:18px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-break:break-word}',
      '.ag-msg.user .ag-bubble{background:' + BRAND_COLOR + ';color:white;border-bottom-right-radius:4px}',
      '.ag-msg.bot .ag-bubble{background:white;color:#1e293b;border-bottom-left-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}',
      '.ag-time{font-size:10px;color:#94a3b8;margin-top:3px;padding:0 4px}',

      /* Typing indicator */
      '#abhinav-typing{align-self:flex-start;background:white;border-radius:18px;border-bottom-left-radius:4px;padding:12px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);flex-shrink:0}',
      '#abhinav-typing span{display:inline-block;width:7px;height:7px;border-radius:50%;background:#94a3b8;margin:0 2px;animation:bounce 1.2s infinite}',
      '#abhinav-typing span:nth-child(2){animation-delay:0.2s}',
      '#abhinav-typing span:nth-child(3){animation-delay:0.4s}',
      '@keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}',

      /* Quick replies */
      '#abhinav-quick-replies{padding:8px 12px;display:flex;flex-wrap:wrap;gap:6px;background:#f8fafc;border-top:1px solid #e2e8f0;flex-shrink:0}',
      '.ag-qr{background:white;border:1.5px solid ' + BRAND_COLOR + ';color:' + BRAND_COLOR + ';border-radius:20px;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.2s;white-space:nowrap}',
      '.ag-qr:hover{background:' + BRAND_COLOR + ';color:white;box-shadow:0 2px 8px rgba(2,132,199,0.25)}',

      /* Input area */
      '#abhinav-input-area{padding:12px;background:white;border-top:1px solid #e2e8f0;display:flex;gap:8px;flex-shrink:0;align-items:flex-end}',
      '#abhinav-input{flex:1;border:1.5px solid #cbd5e1;border-radius:24px;padding:10px 16px;font-size:14px;outline:none;resize:none;max-height:100px;font-family:inherit;transition:border-color 0.2s;line-height:1.4}',
      '#abhinav-input:focus{border-color:' + BRAND_COLOR + '}',
      '#abhinav-send{width:40px;height:40px;border-radius:50%;background:' + BRAND_COLOR + ';border:none;color:white;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background 0.2s;align-self:flex-end}',
      '#abhinav-send:hover{background:#0369a1}',
      '#abhinav-send:disabled{background:#94a3b8;cursor:not-allowed}',
      '#abhinav-send svg{width:18px;height:18px;fill:white}',

      /* Lead capture form */
      '.ag-lead-card{background:white;border:1.5px solid ' + BRAND_COLOR + ';border-radius:12px;padding:14px;margin-top:4px;animation:fadeUp 0.25s ease;box-shadow:0 2px 8px rgba(2,132,199,0.15);flex-shrink:0}',
      '.ag-lead-card p{margin:0 0 10px;color:#1e293b;font-size:13px}',
      '.ag-lead-input{width:100%;border:1.5px solid #cbd5e1;border-radius:8px;padding:9px 12px;font-size:13px;outline:none;box-sizing:border-box;font-family:inherit;transition:border-color 0.2s}',
      '.ag-lead-input:focus{border-color:' + BRAND_COLOR + '}',
      '.ag-lead-btn{margin-top:10px;width:100%;background:linear-gradient(135deg,' + BRAND_COLOR + ',#0369a1);color:white;border:none;border-radius:8px;padding:10px;font-size:13px;font-weight:700;cursor:pointer;transition:opacity 0.2s}',
      '.ag-lead-btn:hover{opacity:0.92}',

      /* Project card */
      '.ag-project-card{background:white;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 3px 12px rgba(0,0,0,0.08);margin-top:8px;margin-bottom:6px;animation:fadeUp 0.25s ease;display:flex;flex-direction:column;flex-shrink:0;min-height:240px}',
      '.ag-project-card-img-wrap{width:100%;height:160px;background:#f1f5f9;overflow:hidden;position:relative;flex-shrink:0}',
      '.ag-project-card-img{width:100%;height:160px;min-height:160px;max-height:160px;object-fit:cover;display:block}',
      '.ag-project-card-body{padding:12px 14px;flex-shrink:0}',
      '.ag-project-card-title{font-weight:700;color:' + BRAND_COLOR + ';font-size:14px;margin:0 0 4px}',
      '.ag-project-card-info{font-size:12px;color:#64748b;margin:0 0 10px;line-height:1.4}',
      '.ag-project-card-btn{display:inline-block;background:linear-gradient(135deg,' + BRAND_COLOR + ',#0369a1);color:white;border-radius:6px;padding:6px 14px;font-size:12px;font-weight:600;text-decoration:none;cursor:pointer;border:none;transition:opacity 0.2s}',
      '.ag-project-card-btn:hover{opacity:0.92}',

      /* Footer */
      '#abhinav-footer{padding:6px;text-align:center;background:white;border-top:1px solid #f1f5f9}',
      '#abhinav-footer a{font-size:10px;color:#94a3b8;text-decoration:none}',
      '#abhinav-footer a:hover{color:' + BRAND_COLOR + '}',

      /* Mobile responsive */
      '@media(max-width:400px){#abhinav-chat-panel{width:calc(100vw - 20px);height:calc(100vh - 90px);bottom:70px!important;right:10px!important}}',
    ].join('');

    var style = document.createElement('style');
    style.id = 'abhinav-chat-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ── SVG Icons ──────────────────────────────────────────── */
  var ICON_CHAT = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20 2H4a2 2 0 00-2 2v18l4-4h14a2 2 0 002-2V4a2 2 0 00-2-2zm-2 10H6V10h12v2zm0-4H6V6h12v2z"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

  /* ── HTML Structure ─────────────────────────────────────── */
  function buildHTML() {
    var posClass = 'pos-' + POSITION;
    var html = [
      '<div id="abhinav-chat-widget" class="' + posClass + '">',

      /* Chat panel */
      '<div id="abhinav-chat-panel" class="hidden" role="dialog" aria-label="Abhinav Group Chat">',

      /* Header */
      '<div id="abhinav-header">',
      '  <div id="abhinav-header-logo">AG</div>',
      '  <div id="abhinav-header-info">',
      '    <p id="abhinav-header-title">Abhinav Group</p>',
      '    <p id="abhinav-header-subtitle">' + t('subtitle') + '</p>',
      '    <div id="abhinav-header-status"><div class="dot"></div><span>' + t('online') + '</span></div>',
      '  </div>',
      '  <button id="abhinav-close-btn" aria-label="' + t('close') + '">' + ICON_CLOSE + '</button>',
      '</div>',

      /* Messages */
      '<div id="abhinav-messages"></div>',

      /* Quick replies */
      '<div id="abhinav-quick-replies"></div>',

      /* Input */
      '<div id="abhinav-input-area">',
      '  <textarea id="abhinav-input" rows="1" placeholder="' + t('placeholder') + '" aria-label="' + t('placeholder') + '"></textarea>',
      '  <button id="abhinav-send" aria-label="' + t('send') + '">' + ICON_SEND + '</button>',
      '</div>',

      /* Footer */
      '<div id="abhinav-footer"><a href="https://abhinavgroup.co.in" target="_blank" rel="noopener">' + t('powered') + '</a></div>',

      '</div>',  /* /chat-panel */

      /* Launcher */
      '<button id="abhinav-launcher" aria-label="' + t('open') + '">',
      '  ' + ICON_CHAT,
      '  <div class="badge">1</div>',
      '</button>',

      '</div>',  /* /widget */
    ].join('\n');

    var container = document.createElement('div');
    container.innerHTML = html;
    document.body.appendChild(container.firstChild);
  }

  /* ── DOM References ─────────────────────────────────────── */
  var el = {};
  function cacheEls() {
    el.widget       = document.getElementById('abhinav-chat-widget');
    el.panel        = document.getElementById('abhinav-chat-panel');
    el.launcher     = document.getElementById('abhinav-launcher');
    el.messages     = document.getElementById('abhinav-messages');
    el.quickReplies = document.getElementById('abhinav-quick-replies');
    el.input        = document.getElementById('abhinav-input');
    el.sendBtn      = document.getElementById('abhinav-send');
    el.closeBtn     = document.getElementById('abhinav-close-btn');
    el.badge        = el.launcher.querySelector('.badge');
  }

  /* ── Time Helper ────────────────────────────────────────── */
  function getTime() {
    var d = new Date();
    return d.getHours() + ':' + ('0' + d.getMinutes()).slice(-2) + (d.getHours() >= 12 ? ' PM' : ' AM');
  }

  /* ── Clean Message Formatting (Strip raw markdown artifacts like ###, ***) ── */
  function formatWidgetMessage(raw) {
    if (!raw) return '';
    // Strip markdown heading hashes (###, ##, #) at line start
    var cleaned = raw.replace(/^[#]{1,6}\s*/gm, '');
    // Strip horizontal dividers (---, ***, ___)
    cleaned = cleaned.replace(/^[*\-_]{3,}\s*$/gm, '');
    // Strip triple or more asterisks
    cleaned = cleaned.replace(/\*{3,}/g, '');
    // Trim extra consecutive newlines
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n').trim();

    // Escape HTML first for XSS safety
    var safe = escapeHtml(cleaned);

    // Convert **bold** to <strong>bold</strong>
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Convert bullets (* item or - item) at start of lines into clean bullet • item
    safe = safe.replace(/^[*\-]\s+/gm, '• ');

    // Convert newlines to <br>
    safe = safe.replace(/\n/g, '<br>');

    return safe;
  }

  /* ── Render Messages ────────────────────────────────────── */
  function appendMessage(role, text, extra) {
    extra = extra || {};

    // Remove typing indicator if present
    var typingEl = document.getElementById('abhinav-typing');
    if (typingEl) typingEl.remove();

    var div = document.createElement('div');
    div.className = 'ag-msg ' + role;

    var bubble = document.createElement('div');
    bubble.className = 'ag-bubble';
    bubble.innerHTML = formatWidgetMessage(text);
    div.appendChild(bubble);

    var timeEl = document.createElement('div');
    timeEl.className = 'ag-time';
    timeEl.textContent = getTime();
    div.appendChild(timeEl);

    el.messages.appendChild(div);

    // Render project cards if present
    if (extra.project_cards && extra.project_cards.length) {
      extra.project_cards.forEach(function (card) {
        appendProjectCard(card);
      });
    }

    if (role === 'user') {
      scrollToBottom();
    } else {
      scrollToMessageStart(div);
    }
  }

  function appendProjectCard(card) {
    var div = document.createElement('div');
    div.className = 'ag-project-card';
    var rawUrl = card.image_url || '';
    var fullUrl = rawUrl;
    if (fullUrl && !fullUrl.startsWith('http://') && !fullUrl.startsWith('https://')) {
      var base = API_BASE || (typeof window !== 'undefined' && window.location.origin ? window.location.origin : '');
      fullUrl = base ? base.replace(/\/$/, '') + (fullUrl.startsWith('/') ? '' : '/') + fullUrl : fullUrl;
    }
    var imgHtml = fullUrl
      ? '<div class="ag-project-card-img-wrap">' +
        '<img class="ag-project-card-img" src="' + escapeHtml(fullUrl) + '" alt="' + escapeHtml(card.name) + '" loading="eager" decoding="async" onerror="if(!this._retried && \'' + escapeHtml(rawUrl) + '\' !== this.src){this._retried=true; this.src=\'' + escapeHtml(rawUrl) + '\';}">' +
        '</div>'
      : '';
    div.innerHTML = imgHtml +
      '<div class="ag-project-card-body">' +
      '<p class="ag-project-card-title">' + escapeHtml(card.name) + '</p>' +
      '<p class="ag-project-card-info">' + escapeHtml(card.location || '') + (card.config ? ' · ' + card.config : '') + '</p>' +
      '<button class="ag-project-card-btn">' + (state.lang === 'hi' ? 'प्रोजेक्ट देखें' : 'View Project') + '</button>' +
      '</div>';
    var btn = div.querySelector('.ag-project-card-btn');
    if (btn) {
      btn.addEventListener('click', function (e) {
        if (e) {
          e.preventDefault();
          e.stopPropagation();
        }
        if (card.url) window.open(card.url, '_blank');
      });
    }
    el.messages.appendChild(div);
  }

  function showTyping() {
    var typingEl = document.createElement('div');
    typingEl.id = 'abhinav-typing';
    typingEl.innerHTML = '<span></span><span></span><span></span>';
    el.messages.appendChild(typingEl);
    scrollToBottom();
  }

  function renderQuickReplies(replies) {
    el.quickReplies.innerHTML = '';
    if (!replies || !replies.length) return;
    replies.forEach(function (reply) {
      var btn = document.createElement('button');
      btn.className = 'ag-qr';
      btn.textContent = reply;
      btn.addEventListener('click', function (e) {
        if (e) {
          e.preventDefault();
          e.stopPropagation();
        }
        sendMessage(reply);
      });
      el.quickReplies.appendChild(btn);
    });
  }

  function showLeadCard() {
    if (state.leadCaptured) return;
    // If an unanswered form exists higher up in the chat, reposition it to the active bottom
    var existing = document.getElementById('ag-lead-form');
    if (existing) {
      existing.remove();
    }
    var card = document.createElement('div');
    card.className = 'ag-lead-card';
    card.id = 'ag-lead-form';
    card.innerHTML =
      '<p>' + t('lead_name') + '</p>' +
      '<input class="ag-lead-input" id="ag-lead-name" type="text" placeholder="Your name" autocomplete="name">' +
      '<p style="margin-top:10px">' + t('lead_phone') + '</p>' +
      '<input class="ag-lead-input" id="ag-lead-phone" type="tel" placeholder="10-digit mobile" autocomplete="tel" maxlength="13">' +
      '<p style="margin-top:10px">' + t('lead_email') + '</p>' +
      '<input class="ag-lead-input" id="ag-lead-email" type="email" placeholder="name@example.com (optional)" autocomplete="email">' +
      '<button class="ag-lead-btn" id="ag-lead-submit">' + t('lead_btn') + '</button>';
    el.messages.appendChild(card);

    document.getElementById('ag-lead-submit').addEventListener('click', function (e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      submitLead();
    });
  }

  function submitLead() {
    var name  = (document.getElementById('ag-lead-name').value || '').trim();
    var phone = (document.getElementById('ag-lead-phone').value || '').trim().replace(/\D/g, '');
    var email = (document.getElementById('ag-lead-email') ? document.getElementById('ag-lead-email').value || '' : '').trim();

    if (!name) {
      document.getElementById('ag-lead-name').style.borderColor = 'red';
      return;
    }
    if (phone.length < 10) {
      document.getElementById('ag-lead-phone').style.borderColor = 'red';
      return;
    }

    state.leadData = { name: name, phone: phone, email: email };
    var formEl = document.getElementById('ag-lead-form');
    if (formEl) formEl.remove();

    // POST to leads API
    apiPost('/api/v1/leads/', {
      name: name,
      phone: phone,
      email: email || undefined,
      consent_to_contact: true,
      source_page: SOURCE_PAGE,
      session_token: state.sessionToken,
    }).then(function (data) {
      state.leadCaptured = true;
      appendMessage('bot', t('lead_confirm'));
      renderQuickReplies([t('qr_projects'), t('qr_brochure')]);
    }).catch(function () {
      appendMessage('bot', 'Thank you! You can reach us directly at +91 9309505388.');
    });
  }

  function scrollToMessageStart(msgEl) {
    if (!el.messages || !msgEl) return;
    function align() {
      if (el.messages && msgEl) {
        var topPos = msgEl.offsetTop;
        if (msgEl.offsetParent !== el.messages) {
          topPos = msgEl.offsetTop - el.messages.offsetTop;
        }
        topPos = Math.max(0, topPos - 8);
        el.messages.scrollTop = topPos;
      }
    }
    align();
    setTimeout(align, 60);
    setTimeout(align, 150);
  }

  function scrollToBottom() {
    if (el.messages) {
      el.messages.scrollTop = el.messages.scrollHeight;
    }
    setTimeout(function () {
      if (el.messages) {
        el.messages.scrollTop = el.messages.scrollHeight;
      }
    }, 50);
  }

  function escapeHtml(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ── API Calls ──────────────────────────────────────────── */
  function apiPost(path, data) {
    var headers = { 'Content-Type': 'application/json' };
    if (WIDGET_KEY) headers['X-Widget-Key'] = WIDGET_KEY;
    return fetch(API_BASE + path, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(data),
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  /* ── Send Message ───────────────────────────────────────── */
  function sendMessage(text) {
    text = (text || el.input.value || '').trim();
    if (!text || state.isTyping) return;

    el.input.value = '';
    el.input.style.height = 'auto';
    el.quickReplies.innerHTML = '';
    el.badge.style.display = 'none';

    appendMessage('user', text);
    state.isTyping = true;
    el.sendBtn.disabled = true;
    showTyping();

    var payload = {
      message: text,
      source_page: SOURCE_PAGE,
    };
    if (state.sessionToken) payload.session_token = state.sessionToken;

    apiPost('/api/v1/chat/message', payload)
      .then(function (data) {
        state.isTyping = false;
        el.sendBtn.disabled = false;

        if (data.session_token) state.sessionToken = data.session_token;
        if (data.language) state.lang = data.language;

        appendMessage('bot', data.reply, { project_cards: data.project_cards });

        // Show quick replies
        if (data.quick_replies && data.quick_replies.length) {
          renderQuickReplies(data.quick_replies);
        }

        // Offer lead capture after pricing, escalation, brochure, project, or configuration inquiries
        var leadIntents = [
          'pricing_enquiry', 'escalation', 'brochure_request',
          'project_enquiry_samsara', 'project_enquiry_greenfield',
          'project_enquiry_curve', 'project_enquiry_business_bay',
          'project_enquiry_aeromall', 'config_enquiry', 'nri_enquiry'
        ];
        if (!state.leadCaptured && leadIntents.indexOf(data.intent) !== -1) {
          setTimeout(showLeadCard, 700);
        }

        // Track message count for proactive lead prompt (after 2 exchanges / 4 messages)
        state.messages.push({ role: 'user', text: text });
        state.messages.push({ role: 'bot', text: data.reply });
        if (!state.leadCaptured && state.messages.length >= 4) {
          setTimeout(showLeadCard, 900);
        }
      })
      .catch(function (err) {
        state.isTyping = false;
        el.sendBtn.disabled = false;
        var typingEl = document.getElementById('abhinav-typing');
        if (typingEl) typingEl.remove();
        appendMessage('bot', t('error'));
      });
  }

  /* ── Open / Close ───────────────────────────────────────── */
  function openWidget() {
    state.open = true;
    el.panel.classList.remove('hidden');
    el.panel.classList.add('visible');
    el.launcher.querySelector('svg').style.opacity = '0';
    el.badge.style.display = 'none';
    el.input.focus();

    // Show welcome message on first open
    if (state.messages.length === 0) {
      setTimeout(function () {
        showTyping();
        setTimeout(function () {
          var typingEl = document.getElementById('abhinav-typing');
          if (typingEl) typingEl.remove();
          appendMessage('bot', t('welcome'));
          renderQuickReplies([
            t('qr_projects'), t('qr_residential'),
            t('qr_pricing'), t('qr_sales'),
          ]);
        }, 900);
      }, 300);
    }
  }

  function closeWidget() {
    state.open = false;
    el.panel.classList.remove('visible');
    el.panel.classList.add('hidden');
    el.launcher.querySelector('svg').style.opacity = '1';
  }

  function toggleWidget() {
    if (state.open) closeWidget();
    else openWidget();
  }

  /* ── Event Listeners ────────────────────────────────────── */
  function bindEvents() {
    el.launcher.addEventListener('click', function (e) {
      if (e) e.stopPropagation();
      toggleWidget();
    });
    el.closeBtn.addEventListener('click', function (e) {
      if (e) e.stopPropagation();
      closeWidget();
    });
    el.sendBtn.addEventListener('click', function (e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      sendMessage();
    });

    // Send on Enter (Shift+Enter = newline)
    el.input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        sendMessage();
      }
    });

    // Auto-resize textarea
    el.input.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 100) + 'px';
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && state.open) closeWidget();
    });

    // Close on outside click (robust check against detached buttons & internal elements)
    document.addEventListener('click', function (e) {
      if (!state.open) return;
      if (!e || !e.target) return;
      // If clicked inside the launcher, ignore
      if (el.launcher && (el.launcher === e.target || el.launcher.contains(e.target))) return;
      // If clicked inside the chat panel, ignore
      if (el.widget && el.widget.contains(e.target)) return;
      // If clicked node was removed from DOM during event handling (e.g. quick reply cleared), ignore
      if (!document.body.contains(e.target)) return;
      // Check closest container if browser supports it
      if (e.target.closest && (e.target.closest('#abhinav-chat-panel') || e.target.closest('#abhinav-launcher') || e.target.closest('#abhinav-chat-widget'))) return;
      closeWidget();
    });
  }

  /* ── Init ───────────────────────────────────────────────── */
  function init() {
    // Set initial language
    state.lang = LANG === 'auto' ? 'en' : LANG;

    injectStyles();
    buildHTML();
    cacheEls();
    bindEvents();

    // Auto-open after delay if configured
    if (cfg.autoOpen) {
      setTimeout(openWidget, cfg.autoOpenDelay || 3000);
    }

    console.log('[AbhinavChat] Widget initialized. API:', API_BASE);
  }

  /* ── Boot ───────────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose public API for external control
  window.AbhinavChat = {
    open: openWidget,
    close: closeWidget,
    sendMessage: sendMessage,
  };

})();
