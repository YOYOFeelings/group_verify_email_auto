(function () {
  'use strict';

  var container = document.getElementById('features-container');
  if (!container) return;

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function renderPageHeader(data) {
    var section = document.createElement('section');
    section.className = 'page-header section';
    section.id = 'page-header';
    var div = document.createElement('div');
    div.className = 'container';
    div.innerHTML = '<h1>' + escapeHtml(data.title) + '</h1><p class="page-header-desc">' + escapeHtml(data.desc) + '</p>';
    section.appendChild(div);
    return section;
  }

  function renderDualVerify(data) {
    var section = document.createElement('section');
    section.className = 'dual-verify section';
    section.id = 'dual-verify';
    var div = document.createElement('div');
    div.className = 'container';
    var html = '<h2 class="section-title">' + escapeHtml(data.title) + '</h2>';
    html += '<p class="section-desc">' + escapeHtml(data.desc) + '</p>';
    html += '<div class="verify-cards">';
    for (var i = 0; i < data.cards.length; i++) {
      var card = data.cards[i];
      var cardClass = card.title === '邮箱验证' ? 'verify-card-email' : 'verify-card-math';
      html += '<article class="verify-card ' + cardClass + '">';
      html += '<div class="verify-card-header"><span class="verify-card-icon">' + card.icon + '</span><h3>' + escapeHtml(card.title) + '</h3></div>';
      html += '<div class="verify-card-body"><p>' + escapeHtml(card.desc) + '</p></div>';
      html += '</article>';
    }
    html += '</div>';
    div.innerHTML = html;
    section.appendChild(div);
    return section;
  }

  function renderVerifyFlow(data) {
    var section = document.createElement('section');
    section.className = 'verify-flow section';
    section.id = 'verify-flow';
    var div = document.createElement('div');
    div.className = 'container';
    var html = '<h2 class="section-title">' + escapeHtml(data.title) + '</h2>';
    html += '<p class="section-desc">' + escapeHtml(data.desc) + '</p>';
    html += '<div class="flow-steps">';
    for (var i = 0; i < data.steps.length; i++) {
      var step = data.steps[i];
      html += '<div class="flow-step">';
      html += '<div class="flow-step-number">' + escapeHtml(step.num) + '</div>';
      html += '<div class="flow-step-content"><h3>' + escapeHtml(step.title) + '</h3><p>' + escapeHtml(step.desc) + '</p></div>';
      if (i < data.steps.length - 1) {
        html += '<div class="flow-step-arrow">&darr;</div>';
      }
      html += '</div>';
    }
    html += '</div>';
    div.innerHTML = html;
    section.appendChild(div);
    return section;
  }

  function renderCoreFeatures(data) {
    var section = document.createElement('section');
    section.className = 'core-features section';
    section.id = 'core-features';
    var div = document.createElement('div');
    div.className = 'container';
    var html = '<h2 class="section-title">' + escapeHtml(data.title) + '</h2>';
    html += '<p class="section-desc">' + escapeHtml(data.desc) + '</p>';
    html += '<div class="core-grid">';
    for (var i = 0; i < data.cards.length; i++) {
      var card = data.cards[i];
      html += '<article class="core-card">';
      html += '<div class="core-card-icon">' + card.icon + '</div>';
      html += '<h3>' + escapeHtml(card.title) + '</h3>';
      html += '<p>' + escapeHtml(card.desc) + '</p>';
      html += '</article>';
    }
    html += '</div>';
    div.innerHTML = html;
    section.appendChild(div);
    return section;
  }

  function renderCTA(data) {
    var section = document.createElement('section');
    section.className = 'cta section';
    section.id = 'cta';
    var div = document.createElement('div');
    div.className = 'container';
    div.innerHTML = '<h2>' + escapeHtml(data.title) + '</h2><p>' + escapeHtml(data.desc) + '</p><div class="cta-actions"><a href="' + data.btnLink.replace(/"/g, '&quot;') + '" class="btn btn-primary">' + escapeHtml(data.btnText) + ' &rarr;</a></div>';
    section.appendChild(div);
    return section;
  }

  function renderContributors(data) {
    var section = document.createElement('section');
    section.className = 'contributors section';
    section.id = 'contributors';
    var div = document.createElement('div');
    div.className = 'container';
    var html = '<h2 class="section-title">' + escapeHtml(data.title) + '</h2>';
    html += '<p class="section-desc">' + escapeHtml(data.desc) + '</p>';
    html += '<div class="contributors-list">';
    for (var i = 0; i < data.list.length; i++) {
      var person = data.list[i];
      html += '<a href="' + person.link.replace(/"/g, '&quot;') + '" class="contributor-item" target="_blank" rel="noopener">';
      html += '<span class="contributor-name">' + escapeHtml(person.name) + '</span>';
      html += '<span class="contributor-role">' + escapeHtml(person.role) + '</span>';
      html += '</a>';
    }
    html += '</div>';
    div.innerHTML = html;
    section.appendChild(div);
    return section;
  }

  function renderAll(data) {
    container.innerHTML = '';
    container.appendChild(renderPageHeader(data.pageHeader));
    container.appendChild(renderDualVerify(data.dualVerify));
    container.appendChild(renderVerifyFlow(data.verifyFlow));
    container.appendChild(renderCoreFeatures(data.coreFeatures));
    container.appendChild(renderCTA(data.cta));
    if (data.contributors) {
      container.appendChild(renderContributors(data.contributors));
    }
  }

  function renderFallback() {
    container.innerHTML =
      '<section class="page-header section" id="page-header">' +
        '<div class="container"><h1>功能介绍</h1><p class="page-header-desc">全方位了解 QQ群邮箱验证码插件 的核心能力</p></div>' +
      '</section>' +
      '<section class="dual-verify section" id="dual-verify">' +
        '<div class="container">' +
          '<h2 class="section-title">双验证体系</h2>' +
          '<p class="section-desc">两种验证方式，灵活应对不同场景</p>' +
          '<div class="verify-cards">' +
            '<article class="verify-card verify-card-email">' +
              '<div class="verify-card-header"><span class="verify-card-icon">&#x1F4E7;</span><h3>邮箱验证</h3></div>' +
              '<div class="verify-card-body"><p>系统自动获取用户QQ号，发送验证码到QQ邮箱，验证身份真实性</p></div>' +
            '</article>' +
            '<article class="verify-card verify-card-math">' +
              '<div class="verify-card-header"><span class="verify-card-icon">&#x2797;</span><h3>数学题验证</h3></div>' +
              '<div class="verify-card-body"><p>快速出题，无需邮箱配置，适合低门槛验证场景</p></div>' +
            '</article>' +
          '</div>' +
        '</div>' +
      '</section>' +
      '<section class="verify-flow section" id="verify-flow">' +
        '<div class="container">' +
          '<h2 class="section-title">验证流程</h2>' +
          '<p class="section-desc">三步完成验证，简单快捷</p>' +
          '<div class="flow-steps">' +
            '<div class="flow-step"><div class="flow-step-number">01</div><div class="flow-step-content"><h3>用户入群</h3><p>新成员加入群聊，触发验证流程</p></div><div class="flow-step-arrow">&darr;</div></div>' +
            '<div class="flow-step"><div class="flow-step-number">02</div><div class="flow-step-content"><h3>选择验证</h3><p>自动发送验证方式选择菜单，用户选择邮箱或数学题验证</p></div><div class="flow-step-arrow">&darr;</div></div>' +
            '<div class="flow-step"><div class="flow-step-number">03</div><div class="flow-step-content"><h3>验证结果</h3><p>验证成功发送欢迎语，超时自动踢出并公告</p></div></div>' +
          '</div>' +
        '</div>' +
      '</section>' +
      '<section class="core-features section" id="core-features">' +
        '<div class="container">' +
          '<h2 class="section-title">核心特性</h2>' +
          '<p class="section-desc">更多强大功能，全方位守护群聊</p>' +
          '<div class="core-grid">' +
            '<article class="core-card"><div class="core-card-icon">&#x1F4DD;</div><h3>自定义模板</h3><p>所有消息模板均支持变量替换，满足个性化需求</p></article>' +
            '<article class="core-card"><div class="core-card-icon">&#x1F504;</div><h3>回归用户检测</h3><p>自动识别之前验证成功的用户，重新入群时跳过验证流程</p></article>' +
            '<article class="core-card"><div class="core-card-icon">&#x1F4CA;</div><h3>数据库记录</h3><p>使用SQLite持久化存储所有验证记录</p></article>' +
            '<article class="core-card"><div class="core-card-icon">&#x1F310;</div><h3>多群管理</h3><p>可指定特定群开启验证，也可配置全局生效</p></article>' +
          '</div>' +
        '</div>' +
      '</section>' +
      '<section class="cta section" id="cta">' +
        '<div class="container">' +
          '<h2>立即体验</h2>' +
          '<p>在 AstrBot 管理面板搜索「群邮箱验证码」即可安装</p>' +
          '<div class="cta-actions"><a href="./install.html" class="btn btn-primary">查看安装指南 &rarr;</a></div>' +
        '</div>' +
      '</section>';
  }

  var dataScript = document.getElementById('features-data');
  if (dataScript && dataScript.textContent) {
    try {
      var data = JSON.parse(dataScript.textContent);
      renderAll(data);
      return;
    } catch (e) {}
  }

  fetch('./data/features.json')
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (data) {
      renderAll(data);
    })
    .catch(function () {
      renderFallback();
    });
})();