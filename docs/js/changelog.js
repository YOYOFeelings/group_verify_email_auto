document.addEventListener('DOMContentLoaded', async function () {
  const container = document.getElementById('changelog-container');
  if (!container) return;

  try {
    const response = await fetch('https://api.github.com/repos/YOYOFeelings/group_verify_email_auto/releases');
    if (!response.ok) return;
    const releases = await response.json();
    if (!Array.isArray(releases) || releases.length === 0) return;

    container.innerHTML = '';

    releases.forEach(function (release, index) {
      const card = document.createElement('div');
      card.className = 'version-card';
      if (index === 0) {
        card.classList.add('latest');
      }

      const versionDiv = document.createElement('div');
      versionDiv.className = 'version';
      versionDiv.textContent = release.tag_name || release.name || '';

      if (index === 0) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = '最新';
        versionDiv.appendChild(badge);
      }

      card.appendChild(versionDiv);

      const changesUl = document.createElement('ul');
      changesUl.className = 'changes';

      if (release.body) {
        const lines = release.body.split('\n');
        lines.forEach(function (line) {
          const trimmed = line.trim();
          if (trimmed) {
            const li = document.createElement('li');
            li.textContent = trimmed;
            changesUl.appendChild(li);
          }
        });
      }

      card.appendChild(changesUl);
      container.appendChild(card);
    });
  } catch (e) {
    // Keep fallback content on error
  }
});