/* 위치 확정 — 주소를 골라 좌표·이름을 채우고, 부동산 정보 사이트로 이어 준다.

   ── 왜 이렇게 되어 있나 ──
   알고리즘은 좌표를 반드시 요구한다(M1 등시선 조회·M2 격자 교차·M3 경쟁 거리).
   그런데 주소→좌표 변환은 무료·무키로는 불가능하다. 그래서 두 경로를 둔다.

     키 있음  카카오맵 JS SDK — 주소·상호 검색 즉시 좌표까지 채운다.
              JS 키는 도메인 제한으로 보호되므로 공개 페이지에 넣어도 안전하다.
     키 없음  다음 우편번호 서비스(무키) 로 주소만 받고, 좌표는 지도에서 복사해
              붙여넣는다. 발급 절차 없이 바로 쓸 수 있다.

   부동산 정보(네이버지도·네이버부동산·호갱노노·국토부)는 **가져오지 않는다.**
   공개 API 가 없고 약관이 스크래핑을 금지하며 정적 페이지는 CORS 로 막힌다.
   대신 주소로 각 서비스를 새 탭에 여는 링크를 만든다 — 네 곳에 복붙하는 수고만 없앤다. */
const PLACE = (() => {
  'use strict';

  const KEY_STORE = 'cafe-trade-area/kakao-js-key';
  const SDK = 'https://dapi.kakao.com/v2/maps/sdk.js';
  const POSTCODE = 'https://t1.daumcdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js';

  /* ── 키 ─────────────────────────────── */
  function getKey() {
    try { return (localStorage.getItem(KEY_STORE) || '').trim(); }
    catch (e) { return ''; }
  }
  function setKey(v) {
    try {
      const k = String(v || '').trim();
      if (k) localStorage.setItem(KEY_STORE, k); else localStorage.removeItem(KEY_STORE);
    } catch (e) { /* 시크릿 모드 */ }
  }
  const hasKey = () => !!getKey();

  /* ── 스크립트 로드 ─────────────────────────────── */
  const loaded = {};
  function script(src) {
    if (loaded[src]) return loaded[src];
    loaded[src] = new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = () => res(true);
      s.onerror = () => { delete loaded[src]; rej(new Error('스크립트를 불러오지 못했습니다')); };
      document.head.appendChild(s);
    });
    return loaded[src];
  }

  function loadKakao() {
    const key = getKey();
    if (!key) return Promise.reject(new Error('카카오 JS 키가 없습니다'));
    if (window.kakao && window.kakao.maps && window.kakao.maps.services) return Promise.resolve(true);
    return script(`${SDK}?appkey=${encodeURIComponent(key)}&libraries=services&autoload=false`)
      .then(() => new Promise(res => window.kakao.maps.load(() => res(true))));
  }

  /* ── 검색 (키 있음) ─────────────────────────────── */
  // 주소든 상호든 한 칸에 넣게 한다. 주소로 먼저 찾고, 없으면 장소명으로 찾는다.
  function search(query) {
    const q = String(query || '').trim();
    if (!q) return Promise.resolve([]);
    return loadKakao().then(() => new Promise(resolve => {
      const geo = new window.kakao.maps.services.Geocoder();
      const places = new window.kakao.maps.services.Places();
      const OK = window.kakao.maps.services.Status.OK;

      geo.addressSearch(q, (addrRes, addrStatus) => {
        const fromAddr = (addrStatus === OK ? addrRes : []).map(r => ({
          이름: (r.road_address && r.road_address.building_name) || '',
          주소: (r.road_address && r.road_address.address_name) || r.address_name || '',
          지번: (r.address && r.address.address_name) || '',
          우편번호: (r.road_address && r.road_address.zone_no) || '',
          법정동코드: (r.address && r.address.b_code) || '',
          위도: Number(r.y), 경도: Number(r.x), 출처: '주소',
        }));
        places.keywordSearch(q, (plRes, plStatus) => {
          // 장소 검색은 우편번호·법정동코드를 주지 않는다. 빈 값으로 두고,
          // 필요하면 '주소만 고르기'(우편번호 서비스)로 채운다.
          const fromPlace = (plStatus === OK ? plRes : []).map(r => ({
            이름: r.place_name || '',
            주소: r.road_address_name || r.address_name || '',
            지번: r.address_name || '',
            우편번호: '', 법정동코드: '',
            위도: Number(r.y), 경도: Number(r.x), 출처: '장소',
          }));
          // 주소 결과를 먼저 — 후보지는 '그 자리'가 기준이지 상호가 기준이 아니다
          const all = fromAddr.concat(fromPlace)
            .filter(r => Number.isFinite(r.위도) && Number.isFinite(r.경도) && r.주소);
          const seen = {}, out = [];
          all.forEach(r => {
            const k = `${r.주소}|${r.이름}`;
            if (seen[k]) return;
            seen[k] = true;
            out.push(r);
          });
          resolve(out.slice(0, 8));
        });
      });
    }));
  }

  /* ── 주소만 (키 없음) ─────────────────────────────── */
  // 다음 우편번호 서비스는 키가 필요 없다. 대신 좌표는 주지 않는다.
  function openPostcode() {
    return script(POSTCODE).then(() => new Promise((resolve, reject) => {
      if (!window.daum || !window.daum.Postcode) {
        reject(new Error('우편번호 서비스를 불러오지 못했습니다'));
        return;
      }
      let done = false;
      new window.daum.Postcode({
        oncomplete: data => {
          done = true;
          resolve({
            이름: data.buildingName || '',
            주소: data.roadAddress || data.address || '',
            지번: data.jibunAddress || '',
            // zonecode = 5자리 신우편번호, bcode = 10자리 법정동코드.
            // 법정동코드 앞 5자리가 국토교통부 실거래가 API 의 지역코드(LAWD_CD)다.
            우편번호: data.zonecode || '',
            법정동코드: data.bcode || '',
            위도: null, 경도: null, 출처: '우편번호',
          });
        },
        onclose: () => { if (!done) reject(new Error('취소')); },
      }).open();
    }));
  }

  /* ── 좌표 붙여넣기 ─────────────────────────────── */
  /* 네이버지도·구글지도에서 '좌표 복사' 한 문자열을 그대로 받는다.
     "37.5445, 127.0557" · "위도 37.5445 경도 127.0557" · 탭 구분 등. */
  function parseCoords(text) {
    const nums = String(text || '').match(/-?\d+(?:\.\d+)?/g);
    if (!nums || nums.length < 2) return null;
    let a = Number(nums[0]), b = Number(nums[1]);
    // 한국 범위로 판별해 순서가 뒤바뀐 입력도 받아 준다
    const isLat = v => v >= 33 && v <= 39;
    const isLon = v => v >= 124 && v <= 132;
    if (isLat(a) && isLon(b)) return { 위도: a, 경도: b };
    if (isLon(a) && isLat(b)) return { 위도: b, 경도: a };
    return null;
  }

  /* ── 실거래가 지역코드 ─────────────────────────────── */
  /* 국토교통부 실거래가 API 는 법정동코드 앞 5자리(시군구 코드)를 지역코드로 받는다.
     10자리 전체를 넣으면 조회되지 않으므로 여기서 잘라 둔다. */
  function lawdCode(bcode) {
    const b = String(bcode || '').replace(/\D/g, '');
    return b.length >= 5 ? b.slice(0, 5) : '';
  }

  /* ── 후보지명 제안 ─────────────────────────────── */
  /* 이름은 심의표와 등시선 조회의 키다. 사람이 알아볼 수 있으면서 짧아야 한다.
     건물·상호가 있으면 그것을, 없으면 '구 + 길이름 + 번지'로 줄인다. */
  function suggestName(hit) {
    if (!hit) return '';
    if (hit.이름) return hit.이름.trim();
    const parts = String(hit.주소 || '').trim().split(/\s+/);
    if (parts.length <= 2) return parts.join(' ');
    return parts.slice(-3).join(' ');   // 예: 성동구 연무장길 42
  }

  /* ── 부동산 정보 링크 ─────────────────────────────── */
  /* 각 서비스의 검색 URL 로 새 탭을 연다. 데이터를 읽어 오는 것이 아니라
     사람이 그 사이트에서 직접 보는 것이다.

     ⚠ URL 형식은 각 서비스가 언제든 바꿀 수 있다. 형식이 어긋나면 최소한
     해당 사이트에는 도착하므로 거기서 검색하면 된다. */
  const SERVICES = [
    { id: 'naver-map', 이름: '네이버지도', 설명: '위치·주변 시설',
      url: q => `https://map.naver.com/p/search/${encodeURIComponent(q)}` },
    { id: 'naver-land', 이름: '네이버 부동산', 설명: '매물·시세',
      url: q => `https://new.land.naver.com/search?sk=${encodeURIComponent(q)}` },
    { id: 'hogangnono', 이름: '호갱노노', 설명: '실거래가·주변 분석',
      url: q => `https://hogangnono.com/search?q=${encodeURIComponent(q)}` },
    { id: 'kras', 이름: '일사편리', 설명: '부동산종합증명 (국토교통부)',
      url: () => 'https://kras.go.kr/' },
  ];

  function links(site) {
    const q = String((site && (site.주소 || site.후보지명)) || '').trim();
    if (!q) return [];
    return SERVICES.map(s => ({ id: s.id, 이름: s.이름, 설명: s.설명, href: s.url(q) }));
  }

  return { getKey, setKey, hasKey, search, openPostcode, parseCoords,
           suggestName, lawdCode, links, SERVICES };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = PLACE;
