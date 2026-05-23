(function () {
  'use strict';

  /* ============================================
     页面加载渐入动画
     ============================================ */
  document.addEventListener('DOMContentLoaded', function () {
    document.body.classList.add('page-enter');
  });

  /* ============================================
     导航栏滚动效果
     ============================================ */
  var navbar = document.querySelector('.navbar');

  function handleNavScroll() {
    if (!navbar) return;
    if (window.scrollY > 20) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  }

  window.addEventListener('scroll', handleNavScroll, { passive: true });
  handleNavScroll();

  /* ============================================
     移动端汉堡菜单切换
     ============================================ */
  var hamburger = document.querySelector('.hamburger');
  var navLinks = document.querySelector('.nav-links');

  if (hamburger && navLinks) {
    hamburger.addEventListener('click', function () {
      hamburger.classList.toggle('active');
      navLinks.classList.toggle('open');
      document.body.style.overflow = navLinks.classList.contains('open') ? 'hidden' : '';
    });

    // 点击导航链接后关闭菜单
    navLinks.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        hamburger.classList.remove('active');
        navLinks.classList.remove('open');
        document.body.style.overflow = '';
      });
    });

    // 窗口变化时重置移动端菜单状态
    window.addEventListener('resize', function () {
      if (window.innerWidth > 768) {
        hamburger.classList.remove('active');
        navLinks.classList.remove('open');
        document.body.style.overflow = '';
      }
    });
  }

  /* ============================================
     当前页面导航高亮
     ============================================ */
  function highlightCurrentNav() {
    var currentPath = window.location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.nav-links a').forEach(function (link) {
      var href = link.getAttribute('href');
      if (href === currentPath) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }
  highlightCurrentNav();

  /* ============================================
     滚动入场动画（Intersection Observer）
     ============================================ */
  function initScrollAnimations() {
    var animTargets = document.querySelectorAll('.fade-in, .fade-in-left, .fade-in-right, .fade-in-scale');

    if (!('IntersectionObserver' in window)) {
      animTargets.forEach(function (el) { el.classList.add('visible'); });
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -40px 0px'
    });

    animTargets.forEach(function (el) { observer.observe(el); });
  }
  initScrollAnimations();

  /* ============================================
     回到顶部按钮
     ============================================ */
  function initBackToTop() {
    var btn = document.querySelector('.back-to-top');

    if (!btn) {
      btn = document.createElement('button');
      btn.className = 'back-to-top';
      btn.setAttribute('aria-label', '回到顶部');
      btn.innerHTML = '↑';
      document.body.appendChild(btn);
    }

    function toggleBtn() {
      if (window.scrollY > 400) {
        btn.classList.add('visible');
      } else {
        btn.classList.remove('visible');
      }
    }

    window.addEventListener('scroll', toggleBtn, { passive: true });
    toggleBtn();

    btn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
  initBackToTop();

  /* ============================================
     FAQ 折叠展开
     ============================================ */
  function initFAQ() {
    document.querySelectorAll('.faq-item').forEach(function (item) {
      var question = item.querySelector('.faq-question');
      if (!question) return;

      question.addEventListener('click', function () {
        var isActive = item.classList.contains('active');

        // 可选：只允许同时展开一个
        // item.parentElement.querySelectorAll('.faq-item.active').forEach(function (openItem) {
        //   if (openItem !== item) openItem.classList.remove('active');
        // });

        item.classList.toggle('active');
      });
    });
  }
  initFAQ();

  /* ============================================
     代码块复制功能
     ============================================ */
  function initCodeCopy() {
    document.querySelectorAll('.code-block').forEach(function (block) {
      var header = block.querySelector('.code-header');
      if (!header) return;

      var copyBtn = header.querySelector('.copy-btn');
      if (!copyBtn) return;

      var code = block.querySelector('pre code') || block.querySelector('pre');
      if (!code) return;

      copyBtn.addEventListener('click', function () {
        var text = code.textContent || code.innerText;

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            showCopiedFeedback(copyBtn);
          }).catch(function () {
            fallbackCopy(text, copyBtn);
          });
        } else {
          fallbackCopy(text, copyBtn);
        }
      });
    });
  }

  function fallbackCopy(text, btn) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      showCopiedFeedback(btn);
    } catch (e) {
      // 静默失败
    }
    document.body.removeChild(textarea);
  }

  function showCopiedFeedback(btn) {
    var originalText = btn.textContent;
    btn.textContent = '✓ 已复制';
    btn.style.color = 'var(--accent)';
    setTimeout(function () {
      btn.textContent = originalText;
      btn.style.color = '';
    }, 2000);
  }
  initCodeCopy();

  /* ============================================
     轻触友好的触发优化
     ============================================ */
  function initTouchOptimizations() {
    var isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    if (isTouchDevice) {
      document.documentElement.classList.add('is-touch');

      // 触摸设备上卡片点击触发 hover 效果
      document.querySelectorAll('.card').forEach(function (card) {
        card.addEventListener('touchstart', function () {
          this.classList.add('touch-hover');
        }, { passive: true });
      });
    }
  }
  initTouchOptimizations();

  /* ============================================
     平滑锚点滚动（所有内部锚点链接）
     ============================================ */
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
      anchor.addEventListener('click', function (e) {
        var targetId = this.getAttribute('href');
        if (targetId === '#') return;

        var target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          var navHeight = navbar ? navbar.offsetHeight : 64;
          var targetPos = target.getBoundingClientRect().top + window.scrollY - navHeight;
          window.scrollTo({ top: targetPos, behavior: 'smooth' });
        }
      });
    });
  }
  initSmoothScroll();

})();