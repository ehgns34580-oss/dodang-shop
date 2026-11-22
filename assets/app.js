(() => {
  // 검색 + 카테고리 칩
  const q = document.querySelector('.q');
  const rows = [...document.querySelectorAll('.searchable')];
  let cat = '';
  const apply = () => {
    const s = (q ? q.value : '').trim().toLowerCase();
    rows.forEach(r => {
      r.hidden = !((!cat || r.dataset.c === cat) && (!s || (r.dataset.q || '').includes(s)));
    });
  };
  if (q) q.addEventListener('input', apply);
  document.querySelectorAll('.chips button').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.chips button').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    cat = b.dataset.c;
    apply();
  }));

  // 영상 특정 시점으로 이동 (YouTube iframe API postMessage)
  const yt = document.getElementById('yt');
  const send = (func, args) => yt && yt.contentWindow.postMessage(JSON.stringify({ event: 'command', func, args: args || [] }), '*');
  document.querySelectorAll('.seek').forEach(b => b.addEventListener('click', () => {
    send('seekTo', [Number(b.dataset.t), true]);
    send('playVideo');
    yt.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }));
})();

// 모바일: 현재 메뉴가 보이도록 가로 스크롤 맞추기
(() => {
  const on = document.querySelector('.top nav a.on');
  if (on) on.scrollIntoView({ block: 'nearest', inline: 'center' });
})();
