# QUICKSTART — 셋업부터 첫 계약까지

업종 전문 콘텐츠 대행 시스템을 실제로 가동하는 순서. 기호: 🙋 사람만 · 🤖 자동 · 💳 비용/결제.

---

## STEP 0 · 문 열기 (반나절, 대부분 완료됨)

| 항목 | 상태 | 방법 |
|---|---|---|
| 연락처 | ✅ 완료 | 카카오톡 오픈채팅 + 이메일 `ceo-jason@jasons-consulting.com` |
| 🙋 랜딩페이지 라이브 | ⬜ | 저장소 **Settings → Pages → Source: GitHub Actions** → push 시 자동 배포 |
| 🙋 리드 폼 백엔드(선택) | ⬜ | `ops/리드-백엔드-설정.md` (카톡+이메일로 충분하면 생략 가능) |
| (선택) 상호 | — | 예시값 `콘텐츠하다` → 실제 브랜드명으로 교체 원할 때 |

배포 후 랜딩페이지 URL을 확보해 카톡·명함·SNS 프로필에 건다.

## STEP 1 · 타깃 잡기 (🙋 2시간)

1. 한 업종·한 지역 선정 (예: 성수동 요식업). 집중이 사례를 만든다.
2. `automation/타겟리스트.example.csv` 형식으로 20~30곳 수집
   - 니즈 신호: 리뷰 적음 / 답글 없음 / SNS 방치 / 신규 오픈
3. 우선순위 정렬:
   ```
   cd content-agency/automation
   python score_prospects.py --csv 타겟리스트.example.csv
   # → output/타겟_우선순위.md (🔥 최우선부터 접촉)
   ```

## STEP 2 · 무기 준비 (🤖 무료 / 💳 실제본은 승인)

4. 샘플 콘텐츠(영업 미끼) 초안 생성:
   ```
   python build_calendar.py --business business.example.yaml --days 30   # 30일 캘린더
   python generate_content.py --calendar content_calendar.generated.yaml  # dry-run: 무료
   # 실제 콘텐츠(💳 토큰 비용, 승인 후): python generate_content.py --calendar ... --live
   ```
5. 검수: `automation/review.html` 열어 승인/보류/반려 → 승인본 내보내기
6. 영업 자산: `ops/영업-아웃리치-키트.md` (스크립트) · `ops/제안서-견적서-템플릿.md` (클로징)

## STEP 3 · 영업 실행 (🙋 매일 10~20곳)

7. 우선순위 상단부터 **콜드 아웃리치** — "무료 진단 + 샘플 1건" 미끼
8. 문의 → **카카오톡/이메일 상담** → 30분 무료 진단
9. 진단 요약으로 제안서 작성 → 요금제 제안

## STEP 4 · 클로징·납품 (🙋💳 계약 / 🤖 생산)

10. 💳 계약·결제 (스타터 49만원/월~, 첫 달 미달 시 50% 환급으로 진입장벽↓)
11. 🤖 납품 파이프라인:
    ```
    build_calendar → generate_content → review(승인) → publish → [게시] → report
    ```
12. 매월 `python report.py --brand "업체명" --month YYYY-MM` 로 성과 리포트 발송

---

## 현실 체크
- **매출은 STEP 3~4(영업·계약)에서만** 발생하며, 이는 사람의 일이다.
- 시스템의 가치는 **1인이 3~5곳을 동시 운영**하게 해 마진을 만드는 것 — 확장의 무기다.
- 첫 계약 공식: **한 업종 집중 + 무료 샘플 신뢰 + 성과 보장 리스크 제거.**
- 접촉 30~50곳 → 첫 계약 1건이 정상 전환율. 물량이 답.

## 파일 지도
- 랜딩/폼: `index.html`, `ops/리드-수집-폼.html`
- 전략: `playbooks/*.md`, `templates/*.md`
- 자동화: `automation/*.py`, `automation/review.html`
- 영업: `ops/첫-수익-실행계획.md`, `ops/영업-아웃리치-키트.md`, `ops/제안서-견적서-템플릿.md`
- 운영: `ops/수익화-런북.md`, `ops/온보딩-체크리스트.md`, `ops/월간-리포트-템플릿.md`
