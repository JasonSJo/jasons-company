/* 위치 모듈 동작 확인 — 좌표 파서·이름 제안·외부 링크를 stdout 으로 낸다.
   tests/test_place.py 가 대조한다. 네트워크는 쓰지 않는다(순수 함수만 검사). */
const path = require('path');
const PLACE = require(path.resolve(__dirname, '..', '..', 'input', 'js', 'place.js'));

const coords = [
  '37.5445, 127.0557', '127.0557, 37.5445', '위도 37.5445 경도 127.0557',
  '37.5445\t127.0557', '서울시', '1, 2', '', '37.5445',
].map(t => ({ 입력: t, 결과: PLACE.parseCoords(t) }));

const names = [
  { 이름: '스타벅스 성수점', 주소: '서울 성동구 연무장길 42' },
  { 이름: '', 주소: '서울 성동구 연무장길 42' },
  { 이름: '', 주소: '서울 성동구' },
].map(h => ({ 입력: h, 결과: PLACE.suggestName(h) }));

const lawd = ['1114010300', '11140', '', 'abc', '111'].map(b => ({ 입력: b, 결과: PLACE.lawdCode(b) }));

process.stdout.write(JSON.stringify({
  coords, names, lawd,
  서비스: PLACE.SERVICES.map(s => s.이름),
  링크: PLACE.links({ 주소: '서울 성동구 연무장길 42' }),
  링크_주소없음: PLACE.links({ 주소: '' }),
}, null, 1));
