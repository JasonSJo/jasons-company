/* 상권조사 리포트 — analysis/build_report.py 의 render() 를 그대로 옮겼다.
   콘솔에서 내려받은 .md 와 CLI 가 만든 .md 는 같은 파일이어야 한다
   (analysis/tests/test_parity.py 가 문자열 단위로 대조한다). */
const Report = (() => {

  /* 표기 반올림도 모델과 같은 규칙(r2)을 먼저 통과시킨다.
     toFixed·toLocaleString 에 그냥 맡기면 파이썬 nf() 와 마지막 자리가 갈린다. */
  const num = (v, d = 0) => M.r2(Number(v || 0), d)
    .toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const fx = (v, d) => M.r2(Number(v || 0), d).toFixed(d);

  function nearby(site, pois, radius, kind) {
    const lat = M.f(site.위도), lon = M.f(site.경도);
    if (!lat || !lon) return [];
    return (pois || []).filter(p => String(p.분류 || '').trim() === kind)
      .map(p => {
        const plat = M.f(p.위도), plon = M.f(p.경도);
        if (!plat || !plon) return null;
        const d = M.haversine(lat, lon, plat, plon);
        return d <= radius ? { d, p } : null;
      }).filter(Boolean).sort((a, b) => a.d - b.d);
  }

  /* build_report.py 의 render() 와 줄 단위로 같은 마크다운을 만든다. */
  function markdown(site, pois, brand, dateStr) {
    const b = M.withDefaults(brand);
    const r = M.analyze(site, pois, b);
    const radius = M.f(b.반경_m, 500);
    const p = r.손익, rev = r.매출추정, c = r.경쟁;
    const [v, vNote] = M.verdict(r);
    const L = [];

    L.push(`# 상권조사 리포트 — ${r.후보지명}`, '',
      '| | |', '|---|---|',
      `| 브랜드 | ${b.브랜드 || '—'} |`,
      `| 주소 | ${r.주소 || '—'} |`,
      `| 조사 반경 | ${num(radius)}m |`,
      `| 조사일 | ${dateStr || U.today()} |`,
      `| 종합점수 | **${r.총점} / 100 (${r.등급}등급 · ${r.등급설명})** |`,
      `| 결론 | **${v}** |`, '',
      `> ${vNote}`, '',
      '## 1. 점수 요약', '',
      '| 항목 | 배점 | 획득 | 근거 |', '|---|---:|---:|---|');
    M.WEIGHT_KEYS.forEach((k, i) =>
      L.push(`| ${k} | ${M.WEIGHTS[k]} | ${r.항목[k]} | ${r.근거[i]} |`));
    L.push(`| **합계** | **100** | **${r.총점}** | |`);

    L.push('', '## 2. 배후수요', '',
      `- 주거인구 ${num(M.i(site.주거인구_500m))}명 · 아파트 ${num(M.i(site.아파트세대수))}세대`,
      `- 직장인구 ${num(M.i(site.직장인구_500m))}명 · 오피스빌딩 ${num(M.i(site.오피스빌딩수))}개`,
      `- 대학·학원 ${num(M.i(site.대학_학원수))}개`,
      `- 유동인구 일평균 ${num(M.i(site.유동인구_일평균))}명`);
    const stn = String(site.지하철역명 || '').trim();
    if (stn) {
      L.push(`- 최근접역 **${stn}** 도보 ${num(M.f(site.지하철_도보분))}분 · `
        + `일평균 승하차 ${num(M.i(site.지하철_일평균승하차))}명`);
    }

    L.push('', '## 3. 경쟁 현황', '',
      `반경 ${num(radius)}m 내 카페 **${c.카페수}곳** — `
      + `동일포지션(저가·테이크아웃) ${c.동일포지션}곳, 앵커 브랜드 ${c.앵커브랜드}곳.`, '');
    const cafes = nearby(site, pois, radius, '카페');
    if (cafes.length) {
      L.push('| 거리 | 상호 | 브랜드 |', '|---:|---|---|');
      cafes.slice(0, 15).forEach(({ d, p: q }) =>
        L.push(`| ${num(d)}m | ${q.상호 || ''} | ${q.브랜드 || ''} |`));
      if (cafes.length > 15) L.push(`| … | 외 ${cafes.length - 15}곳 | |`);
      if (cafes.length < c.카페수) {
        L.push('', `> 좌표가 확보된 곳만 표에 나옵니다. 현장 조사 기준 총 ${c.카페수}곳으로 `
          + '계산했습니다 (경쟁 과소평가 방지).');
      }
    } else {
      L.push('> 좌표 기반 POI 가 없어 현장 조사 수치로만 계산했습니다. '
        + '`collect_pois.py --live` 로 실제 목록을 수집하면 이 표가 채워집니다.');
    }
    if (c.자사점_최근접_m !== null) {
      L.push('', `- 자사 기존점 최근접 거리 **${num(c.자사점_최근접_m)}m**`
        + (c.자사점_최근접_m < 500 ? ' ⚠ 자기잠식 검토 필요' : ''));
    }

    const corner = ['Y', 'O'].includes(String(site.코너여부 || '').toUpperCase().charAt(0)) ? 'O' : 'X';
    L.push('', '## 4. 입지·접근성', '',
      `- ${M.i(site.층, 1)}층 · 전용 ${num(M.f(site.전용면적_평))}평 · `
      + `전면 ${num(M.f(site.전면길이_m))}m · 코너 ${corner} · `
      + `주차 ${M.i(site.주차가능대수)}대 · 좌석 ${M.i(site.좌석수)}석`,
      `- 보증금 ${num(M.f(site.보증금_만원))}만 · 월임대료 ${num(M.f(site.월임대료_만원))}만 · `
      + `관리비 ${num(M.f(site.관리비_만원))}만 · 권리금 ${num(M.f(site.권리금_만원))}만`,
      '', '## 5. 매출 추정', '',
      '추정 근거는 **상권 총 카페수요 × 자사 점유율** 입니다. '
      + '유동인구에 유입률을 한 번 곱하는 방식은 유동에 이미 포함된 직장·주거 인구를 '
      + '중복 계산해 매출을 과대추정하므로 쓰지 않았습니다.', '',
      '| 단계 | 값 |', '|---|---:|',
      `| 상권 하루 카페 이용객(추정) | ${num(rev.상권수요_일객수)}명 |`,
      `| 반경 내 카페 수 | ${rev.경쟁카페수}곳 |`,
      `| 입지 배수(접근성 반영) | ×${rev.입지배수} |`,
      `| **자사 점유율** | **${fx(rev.점유율 * 100, 2)}%** |`,
      `| 하루 객수(추정) | ${num(rev.일객수_추정)}명 |`,
      `| 객단가 | ${num(rev.객단가_원)}원 |`,
      `| **월 매출(추정)** | **${num(p.월매출_만원)}만원** |`);
    if (rev.좌석제약) {
      L.push('', `> 좌석 처리능력(${num(rev.좌석상한_일객수)}명/일)이 상한으로 작동했습니다. `
        + '테이크아웃 동선 강화 또는 좌석 확충 시 상향 여지가 있습니다.');
    }

    const other = p.고정비_만원 - p.인건비_만원 - p.임대료_만원;
    L.push('', '## 6. 추정 손익 (월)', '',
      '| 항목 | 금액(만원) |', '|---|---:|',
      `| 매출 | ${num(p.월매출_만원)} |`,
      `| 변동비 (${fx(p.변동비율 * 100, 1)}%) | −${num(p.변동비_만원)} |`,
      `| 인건비 | −${num(p.인건비_만원)} |`,
      `| 임대료·관리비 | −${num(p.임대료_만원)} |`,
      `| 기타 고정비 | −${num(other)} |`,
      `| **영업이익** | **${num(p.영업이익_만원)} (${fx(p.영업이익률 * 100, 1)}%)** |`, '',
      `- 손익분기 월매출 **${p.BEP월매출_만원 === null ? '도달 불가' : num(p.BEP월매출_만원)}`
      + `${p.BEP월매출_만원 === null ? '' : '만원'}** `
      + `(현재 추정 대비 ${num(p.BEP달성률 * 100)}%)`,
      `- 초기투자 **${num(p.초기투자_만원)}만원** `
      + `(보증금 ${num(p.보증금_만원)}만 회수분 제외 시 ${num(p.회수대상투자_만원)}만원)`,
      `- 투자회수 **${p.투자회수_개월 === null ? '—' : p.투자회수_개월}개월**`);

    L.push('', '## 7. 리스크', '');
    if (r.리스크.length) r.리스크.forEach(x => L.push(`- ${x}`));
    else L.push('- 특이 리스크 없음');

    L.push('', '## 8. 결론', '', `**${v}** — ${vNote}`, '', '---', '',
      '※ 본 리포트의 매출·손익은 공개 지표와 규칙 기반 모델에 의한 **추정치**이며, '
      + '실제 매출을 보장하지 않습니다. 가맹 계약 전 반드시 현장 실사와 '
      + '가맹사업법상 정보공개서를 함께 검토하십시오.');
    return L.join('\n');
  }

  /* 순위표 — score_sites.py 의 상단 요약과 같은 표. */
  function ranking() {
    const rows = S.analyzed(), b = S.brand();
    const L = [`# 상권 후보지 우선순위 — ${b.브랜드 || '카페 프랜차이즈'}`, '',
      `후보지 ${rows.length}곳 · 상권 반경 ${num(M.f(b.반경_m, 500))}m · `
      + `객단가 ${num(M.f(b.객단가_원, 5200))}원 기준`, '',
      '| 순위 | 후보지 | 총점 | 등급 | 추정 월매출 | 영업이익 | BEP달성 | 회수개월 | 심의 |',
      '|---:|---|---:|:--:|---:|---:|---:|---:|---|'];
    rows.forEach(({ r }, i) => {
      const p = r.손익;
      L.push(`| ${i + 1} | ${r.후보지명} | **${r.총점}** | ${r.등급} | ${num(p.월매출_만원)}만 | `
        + `${num(p.영업이익_만원)}만 | ${num(p.BEP달성률 * 100)}% | `
        + `${p.투자회수_개월 === null ? '—' : num(p.투자회수_개월)} | ${M.verdict(r)[0]} |`);
    });
    L.push('', '> 등급: **A** 즉시 출점 검토(80+) · **B** 조건부 추천(65+) · '
      + '**C** 보류·재협상(50+) · **D** 부적합');
    return L.join('\n');
  }

  function render() {
    const el = document.getElementById('rp-body');
    const site = S.current();
    if (!site) {
      el.innerHTML = `<div class="empty"><b>후보지를 먼저 추가하세요</b>
        후보지가 있어야 리포트를 만들 수 있습니다.</div>`;
      return;
    }
    const md = markdown(site, S.get().pois, S.brand());
    el.innerHTML = `
      <div class="panel-head">
        <div><h3>${U.esc(site.후보지명 || '후보지')} 상권조사 리포트</h3>
          <p>가맹 희망자·투자 심의에 제출할 수 있는 형태입니다.
             <code>build_report.py</code> 가 만드는 파일과 같은 내용입니다.</p></div>
        <div class="acts">
          <button class="sm" id="rp-copy">복사</button>
          <button class="sm" id="rp-rank">순위표 내려받기</button>
          <button class="sm primary" id="rp-dl">리포트 내려받기</button>
        </div>
      </div>
      <div class="mdout" id="rp-md">${U.esc(md)}</div>`;

    document.getElementById('rp-dl').onclick = () => {
      U.download(`상권조사_${(site.후보지명 || '후보지').replace(/[\/\s]/g, '_')}.md`, md, 'text/markdown');
      U.toast('리포트를 내려받았습니다');
    };
    document.getElementById('rp-rank').onclick = () => {
      U.download('상권_후보지_순위.md', ranking(), 'text/markdown');
      U.toast('순위표를 내려받았습니다');
    };
    document.getElementById('rp-copy').onclick = async () => {
      try {
        await navigator.clipboard.writeText(md);
        U.toast('클립보드에 복사했습니다');
      } catch (e) {
        // file:// 이나 권한 거부 시 — 직접 선택할 수 있게 안내
        U.toast('복사 권한이 없습니다. 아래 본문을 직접 선택해 복사하세요.');
      }
    };
  }

  return { render, markdown, ranking };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Report;
